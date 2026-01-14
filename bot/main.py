import os
import uuid
import logging
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta

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
# Environment
# --------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
	raise RuntimeError("BOT_TOKEN is not set")

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
MAX_TG_AUDIO_MB = 50
MAX_STORAGE_HOURS = 12

BITRATE_LEVELS = [192, 160, 128, 96, 64]
LONG_VIDEO_SECONDS = 5400  # 1.5 hours

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	return duration_sec * bitrate_kbps / 8 / 1024


def cleanup_old_files():
	now = time.time()

	for f in STORAGE_DIR.glob("*.mp3"):
		if now - f.stat().st_mtime > MAX_STORAGE_HOURS * 3600:
			try:
				f.unlink()
			except Exception:
				logging.exception("Failed to remove old file")


def choose_bitrate(duration: int) -> int:
	for br in BITRATE_LEVELS:
		size = estimate_mp3_size_mb(duration, br)
		if size <= MAX_TG_AUDIO_MB:
			return br
	return 64


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
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	user = update.effective_user
	register_user(user)

	cleanup_old_files()

	url = update.message.text.strip()

	if "youtube.com" not in url and "youtu.be" not in url:
		await update.message.reply_text("❌ Please send a valid YouTube link.")
		return

	await update.message.reply_text("⏳ Checking video info...")

	# --- Extract metadata ---
	try:
		opts = ydl_base_opts()
		opts["skip_download"] = True

		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=False)

	except Exception as e:
		logging.exception("Metadata extraction failed")
		await update.message.reply_text("❌ Failed to read video info.")

		log_download(
			user_id=user.id,
			video_url=url,
			video_id=info.get("id") if info else None,
			video_title=title if "title" in locals() else None,
			duration_seconds=duration if "duration" in locals() else None,
			chosen_bitrate=chosen_bitrate if "chosen_bitrate" in locals() else None,
			estimated_size_mb=estimated_size if "estimated_size" in locals() else None,
			real_size_mb=None,
			delivery_method="failed",
			status="failed",
			error_message=str(e),
		)

		return

	duration = info.get("duration")
	title = info.get("title", "audio")

	if not duration:
		await update.message.reply_text("❌ Cannot determine video duration.")
		return

	chosen_bitrate = choose_bitrate(duration)
	estimated_size = estimate_mp3_size_mb(duration, chosen_bitrate)

	logging.info(
		f"Video: {title} | "
		f"Duration: {duration}s | "
		f"Chosen bitrate: {chosen_bitrate} kbps | "
		f"Estimated size: {estimated_size:.1f} MB"
	)

	# --- Very long video ---
	if duration >= LONG_VIDEO_SECONDS:
		await update.message.reply_text(
			"⚠️ This video is longer than 1.5 hours. I can create a download link instead (64 kbps).\n\n"
			"Please wait, processing may take some time."
		)

	# --- Telegram upload possible ---
	if estimated_size <= MAX_TG_AUDIO_MB:
		await update.message.reply_text(
			f"⏳ Downloading audio: {chosen_bitrate} kbps (~{estimated_size:.1f} MB)"
		)

		tmp_id = uuid.uuid4().hex
		tmp_path = Path(f"/tmp/{tmp_id}.mp3")

		opts = ydl_base_opts()
		opts.update({
			"format": "bestaudio/best",
			"outtmpl": f"/tmp/{tmp_id}.%(ext)s",
			"postprocessors": [{
				"key": "FFmpegExtractAudio",
				"preferredcodec": "mp3",
				"preferredquality": str(chosen_bitrate),
			}],
		})

		try:
			with yt_dlp.YoutubeDL(opts) as ydl:
				ydl.extract_info(url, download=True)

			real_size = tmp_path.stat().st_size / 1024 / 1024
			logging.info(f"Real size: {real_size:.1f} MB | Bitrate: {chosen_bitrate} kbps")

			await update.message.reply_audio(
				audio=open(tmp_path, "rb"),
				title=title,
			)
			
			increment_downloads(user.id)
			log_download(
				user_id=user.id,
				video_url=url,
				video_id=info.get("id"),
				video_title=title,
				duration_seconds=duration,
				chosen_bitrate=chosen_bitrate,
				estimated_size_mb=estimated_size,
				real_size_mb=real_size,
				delivery_method="telegram",
				status="success",
			)

		except Exception as e:
			logging.exception("Telegram upload failed")
			await update.message.reply_text("❌ Failed to send audio.")

			log_download(
				user_id=user.id,
				video_url=url,
				video_id=info.get("id") if info else None,
				video_title=title if "title" in locals() else None,
				duration_seconds=duration if "duration" in locals() else None,
				chosen_bitrate=chosen_bitrate if "chosen_bitrate" in locals() else None,
				estimated_size_mb=estimated_size if "estimated_size" in locals() else None,
				real_size_mb=None,
				delivery_method="failed",
				status="failed",
				error_message=str(e),
			)

		finally:
			if tmp_path.exists():
				tmp_path.unlink()

		return

	# --- Fallback: download link (always 64 kbps) ---
	if duration < LONG_VIDEO_SECONDS:
		await update.message.reply_text(
			"⚠️ This video is too large for Telegram upload. I can create a download link instead (64 kbps).\n\n"
			"Please wait, processing may take some time."
		)

	file_id = uuid.uuid4().hex
	final_path = STORAGE_DIR / f"{file_id}.mp3"

	opts = ydl_base_opts()
	opts.update({
		"format": "bestaudio/best",
		"outtmpl": f"/tmp/{file_id}.%(ext)s",
		"postprocessors": [{
			"key": "FFmpegExtractAudio",
			"preferredcodec": "mp3",
			"preferredquality": "64",
		}],
	})

	try:
		with yt_dlp.YoutubeDL(opts) as ydl:
			ydl.extract_info(url, download=True)

		tmp_mp3 = Path(f"/tmp/{file_id}.mp3")
		shutil.move(str(tmp_mp3), str(final_path))

		size_mb = final_path.stat().st_size / 1024 / 1024
		logging.info(
			f"File saved: {final_path.name} | "
			f"Real size: {size_mb:.1f} MB | Bitrate: 64 kbps"
		)

		link = f"{BASE_URL}/audio/{final_path.name}"

		await update.message.reply_text(
			"✅ Your audio is ready:\n"
			f"{link}\n\n"
			"⏰ The file will be available for 12 hours."
		)

		increment_downloads(user.id)
		log_download(
			user_id=user.id,
			video_url=url,
			video_id=info.get("id"),
			video_title=title,
			duration_seconds=duration,
			chosen_bitrate=64,
			estimated_size_mb=estimated_size,
			real_size_mb=size_mb,
			delivery_method="link",
			status="success",
			file_path=str(final_path),
			download_url=link,
			fallback_reason="too_large",
		)

	except Exception as e:
		logging.exception("Download link generation failed")
		await update.message.reply_text("❌ Failed to create download link.")

		log_download(
			user_id=user.id,
			video_url=url,
			video_id=info.get("id") if info else None,
			video_title=title if "title" in locals() else None,
			duration_seconds=duration if "duration" in locals() else None,
			chosen_bitrate=chosen_bitrate if "chosen_bitrate" in locals() else None,
			estimated_size_mb=estimated_size if "estimated_size" in locals() else None,
			real_size_mb=None,
			delivery_method="failed",
			status="failed",
			error_message=str(e),
		)


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

	app = ApplicationBuilder().token(BOT_TOKEN).build()

	app.add_handler(CommandHandler("stats", stats_handler))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

	logging.info("Bot started")
	app.run_polling()


if __name__ == "__main__":
	main()
