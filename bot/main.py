import os
import uuid
import logging
import time
import shutil
import re
import asyncio

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import yt_dlp # type: ignore

from telegram import Update # type: ignore
from telegram.ext import ( # type: ignore
	ApplicationBuilder,
	MessageHandler,
	CommandHandler,
	ContextTypes,
	filters,
)

from db import (
	init_db,
	register_user,
	increment_downloads,
	log_download,
	get_total_users,
)


# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(levelname)s - %(message)s",
)

# Reduce telegram polling noise
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --------------------------------------------------
# Download queue control
# --------------------------------------------------
DOWNLOAD_WORKERS = 2
download_queue: asyncio.Queue = asyncio.Queue()

# --------------------------------------------------
# yt-dlp retry settings
# --------------------------------------------------
YTDLP_MAX_RETRIES = 3
YTDLP_RETRY_DELAY = 7  # seconds
YTDLP_403_NOTIFY_THRESHOLD = 5

# --------------------------------------------------
# Environment
# --------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
	raise RuntimeError("BOT_TOKEN is not set")

BOT_USERNAME = os.getenv("BOT_USERNAME", "@ytaudio_down_bot")
BOT_TITLE = os.getenv("BOT_TITLE", "Yura Downloader")
BOT_CAPTION = os.getenv("BOT_CAPTION", "🎧 via 👉 ")

APP_ENV = os.getenv("APP_ENV", "prod")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

COOKIES_PATH = "/cookies.txt"

if APP_ENV == "dev":
	logging.info("Running in DEV mode")
else:
	logging.info("Running in PROD mode")

# --------------------------------------------------
# Paths
# --------------------------------------------------
STORAGE_DIR = Path("/storage/audio")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# Constants
# --------------------------------------------------
AUDIO_CODEC = "aac"         	# aac | mp3 | opus
AUDIO_CONTAINER = "m4a" 		# m4a | mp3 | ogg
# BITRATE_LEVELS = [192, 160, 128, 96, 64]
AUDIO_BITRATE_KBPS = 64	  		# 64 | 96 | 128 | 160 | 192

MAX_TG_AUDIO_MB = 50 			# Telegram upload limit
MAX_TG_AUDIO_MARGIN_MB = 5 		# Safety margin
MAX_TG_AUDIO_EFFECTIVE_MB = MAX_TG_AUDIO_MB - MAX_TG_AUDIO_MARGIN_MB

MAX_STORAGE_HOURS = 12 			# How long to keep files on disk

LONG_VIDEO_SECONDS = 7200 		# 2 hours

LONG_WARNING_SECONDS = 1800  	# 30 min
BIG_WARNING_MB = 40 			# 40 MB

# --------------------------------------------------
# Helpers | utils
# --------------------------------------------------
def estimate_audio_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	"""
	Estimate audio file size in MB based on duration and bitrate.
	Works for mp3, m4a (AAC), opus, etc.
	"""
	return duration_sec * bitrate_kbps / 8 / 1024


def cleanup_old_files():
	now = time.time()

	for f in STORAGE_DIR.glob(f"*.{AUDIO_CONTAINER}"):
		if now - f.stat().st_mtime > MAX_STORAGE_HOURS * 3600:
			try:
				f.unlink()
			except Exception:
				logging.exception("Failed to remove old file")


def safe_filename(text: str, max_len: int = 150) -> str:
	"""
	Remove forbidden characters and limit filename length.
	"""
	text = re.sub(r'[\\/*?:"<>|]', "", text)
	text = re.sub(r"\s+", " ", text).strip()
	return text[:max_len]


def format_duration(seconds: int) -> str:
	"""
	Format duration in HH:MM or MM min.
	"""
	if seconds <= 0:
		return "unknown"

	h = seconds // 3600
	m = (seconds % 3600) // 60

	if h > 0:
		return f"{h:02d}:{m:02d}"
	return f"{m:02d} min"


def format_date(yyyymmdd: Optional[str]) -> str:
	"""
	Convert YYYYMMDD -> YYYY-MM-DD
	"""
	if not yyyymmdd or len(yyyymmdd) != 8:
		return "unknown-date"

	return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def build_audio_filename(info: dict) -> str:
	"""
	Build human-readable audio filename:
	Channel – Title (HH:MM, YYYY-MM-DD).m4a
	"""
	channel = (
		info.get("channel")
		or info.get("uploader")
		or "YouTube"
	)

	title = info.get("title", "audio")
	duration = info.get("duration", 0)
	upload_date = info.get("upload_date")

	duration_str = format_duration(duration)
	date_str = format_date(upload_date)

	filename = (
		f"{channel} – {title} "
		f"({duration_str}, {date_str}).{AUDIO_CONTAINER}"
	)

	return safe_filename(filename)


