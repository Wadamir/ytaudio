import os
import uuid
import logging
import time
import shutil
import re
import asyncio
import random
import logging
import sqlite3
import aiohttp
import logging

from PIL import Image
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime, timedelta, timezone

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
	can_user_download,
	
	#--- Stats ---
	get_total_users,
	get_total_new_users_today,
	get_total_users_week,
	get_top_users,

	get_total_downloads,
	get_total_downloads_today,
	get_total_downloads_week,
	get_downloads_by_delivery_methods,
	get_failure_rate,

	get_avg_processing_time,
	get_latency_stats,

	get_total_youtube_errors,
	get_total_youtube_errors_today,
	get_youtube_errors_by_type,
	get_failed_downloads_last_24h,
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
YTDLP_MAX_RETRIES = 3			# total attempts

YTDLP_BACKOFF_BASE = 5        	# starting delay
YTDLP_BACKOFF_MULTIPLIER = 3	# exponential factor
YTDLP_BACKOFF_MAX = 60        	# max delay

YTDLP_NOTIFY_THRESHOLD = 5		# notify admin on errors
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

ASSETS_DIR = Path(__file__).parent / "assets"
TMP_DIR = Path("/tmp/ytaudio_thumbs")
TMP_DIR.mkdir(parents=True, exist_ok=True)
PLACEHOLDER_THUMBNAIL = ASSETS_DIR / "youtube_placeholder.jpg"

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


def extract_http_error_code(error: Exception) -> str | None:
	msg = str(error)

	if "403" in msg:
		return "403"
	if "429" in msg:
		return "429"
	if "404" in msg:
		return "404"
	if "500" in msg:
		return "500"

	return None


def can_use_fast_path(info: dict, max_size_mb: float) -> bool:
	for f in info.get("formats", []):
		if f.get("ext") != "m4a":
			continue
		if f.get("acodec") != "mp4a.40.2":
			continue

		size = f.get("filesize") or f.get("filesize_approx")
		if size and (size / 1024 / 1024) <= max_size_mb:
			return True

	return False


def fmt_int(value: Optional[float | int]) -> str:
	if value is None:
		return "—"
	return f"{int(value):,}".replace(",", " ")


def time_until_utc_reset() -> str:
	now = datetime.now(timezone.utc)
	tomorrow = (now + timedelta(days=1)).date()
	reset_at = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)

	delta = reset_at - now
	total_seconds = int(delta.total_seconds())

	hours, remainder = divmod(total_seconds, 3600)
	minutes = remainder // 60

	if hours > 0:
		return f"{hours}h {minutes}m"
	return f"{minutes}m"


async def global_error_handler(update, context):
	error = context.error
	logging.exception("Unhandled exception", exc_info=error)

	try:
		await context.bot.send_message(
			chat_id=ADMIN_USER_ID,
			text=(
				"🚨 <b>Unhandled exception</b>\n\n"
				f"<code>{str(error)[:400]}</code>"
			),
			parse_mode="HTML",
		)
	except Exception:
		pass


async def get_audio_thumbnail(
	thumb_url: Optional[str],
	video_id: Optional[str],
) -> Optional[BinaryIO]:
	"""
	Returns an opened file object for Telegram audio thumbnail.
	Always falls back to placeholder if thumbnail is invalid.
	"""

	# 1️⃣ Try YouTube thumbnail
	if thumb_url and video_id:
		tmp_path = TMP_DIR / f"{video_id}.jpg"

		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(thumb_url, timeout=10) as resp:
					if resp.status == 200:
						tmp_path.write_bytes(await resp.read())

			# Validate image via Pillow
			if tmp_path.exists():
				try:
					with Image.open(tmp_path) as img:
						img.verify()  # validate file
					return open(tmp_path, "rb")
				except Exception:
					logging.warning("Downloaded thumbnail is not a valid image")

		except Exception as e:
			logging.warning(f"Thumbnail download failed: {e}")

	# 2️⃣ Fallback
	if PLACEHOLDER_THUMBNAIL.exists():
		return open(PLACEHOLDER_THUMBNAIL, "rb")

	return None



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


