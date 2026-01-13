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

logging.info(f"Running in {APP_ENV.upper()} mode")

# --------------------------------------------------
# Constants
# --------------------------------------------------
MAX_TG_AUDIO_MB = 50
BITRATE_STEPS = [192, 160, 128, 96, 64]

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	return duration_sec * bitrate_kbps / 8 / 1024


def get_file_size_mb(path: str) -> float:
	return os.path.getsize(path) / 1024 / 1024


# --------------------------------------------------
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	url = update.message.text.strip()

	if "youtube.com" not in url and "youtu.be" not in url:
		await update.message.reply_text("❌ Send a valid YouTube link")
		return

	await update.message.reply_text("⏳ Checking video info...")

	# --- Metadata ---
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
		await update.message.reply_text("❌ Failed to read video info")
		return

	duration = info.get("duration")
	title = info.get("title", "audio")

	if not duration:
		await update.message.reply_text("❌ Cannot determine video duration")
		return

	audio_file = None

	# --- Try bitrates ---
	for bitrate in BITRATE_STEPS:
		estimated_mb = estimate_mp3_size_mb(duration, bitrate)

		logging.info(
			f"Trying bitrate {bitrate} kbps | "
			f"Estimated size: {estimated_mb:.1f} MB"
		)

		await update.message.reply_text(
			f"🎧 Trying {bitrate} kbps (~{estimated_mb:.1f} MB)"
		)

		ydl_opts = {
			"format": "bestaudio/best",
			"outtmpl": "/tmp/%(id)s.%(ext)s",
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

		try:
			with yt_dlp.YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(url, download=True)

			audio_file = f"/tmp/{info['id']}.mp3"

			if not os.path.exists(audio_file):
				raise RuntimeError("Audio file missing")

			real_size_mb = get_file_size_mb(audio_file)

			logging.info(
				f"Downloaded | Bitrate: {bitrate} kbps | "
				f"Real size: {real_size_mb:.2f} MB"
			)

			if real_size_mb <= MAX_TG_AUDIO_MB:
				await update.message.reply_audio(
					audio=open(audio_file, "rb"),
					title=title,
				)
				return

			# Too large → try lower bitrate
			logging.warning(
				f"Too large for Telegram ({real_size_mb:.2f} MB), "
				f"retrying lower bitrate"
			)

		except Exception:
			logging.exception("Download failed")

		finally:
			if audio_file and os.path.exists(audio_file):
				os.remove(audio_file)
				audio_file = None

	# --- All attempts failed ---
	await update.message.reply_text(
		"❌ Audio is too large even at minimum quality.\n"
		"Try a shorter video."
	)

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