# --------------------------------------------------
# yt-dlp base options
# --------------------------------------------------
def ydl_base_opts():
	return {
		"cookies": COOKIES_PATH,
		"quiet": True,
		"socket_timeout": 30,
		"retries": 3,
		"fragment_retries": 3,
		"noplaylist": True,
		"js_runtimes": {
			"node": {
				"path": "/usr/bin/node"
			}
		},
		"remote_components": ["ejs:github"],
	}


# --------------------------------------------------
# Workers | background tasks
# --------------------------------------------------
async def download_worker(worker_id: int):
	logging.info(f"Worker #{worker_id} started")

	while True:
		job = await download_queue.get()

		try:
			await process_job(job)
		except Exception:
			logging.exception("Worker job failed")
		finally:
			download_queue.task_done()


async def ytdlp_download_with_retry(
	url: str,
	opts: dict,
	video_id: Optional[str],
	application,
):
	last_error = None

	for attempt in range(1, YTDLP_MAX_RETRIES + 1):
		try:
			return await asyncio.to_thread(
				lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=True)
			)

		except Exception as e:
			last_error = e
			msg = str(e)

			if "403" in msg:
				logging.warning(f"YouTube 403 (attempt {attempt}/{YTDLP_MAX_RETRIES})")

				# --- log 403 ---
				from db import log_youtube_error, count_today_youtube_403
				log_youtube_error("403", url, video_id)

				# --- notify admin if threshold reached ---
				count = count_today_youtube_403()
				if count == YTDLP_403_NOTIFY_THRESHOLD:
					await application.bot.send_message(
						chat_id=ADMIN_USER_ID,
						text=(
							"⚠️ <b>YouTube 403 errors detected</b>\n\n"
							f"403 errors today: {count}\n"
							"YouTube may be throttling downloads."
						),
						parse_mode="HTML",
					)

				if attempt < YTDLP_MAX_RETRIES:
					await asyncio.sleep(YTDLP_RETRY_DELAY)
					continue

			raise

	raise last_error


