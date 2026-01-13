import os
import logging
import yt_dlp

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

# Убираем спам getUpdates
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --------------------------------------------------
# Environment
# --------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
	raise RuntimeError("BOT_TOKEN is not set")

APP_ENV = os.getenv("APP_ENV", "prod")
COOKIES_PATH = "/cookies.txt"

logging.info(
	"Running in %s mode",
	"DEV" if APP_ENV == "dev" else "PROD"
)

# --------------------------------------------------
# Constants
# --------------------------------------------------
MAX_TG_AUDIO_MB = 50
SAFE_FACTOR = 1.5

BITRATE_STEPS = [192, 160, 128, 96, 64]

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	return duration_sec * bitrate_kbps / 8 / 1024


def real_file_size_mb(path: str) -> float:
	return os.path.getsize(path) / 1024 / 1024


def yt_common_opts():
	return {
		"cookies": COOKIES_PATH,
		"quiet": True,
		"js_runtimes": {
			"node": {
				"path": "/usr/bin/node"
			}
		},
	}


# --------------------------------------------------
# Handler
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	url = update.message.text.strip()

	if "youtube.com" not in url and "youtu.be" not in url:
		await update.message.reply_text("❌ Send a valid YouTube link")
		return

	await update.message.reply_text("⏳ Checking video info...")

	# --- metadata only ---
	try:
		with yt_dlp.YoutubeDL(yt_common_opts()) as ydl:
			info = ydl.extract_info(url, download=False)
	except Exception:
		logging.exception("Failed to extract metadata")
		await update.message.reply_text("❌ Failed to read video info")
		return

	duration = info.get("duration")
	title = info.get("title", "audio")

	if not duration:
		await update.message.reply_text("❌ Cannot determine video duration")
		return

	# --------------------------------------------------
	# Bitrate selection
	# --------------------------------------------------
	chosen_bitrate = None
	estimated_size = None

	for bitrate in BITRATE_STEPS:
		est = estimate_mp3_size_mb(duration, bitrate)

		if est > MAX_TG_AUDIO_MB * SAFE_FACTOR:
			logging.info(
				"Skip bitrate %s kbps — estimated %.1f MB (too large)",
				bitrate, est
			)
			continue

		chosen_bitrate = bitrate
		estimated_size = est
		break

	if not chosen_bitrate:
		await update.message.reply_text(
			"❌ Video is too long even at lowest quality"
		)
		return

	logging.info(
		"Video: %s | Duration: %ss | Chosen bitrate: %s kbps | Estimated size: %.1f MB",
		title, duration, chosen_bitrate, estimated_size
	)

	if estimated_size > MAX_TG_AUDIO_MB:
		await update.message.reply_text(
			f"⚠️ Audio is long.\n"
			f"Quality reduced to {chosen_bitrate} kbps to fit Telegram limits."
		)
	else:
		await update.message.reply_text("⏳ Downloading audio...")

	# --------------------------------------------------
	# Download & convert
	# --------------------------------------------------
	audio_file = None

	ydl_opts = {
		**yt_common_opts(),
		"format": "bestaudio/best",
		"outtmpl": "/tmp/%(id)s.%(ext)s",
		"noplaylist": True,
		"postprocessors": [{
			"key": "FFmpegExtractAudio",
			"preferredcodec": "mp3",
			"preferredquality": str(chosen_bitrate),
		}],
	}

	try:
		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=True)

		audio_file = f"/tmp/{info['id']}.mp3"

		if not os.path.exists(audio_file):
			raise RuntimeError("Audio file not created")

		real_size = real_file_size_mb(audio_file)

		logging.info(
			"MP3 ready | Bitrate: %s kbps | Estimated: %.1f MB | Real: %.1f MB",
			chosen_bitrate, estimated_size, real_size
		)

		await update.message.reply_audio(
			audio=open(audio_file, "rb"),
			title=title,
		)

	except Exception:
		logging.exception("yt-dlp failed")
		await update.message.reply_text(
			"❌ Failed to send audio (file may be too large)"
		)

	finally:
		if audio_file and os.path.exists(audio_file):
			os.remove(audio_file)

# --------------------------------------------------
# Bootstrap
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