def ydl_fast_audio_opts(tmp_id: str):
	return {
		**ydl_base_opts(),
		"format": "bestaudio[ext=m4a]/bestaudio",
		"outtmpl": f"/tmp/{tmp_id}.%(ext)s",
		"postprocessors": [], 						# ❌ no audio postprocessors
	}


def ydl_slow_audio_opts(tmp_id: str, title: str, uploader: str):
	return {
		**ydl_base_opts(),
		"format": "bestaudio/best",
		"outtmpl": f"/tmp/{tmp_id}.%(ext)s",
		"postprocessors": [
			{
				"key": "FFmpegExtractAudio",
				"preferredcodec": "aac",
				"preferredquality": str(AUDIO_BITRATE_KBPS),
			},
			{
				"key": "FFmpegMetadata",
			},
		],
		"postprocessor_args": [
			"-metadata", f"title={title}",
			"-metadata", f"artist={uploader}",
			"-metadata", "album=YouTube",
			"-metadata", f"comment={BOT_CAPTION} {BOT_USERNAME}",
			"-metadata", f"encoded_by={BOT_USERNAME}",
		],
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


def calc_backoff_with_jitter(attempt: int) -> int:
	max_delay = YTDLP_BACKOFF_BASE * (YTDLP_BACKOFF_MULTIPLIER ** (attempt - 1))
	max_delay = min(max_delay, YTDLP_BACKOFF_MAX)

	# Full jitter: random delay from 0 to max_delay
	return random.randint(0, max_delay)


async def ytdlp_download_with_retry(
	url: str,
	opts: dict,
	video_id: str | None,
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
			error_code = extract_http_error_code(e)

			# --- retry only for temporary errors ---
			if error_code in ("403", "429"):
				delay = calc_backoff_with_jitter(attempt)

				logging.warning(
					f"YouTube HTTP {error_code} | "
					f"attempt {attempt}/{YTDLP_MAX_RETRIES} | "
					f"retry in {delay}s"
				)

				# --- log REAL error code ---
				from db import log_youtube_error, count_today_youtube_errors
				log_youtube_error(error_code, url, video_id)

				# --- notify admin once per threshold ---
				count = count_today_youtube_errors(error_code)
				if count == YTDLP_NOTIFY_THRESHOLD:
					await application.bot.send_message(
						chat_id=ADMIN_USER_ID,
						text=(
							"⚠️ <b>YouTube temporary errors detected</b>\n\n"
							f"HTTP {error_code} errors today: {count}\n"
							"YouTube may be throttling downloads."
						),
						parse_mode="HTML",
					)

				if attempt < YTDLP_MAX_RETRIES:
					if delay > 0:
						await asyncio.sleep(delay)
					continue

			# --- fatal or retries exhausted ---
			raise

	raise last_error


async def process_job(job: dict):
	processing_mode: Optional[str] = None
	start_ts = time.monotonic()

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

			try:
				log_download(
					user_id=user.id,

					video_url=url,
					video_id=None,
					video_title=None,

					duration_seconds=None,

					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=None,
					real_size_mb=None,

					processing_mode=processing_mode,
					processing_time_ms=int((time.monotonic() - start_ts) * 1000),

					delivery_method="failed",

					status="failed",

					error_message=str(e),
					fallback_reason="metadata_extraction_failed",
				)
			except sqlite3.OperationalError as db_e:
				await notify_admin_once(
					application,
					key="sqlite_operational_error",
					text=f"Database error during logging: {str(db_e)[:400]}",
				)
				raise

			return

		title = info.get("title", "audio")
		duration = info.get("duration", 0)


		# -- Validate duration ---
		if not duration:
			logging.warning("Video duration unknown")
			await status_msg.edit_text("❌ Cannot determine video duration.")

			try:
				log_download(
					user_id=user.id,

					video_url=url,
					video_id=info.get("id") if info else None,
					video_title=title if "title" in locals() else None,

					duration_seconds=duration if "duration" in locals() else None,

					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size if "estimated_size" in locals() else None,
					real_size_mb=None,

					processing_mode=processing_mode,
					processing_time_ms=int((time.monotonic() - start_ts) * 1000),

					delivery_method="failed",

					status="failed",

					error_message="Unknown video duration",
					fallback_reason="unknown_duration",
				)
			except sqlite3.OperationalError as db_e:
				await notify_admin_once(
					application,
					key="sqlite_operational_error",
					text=f"Database error during logging: {str(db_e)[:400]}",
				)
				raise

			return


		estimated_size = estimate_audio_size_mb(duration, AUDIO_BITRATE_KBPS)
		estimated_size_mb = round(estimated_size, 2)

		logging.info(
			f"Video: {title} | "
			f"Duration: {duration}s | "
			f"Estimated size: {estimated_size_mb:.1f} MB"
		)


		warning_line = "\n\n⏰ Please be patient."
		if duration >= LONG_WARNING_SECONDS:
			warning_line = "\n\n⏰ This is a long video. Please be patient."

		elif estimated_size >= BIG_WARNING_MB:
			warning_line = "\n\n⏰ This is a large audio file. Please be patient."

		# if estimated_size <= MAX_TG_AUDIO_EFFECTIVE_MB:
		# 	await status_msg.edit_text(f"⬇️ Downloading audio ≈ {estimated_size_mb:.1f} MB{warning_line}")		

		tmp_id = uuid.uuid4().hex
		tmp_dir = Path("/tmp")

		use_fast_path = can_use_fast_path(info, MAX_TG_AUDIO_EFFECTIVE_MB)

		if use_fast_path:
			processing_mode = "fast"
			await status_msg.edit_text("⚡ Downloading audio (fast mode)")
			opts = ydl_fast_audio_opts(tmp_id)
		else:
			processing_mode = "slow"
			await status_msg.edit_text(f"⬇️ Downloading audio (re-encoding) {estimated_size_mb:.1f} MB{warning_line}")
			opts = ydl_slow_audio_opts(tmp_id, title, info.get("uploader", ""))


		# --- Download audio ---
		try:
			await ytdlp_download_with_retry(
				url=url,
				opts=opts,
				video_id=info.get("id"),
				application=application,
			)

			files = list(tmp_dir.glob(f"{tmp_id}.*"))
			if not files:
				raise RuntimeError("Downloaded audio file not found")
			
			tmp_path = files[0]

			real_size_mb = round(tmp_path.stat().st_size / 1024 / 1024, 2)
			logging.info(f"Real size: {real_size_mb:.1f} MB")

		except Exception as e:
			logging.exception("Audio download failed")
			await status_msg.edit_text("❌ Failed to download audio.")

			try:
				log_download(
					user_id=user.id,

					video_url=url,
					video_id=info.get("id") if info else None,
					video_title=title if "title" in locals() else None,

					duration_seconds=duration if "duration" in locals() else None,

					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
					real_size_mb=None,

					processing_mode=processing_mode,
					processing_time_ms=int((time.monotonic() - start_ts) * 1000),

					delivery_method="failed",

					status="failed",

					error_message=str(e),
					fallback_reason="download_failed",
				)
			except sqlite3.OperationalError as db_e:
				await notify_admin_once(
					application,
					key="sqlite_operational_error",
					text=f"Database error during logging: {str(db_e)[:400]}",
				)
				raise

			return	

		# --- Telegram upload possible ---
		if real_size_mb <= MAX_TG_AUDIO_EFFECTIVE_MB:
			try:
				# # 1. Try YouTube thumbnail
				# thumb_msg = None
				# thumb_url = info.get("thumbnail")
				# if thumb_url:
				# 	try:
				# 		# --- Send thumbnail ---
				# 		thumb_msg = await status_msg.reply_photo(photo=thumb_url)
				# 	except Exception as e:
				# 		logging.warning(f"Failed to send thumbnail: {e}")

				# # 2. Fallback to local placeholder
				# if not thumb_msg and PLACEHOLDER_THUMBNAIL.exists():
				# 	try:
				# 		with open(PLACEHOLDER_THUMBNAIL, "rb") as f:
				# 			thumb_msg = await status_msg.reply_photo(photo=f)
				# 	except Exception as e:
				# 		logging.warning(f"Placeholder thumbnail failed: {e}")

				thumb_file = await get_audio_thumbnail(
					thumb_url=info.get("thumbnail"),
					video_id=info.get("id"),
				)

				# --- Send audio ---
				with open(tmp_path, "rb") as f:
					await status_msg.reply_audio(
						audio=f,
						title=title,
						performer=info.get("uploader"),
						duration=duration,
						filename=build_audio_filename(info),
						thumb=thumb_file,
						caption=f"{BOT_CAPTION} <b>{BOT_USERNAME}</b>",
						parse_mode="HTML",
						reply_to_message_id=thumb_msg.message_id if thumb_msg else None,
					)

				# --- Cleanup ---
				if thumb_file:
					thumb_file.close()

				try:
					await status_msg.delete()
				except Exception:
					logging.warning("Failed to delete status message after upload")
					pass

				increment_downloads(user.id)

				try:
					log_download(
						user_id=user.id,

						video_url=url,
						video_id=info.get("id"),
						video_title=title,

						duration_seconds=duration,

						chosen_bitrate=AUDIO_BITRATE_KBPS,
						estimated_size_mb=estimated_size_mb,
						real_size_mb=real_size_mb,

						processing_mode=processing_mode,
						processing_time_ms=int((time.monotonic() - start_ts) * 1000),

						delivery_method="telegram",

						status="success",
					)
				except sqlite3.OperationalError as db_e:
					await notify_admin_once(
						application,
						key="sqlite_operational_error",
						text=f"Database error during logging: {str(db_e)[:400]}",
					)
					raise

			except Exception as e:
				logging.exception("Telegram upload failed")

				try:
					await status_msg.edit_text("❌ Failed to send audio.")
				except Exception:
					logging.warning("Failed to edit status message after upload failure")
					pass

				try:
					log_download(
						user_id=user.id,

						video_url=url,
						video_id=info.get("id") if info else None,
						video_title=title if "title" in locals() else None,

						duration_seconds=duration if "duration" in locals() else None,

						chosen_bitrate=AUDIO_BITRATE_KBPS,
						estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
						real_size_mb=real_size_mb if "real_size_mb" in locals() else None,

						processing_mode=processing_mode,
						processing_time_ms=int((time.monotonic() - start_ts) * 1000),

						delivery_method="failed",

						status="failed",

						error_message=str(e),
						fallback_reason="telegram_upload_failed",
					)	
				except sqlite3.OperationalError as db_e:
					await notify_admin_once(
						application,
						key="sqlite_operational_error",
						text=f"Database error during logging: {str(db_e)[:400]}",
					)
					raise

			finally:
				if "tmp_path" in locals() and tmp_path.exists():
					tmp_path.unlink()
				
			return
		

		# --- Create download link ---
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

		# --- Move file to storage ---
		final_path = STORAGE_DIR / f"{tmp_id}.{AUDIO_CONTAINER}"
		try:
			shutil.move(str(tmp_path), str(final_path))

			link = f"{BASE_URL}/audio/{final_path.name}"
			filename_download = build_audio_filename(info)

			logging.info(
				f"File saved: {final_path.name} | "
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
			try:
				log_download(
					user_id=user.id,

					video_url=url,
					video_id=info.get("id"),
					video_title=title,

					duration_seconds=duration,

					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size_mb,
					real_size_mb=real_size_mb,

					processing_mode=processing_mode,
					processing_time_ms=int((time.monotonic() - start_ts) * 1000),

					delivery_method="link",

					status="success",

					file_path=str(final_path),
					download_url=link
				)
			except sqlite3.OperationalError as db_e:
				await notify_admin_once(
					application,
					key="sqlite_operational_error",
					text=f"Database error during logging: {str(db_e)[:400]}",
				)
				raise

		except Exception as e:
			logging.exception("Download link generation failed")
			await status_msg.edit_text("❌ Failed to create download link.")

			try:
				log_download(
					user_id=user.id,

					video_url=url,
					video_id=info.get("id") if info else None,
					video_title=title if "title" in locals() else None,

					duration_seconds=duration if "duration" in locals() else None,

					chosen_bitrate=AUDIO_BITRATE_KBPS,
					estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
					real_size_mb=real_size_mb if "real_size_mb" in locals() else None,

					processing_mode=processing_mode,
					processing_time_ms=int((time.monotonic() - start_ts) * 1000),

					delivery_method="failed",

					status="failed",

					error_message=str(e),
					fallback_reason="link_generation_failed",
				)
			except sqlite3.OperationalError as db_e:
				await notify_admin_once(
					application,
					key="sqlite_operational_error",
					text=f"Database error during logging: {str(db_e)[:400]}",
				)
				raise

		finally:
			if "tmp_path" in locals() and tmp_path.exists():
				tmp_path.unlink()

	
	except Exception as e:
		logging.exception("Download worker failed")
		await status_msg.edit_text("❌ An error occurred during processing. Please try again later.")

		try:
			log_download(
				user_id=user.id,

				video_url=url,
				video_id=info.get("id") if info else None,
				video_title=title if "title" in locals() else None,

				duration_seconds=duration if "duration" in locals() else None,

				chosen_bitrate=AUDIO_BITRATE_KBPS,
				estimated_size_mb=estimated_size_mb if "estimated_size_mb" in locals() else None,
				real_size_mb=real_size_mb if "real_size_mb" in locals() else None,

				processing_mode=processing_mode,
				processing_time_ms=int((time.monotonic() - start_ts) * 1000),

				delivery_method="failed",

				status="failed",

				error_message=str(e),
				fallback_reason="worker_failed",
			)
		except sqlite3.OperationalError as db_e:
			await notify_admin_once(
				application,
				key="sqlite_operational_error",
				text=f"Database error during logging: {str(db_e)[:400]}",
			)
			raise



# --------------------------------------------------
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	user = update.effective_user
	register_user(user)

	cleanup_old_files()

	allowed, used, limit, plan = can_user_download(user.id)
	if not allowed:
		reset_in = time_until_utc_reset()
		
		await update.message.reply_text(
			(
				"🚫 <b>Daily limit reached</b>\n\n"
				f"Plan: <b>{plan}</b>\n"
				f"Used today: <b>{used} / {limit}</b>\n\n"
				f"⏰ Limit resets in <b>{reset_in}</b>\n\n"
				f"✨ Upgrade your plan to increase daily limits."
			),
			parse_mode="HTML",
		)
		return	

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
		"application": context.application,
	}

	await download_queue.put(job)



# --------------------------------------------------
# Monetization /plan
# --------------------------------------------------
async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	allowed, used, limit, plan = can_user_download(user.id)
	reset_in = time_until_utc_reset()

	plan_name = plan.capitalize()

	lines = []
	lines.append("📦 <b>Your plan</b>\n")
	lines.append(f"• Plan: <b>{plan_name}</b>")
	lines.append(f"• Daily limit: <b>{limit}</b>")
	lines.append(f"• Used today: <b>{used} / {limit}</b>")
	lines.append(f"• Reset in: <b>{reset_in}</b>")

	if not allowed:
		lines.append("\n🚫 <b>Daily limit reached</b>")

	lines.append("\n✨ Upgrade your plan to increase limits.")

	await update.message.reply_text(
		"\n".join(lines),
		parse_mode="HTML",
		disable_web_page_preview=True,
	)



# --------------------------------------------------
# Admin /stats
# --------------------------------------------------
def build_admin_stats_text() -> str:
	# --- Users ---
	total_users = get_total_users()
	new_today = get_total_new_users_today()
	new_week = get_total_users_week()
	top_users = get_top_users(5)

	# --- Downloads ---
	total_dl = get_total_downloads(success_only=True)
	dl_today = get_total_downloads_today()
	dl_week = get_total_downloads_week()
	by_delivery = get_downloads_by_delivery_methods()
	failure_rate = get_failure_rate()

	# --- Performance ---
	avg_latency = get_avg_processing_time()
	latency_by_mode = get_latency_stats()

	# --- Errors ---
	total_errors = get_total_youtube_errors()
	errors_today = get_total_youtube_errors_today()
	errors_by_type = get_youtube_errors_by_type()
	errors_downloads = get_failed_downloads_last_24h()

	# --------------------------------------------------
	# Formatting
	# --------------------------------------------------
	lines = []

	lines.append("📊 <b>YT Audio Bot – Admin Stats</b>\n")

	# 👥 Users
	lines.append("👥 <b>Users</b>")
	lines.append(f"• Total: <b>{total_users}</b>")
	lines.append(f"• New today: <b>{new_today}</b>")
	lines.append(f"• New 7d: <b>{new_week}</b>")

	if top_users:
		lines.append("• Top users:")
		for u in top_users:
			name = u["username"] or u["first_name"] or str(u["user_id"])
			lines.append(f"  – {name}: {u['downloads_count']}")
	lines.append("")

	# 📥 Downloads
	lines.append("📥 <b>Downloads</b>")
	lines.append(f"• Total (success): <b>{total_dl}</b>")
	lines.append(f"• Today: <b>{dl_today}</b>")
	lines.append(f"• 7d: <b>{dl_week}</b>")

	for k, v in by_delivery.items():
		lines.append(f"• {k}: {v}")

	if failure_rate is not None:
		if failure_rate < 5:
			icon = "🟢"
		elif failure_rate < 10:
			icon = "🟡"
		else:
			icon = "🔴"
		lines.append(
			f"• Failure rate: {icon} <b>{failure_rate:.2f}%</b>"
		)
	lines.append("")

	# ⚡ Performance
	lines.append("⚡ <b>Performance</b>")
	if avg_latency:
		lines.append(
			f"• Avg latency: <b>{fmt_int(avg_latency)} ms</b>"
		)

	for mode, data in latency_by_mode.items():
		mode_label = mode or "unknown"
		lines.append(
			f"• {mode_label}: {fmt_int(data['count'])} | "
			f"avg {fmt_int(data['avg_processing_time_ms'])} ms"
		)
	lines.append("")

	# 🚨 Errors
	lines.append("🚨 <b>YouTube Errors</b>")
	lines.append(f"• Total: <b>{total_errors}</b>")
	lines.append(f"• Today: <b>{errors_today}</b>")
	for etype, cnt in sorted(errors_by_type.items()):
		lines.append(f"• HTTP {etype}: {cnt}")
	if errors_downloads:
		lines.append("• Failed downloads last 24h:")
		for e in errors_downloads[:5]:
			lines.append(f"• {e['count']} x {e['error'][:80]}")
	else:
		lines.append("")
		lines.append("✅ <b>No errors in last 24h</b>")

	return "\n".join(lines)


async def daily_admin_report(application):
	while True:
		now = datetime.now(timezone.utc)

		next_midnight = (
			now.replace(hour=0, minute=0, second=0, microsecond=0)
			+ timedelta(days=1)
		)

		sleep_seconds = (next_midnight - now).total_seconds()
		# sleep_seconds = 100  # for testing

		logging.info(
			f"Daily report scheduled in {int(sleep_seconds)}s "
			f"(at {next_midnight.isoformat()})"
		)

		await asyncio.sleep(sleep_seconds)

		try:
			text = (
				"🕛 <b>Daily report (UTC)</b>\n\n"
				+ build_admin_stats_text()
			)

			await application.bot.send_message(
				chat_id=ADMIN_USER_ID,
				text=text,
				parse_mode="HTML",
				disable_web_page_preview=True,
			)

			logging.info("Daily admin report sent")

		except Exception:
			logging.exception("Failed to send daily admin report")

		# next runs strictly every 24h
		await asyncio.sleep(24 * 3600)


async def notify_admin_once(application, key: str, text: str):
	cache = application.bot_data.setdefault("error_cache", set())
	if key in cache:
		return
	cache.add(key)

	await application.bot.send_message(
		chat_id=ADMIN_USER_ID,
		text=f"🚨 <b>Critical error</b>\n\n{text}",
		parse_mode="HTML"
	)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		return

	await update.message.reply_text(
		build_admin_stats_text(),
		parse_mode="HTML",
		disable_web_page_preview=True,
	)



# --------------------------------------------------
# Application lifecycle hooks
# --------------------------------------------------
async def post_init(application):
	for i in range(DOWNLOAD_WORKERS):
		asyncio.create_task(download_worker(i + 1))

	asyncio.create_task(daily_admin_report(application))



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

	app.add_error_handler(global_error_handler)

	# for i in range(DOWNLOAD_WORKERS):
	# 	app.create_task(download_worker(i + 1))

	app.add_handler(CommandHandler("stats", stats_handler))
	app.add_handler(CommandHandler("plan", plan_handler))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

	logging.info("Bot started")
	app.run_polling()



if __name__ == "__main__":
	main()