async def process_job(job: dict):
	user = job["user"]
	url = job["url"]
	status_msg = job["status_msg"]
	application = job["application"]

	info = None

	try:
		await status_msg.edit_text("🔍 Reading video info…")


		# --- Extract metadata ---
		try:
			opts = ydl_base_opts()
			opts["skip_download"] = True

			info = await asyncio.to_thread(
				lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
			)
		except Exception as e:
			logging.exception("Metadata extraction failed")
			await status_msg.edit_text("❌ Failed to read video info.")

			log_download(
				user_id=user.id,
				video_url=url,
				video_id=None,
				video_title=None,
				duration_seconds=None,
				chosen_bitrate=AUDIO_BITRATE_KBPS,
				estimated_size_mb=None,
				real_size_mb=None,
				delivery_method="failed",
				status="failed",
				error_message=str(e),
			)
			return

		title = info.get("title", "audio")
		duration = info.get("duration", 0)


		# -- Validate duration ---
		if not duration:
			logging.warning("Video duration unknown")
			await status_msg.edit_text("❌ Cannot determine video duration.")

			log_download(
				user_id=user.id,
				video_url=url,
				video_id=info.get("id") if info else None,
				video_title=title if "title" in locals() else None,
				duration_seconds=duration if "duration" in locals() else None,
				chosen_bitrate=AUDIO_BITRATE_KBPS,
				estimated_size_mb=estimated_size if "estimated_size" in locals() else None,
				real_size_mb=None,
				delivery_method="failed",
				status="failed",
				error_message="Unknown video duration",
			)

			return


		estimated_size = estimate_audio_size_mb(duration, AUDIO_BITRATE_KBPS)
		estimated_size_mb = round(estimated_size, 2)

		warning_line = ""
		if duration >= LONG_WARNING_SECONDS:
			warning_line += "\n\n⏰ This is a long video. Please be patient."

		elif estimated_size >= BIG_WARNING_MB:
			warning_line += "\n\n⏰ This is a large audio file. Please be patient."

		logging.info(
			f"Video: {title} | "
			f"Duration: {duration}s | "
			f"Estimated size: {estimated_size_mb:.1f} MB"
		)


		# --- Telegram upload possible ---
		if estimated_size <= MAX_TG_AUDIO_EFFECTIVE_MB:
			await status_msg.edit_text(f"⬇️ Downloading audio ≈ {estimated_size_mb:.1f} MB{warning_line}")

			tmp_id = uuid.uuid4().hex

			opts = ydl_base_opts()
			opts.update({
				"format": "bestaudio/best",
				"outtmpl": f"/tmp/{tmp_id}.%(ext)s",
				"postprocessors": [
					{
						"key": "FFmpegExtractAudio",
						"preferredcodec": AUDIO_CODEC,
						"preferredquality": str(AUDIO_BITRATE_KBPS),
					},
					{
						"key": "FFmpegThumbnailsConvertor",
						"format": "jpg",
					},					
					{
						"key": "EmbedThumbnail",
					},
					{
						"key": "FFmpegMetadata",
					},
				],
				"postprocessor_args": [
					"-metadata", f"title={title}",
					"-metadata", f"artist={info.get('uploader', '')}",
					"-metadata", "album=YouTube",
					"-metadata", "comment=Downloaded via YouTube Audio Downloader @ytaudio_down_bot",
				],
			})

			try:
				await ytdlp_download_with_retry(
					url=url,
					opts=opts,
					video_id=info.get("id"),
					application=application,
				)

				# 🔑 Search for file
				tmp_dir = Path("/tmp")
				files = list(tmp_dir.glob(f"{tmp_id}.*"))

				if not files:
					raise RuntimeError("Downloaded audio file not found")
				
				tmp_path = files[0]

				real_size_mb = round(tmp_path.stat().st_size / 1024 / 1024, 2)
				logging.info(f"Real size: {real_size_mb:.1f} MB")

				thumb_url = info.get("thumbnail")
				if thumb_url:
					# --- Send thumbnail ---
					thumb_msg = await status_msg.reply_photo(
						photo=thumb_url,
					)

				# --- Send audio ---
				with open(tmp_path, "rb") as f:
					await status_msg.reply_audio(
						audio=f,
						title=title,
						performer=info.get("uploader"),
						duration=duration,
						filename=build_audio_filename(info),
						caption=f"{BOT_CAPTION} <b>{BOT_USERNAME}</b>",
						parse_mode="HTML",
						reply_to_message_id=thumb_msg.message_id if thumb_msg else None,
					)
				await status_msg.delete()

				increment_downloads(user.id)
				log_download(
					user_id=user.id,
					video_url=url,
					video_id=info.get("id"),
					video_title=title,
					duration_seconds=duration,
					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size_mb,
					real_size_mb=real_size_mb,
					delivery_method="telegram",
					status="success",
				)

			except Exception as e:
				logging.exception("Telegram upload failed")
				await status_msg.edit_text("❌ Failed to send audio.")
				log_download(
					user_id=user.id,
					video_url=url,
					video_id=info.get("id") if info else None,
					video_title=title if "title" in locals() else None,
					duration_seconds=duration if "duration" in locals() else None,
					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
					real_size_mb=real_size_mb if "real_size_mb" in locals() else None,
					delivery_method="failed",
					status="failed",
					error_message=str(e),
				)	

			finally:
				if "tmp_path" in locals() and tmp_path.exists():
					tmp_path.unlink()
				
			return
		
		# --- Fallback: download link ---
		if duration >= LONG_VIDEO_SECONDS:
			await status_msg.edit_text(
				"⚠️ This video is longer than 2 hours. I will create a download link instead.\n\n"
				"⏰ Please wait, processing may take some time."
			)		
		else:
			await status_msg.edit_text(
				"⚠️ This video is too large for Telegram upload. I can create a download link instead.\n\n"
				"⏰ Please wait, processing may take some time."
			)

		file_id = uuid.uuid4().hex
		final_path = STORAGE_DIR / f"{file_id}.{AUDIO_CONTAINER}"

		opts = ydl_base_opts()
		opts.update({
			"format": "bestaudio/best",
			"outtmpl": f"/tmp/{file_id}.%(ext)s",
			"postprocessors": [
				{
					"key": "FFmpegExtractAudio",
					"preferredcodec": AUDIO_CODEC,
					"preferredquality": str(AUDIO_BITRATE_KBPS),
				},
				{
					"key": "FFmpegThumbnailsConvertor",
					"format": "jpg",
				},				
				{
					"key": "EmbedThumbnail",
				},
				{
					"key": "FFmpegMetadata",
				},
			],
			"postprocessor_args": [
				"-metadata", f"title={title}",
				"-metadata", f"artist={info.get('uploader', '')}",
				"-metadata", "album=YouTube",
				"-metadata", f"comment={BOT_CAPTION} {BOT_USERNAME}",
				"-metadata", f"encoded_by={BOT_USERNAME}",
			],
		})

		try:
			await ytdlp_download_with_retry(
				url=url,
				opts=opts,
				video_id=info.get("id"),
				application=application,
			)

			tmp_dir = Path("/tmp")
			files = list(tmp_dir.glob(f"{file_id}.*"))

			if not files:
				raise RuntimeError("Downloaded audio file not found")

			tmp_path = files[0]
			shutil.move(str(tmp_path), str(final_path))

			size_mb = round((final_path.stat().st_size / 1024 / 1024), 2)

			link = f"{BASE_URL}/audio/{final_path.name}"
			filename_download = build_audio_filename(info)

			logging.info(
				f"File saved: {final_path.name} | "
				f"Real size: {size_mb:.1f} MB | "
				f"Link: {link} | "
				f"Filename: {filename_download}"
			)

			thumb_url = info.get("thumbnail")
			await status_msg.reply_photo(
				photo=thumb_url,
				caption=(
					f"✅ <b>Your audio is ready</b>\n\n"
					f"🎵 <a href=\"{link}\">{filename_download}</a>\n"
					f"⏰ Available for 12 hours\n\n"
					f"{BOT_CAPTION} <b>{BOT_USERNAME}</b>"
				),
				parse_mode="HTML",
			)
			await status_msg.delete()

			increment_downloads(user.id)
			log_download(
				user_id=user.id,
				video_url=url,
				video_id=info.get("id"),
				video_title=title,
				duration_seconds=duration,
				chosen_bitrate=AUDIO_BITRATE_KBPS,
				estimated_size_mb=estimated_size_mb,
				real_size_mb=size_mb,
				delivery_method="link",
				status="success",
				file_path=str(final_path),
				download_url=link,
				fallback_reason="too_large",
			)

		except Exception as e:
			logging.exception("Download link generation failed")
			await status_msg.edit_text("❌ Failed to create download link.")

			log_download(
				user_id=user.id,
				video_url=url,
				video_id=info.get("id") if info else None,
				video_title=title if "title" in locals() else None,
				duration_seconds=duration if "duration" in locals() else None,
				chosen_bitrate=AUDIO_BITRATE_KBPS,
				estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
				real_size_mb=real_size_mb if "real_size_mb" in locals() else None,
				delivery_method="failed",
				status="failed",
				error_message=str(e),
			)

		finally:
			if "tmp_path" in locals() and tmp_path.exists():
				tmp_path.unlink()

	
	except Exception as e:
		logging.exception("Download worker failed")
		await status_msg.edit_text("❌ An error occurred during processing. Please try again later.")



