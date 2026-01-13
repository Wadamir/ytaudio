import os
import time
import uuid
import logging
import yt_dlp
from pathlib import Path

from telegram import Update
from telegram.ext import (
	ApplicationBuilder,
	MessageHandler,
	ContextTypes,
	filters,
)

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(levelname)s - %(message)s",
)

logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --------------------------------------------------
# Environment
# --------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
	raise RuntimeError("BOT_TOKEN is not set")

APP_ENV = os.getenv("APP_ENV", "prod")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

COOKIES_PATH = "/cookies.txt"
STORAGE_DIR = Path("/storage/audio")

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

logging.info(f"Running in {APP_ENV.upper()} mode")

# --------------------------------------------------
# Constants
# --------------------------------------------------
MAX_TG_AUDIO_MB = 50
MIN_BITRATE_KBPS = 64
DEFAULT_BITRATE_KBPS = 192
FILE_TTL_SECONDS = 12 * 60 * 60  # 12 hours

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	return duration_sec * bitrate_kbps / 8 / 1024


def cleanup_old_files():
	now = time.time()
	for file in STORAGE_DIR.glob("*.mp3"):
		if now - file.stat().st_mtime > FILE_TTL_SECONDS:
			try:
				file.unlink()
			except Exception:
				pass


def choose_bitrate(duration: int) -> int:
	for bitrate in (192, 128, 96, 64):
		if estimate_mp3_size_mb(duration, bitrate) <= MAX_TG_AUDIO_MB:
			return bitrate
	return MIN_BITRATE_KBPS


# --------------------------------------------------
# Handler
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	url = update.message.text.strip()

	if "youtube.com" not in url and "youtu.be" not in url:
		await update.message.reply_text("❌ Please send a valid YouTube link.")
		return

	await update.message.reply_text("⏳ Checking video info...")

	# --- Metadata only ---
	try:
		with yt_dlp.YoutubeDL({
			"quiet": True,
			"cookies": COOKIES_PATH,
			"js_runtimes": {
				"node": {"path": "/usr/bin/node"}
			},
		}) as ydl:
			info = ydl.extract_info(url, download=False)
	except Exception:
		logging.exception("Metadata extraction failed")
		await update.message.reply_text("❌ Failed to read video info.")
		return

	duration = info.get("duration")
	title = info.get("title", "audio")

	if not duration:
		await update.message.reply_text("❌ Cannot determine video duration.")
		return

	bitrate = choose_bitrate(duration)
	estimated_mb = estimate_mp3_size_mb(duration, bitrate)

	logging.info(
		f"Video: {title} | "
		f"Duration: {duration}s | "
		f"Chosen bitrate: {bitrate} kbps | "
		f"Estimated size: {estimated_mb:.1f} MB"
	)

	await update.message.reply_text("⏳ Downloading audio...")

	file_id = uuid.uuid4().hex
	outtmpl = f"/tmp/{file_id}.%(ext)s"

	ydl_opts = {
		"format": "bestaudio/best",
		"outtmpl": outtmpl,
		"cookies": COOKIES_PATH,
		"js_runtimes": {
			"node": {"path": "/usr/bin/node"}
		},
		"postprocessors": [{
			"key": "FFmpegExtractAudio",
			"preferredcodec": "mp3",
			"preferredquality": str(bitrate),
		}],
		"noplaylist": True,
		"quiet": True,
	}

	tmp_mp3 = None

	try:
		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=True)

		tmp_mp3 = Path(f"/tmp/{file_id}.mp3")

		if not tmp_mp3.exists():
			raise RuntimeError("MP3 file was not created")

		real_size_mb = tmp_mp3.stat().st_size / 1024 / 1024
		logging.info(
			f"Real size: {real_size_mb:.1f} MB | Bitrate: {bitrate} kbps"
		)

		# --- Send directly if possible ---
		if real_size_mb <= MAX_TG_AUDIO_MB:
			await update.message.reply_audio(
				audio=open(tmp_mp3, "rb"),
				title=title,
			)
			return

		# --- Fallback: store & link ---
		cleanup_old_files()

		final_path = STORAGE_DIR / f"{file_id}.mp3"
		tmp_mp3.rename(final_path)

		link = f"{BASE_URL}/audio/{final_path.name}"

		await update.message.reply_text(
			"⚠️ The audio file is too large for Telegram.\n\n"
			"Here is a download link (available for 12 hours):\n"
			f"{link}"
		)

	except Exception:
		logging.exception("Download error")
		await update.message.reply_text("❌ Failed to process this video.")

	finally:
		if tmp_mp3 and tmp_mp3.exists():
			try:
				tmp_mp3.unlink()
			except Exception:
				pass


# --------------------------------------------------
# App bootstrap
# --------------------------------------------------
def main():
	app = ApplicationBuilder().token(BOT_TOKEN).build()

	app.add_handler(
		MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
	)

	logging.info("Bot started")
	app.run_polling()


if __name__ == "__main__":
	main()