# --------------------------------------------------
# Application lifecycle hooks
# --------------------------------------------------
async def post_init(application):
	for i in range(DOWNLOAD_WORKERS):
		application.create_task(download_worker(i + 1))



# --------------------------------------------------
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	user = update.effective_user
	register_user(user)

	cleanup_old_files()

	url = update.message.text.strip()

	if not re.search(r"(youtube\.com|youtu\.be)", url):
		await update.message.reply_text("❌ Please send a valid YouTube link.")
		return

	# 🔑 Status message
	status_msg = await update.message.reply_text("⏳ Queuing download task... Please wait. ")

	job = {
		"user": user,
		"url": url,
		"status_msg": status_msg,
	}

	await download_queue.put(job)



# --------------------------------------------------
# Admin /stats
# --------------------------------------------------
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		return

	total = get_total_users()
	await update.message.reply_text(
		f"📊 Stats\n\nTotal users: {total}"
	)



# --------------------------------------------------
# App bootstrap
# --------------------------------------------------
def main():
	init_db()

	app = (
		ApplicationBuilder()
		.token(BOT_TOKEN)
		.post_init(post_init)
		.build()
	)

	# for i in range(DOWNLOAD_WORKERS):
	# 	app.create_task(download_worker(i + 1))

	app.add_handler(CommandHandler("stats", stats_handler))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

	logging.info("Bot started")
	app.run_polling()



if __name__ == "__main__":
	main()
