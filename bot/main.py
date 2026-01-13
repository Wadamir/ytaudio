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
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	url = update.message.text.strip()

	if "youtube.com" not in url and "youtu.be" not in url:
		await update.message.reply_text("❌ Send a valid YouTube link")
		return

	await update.message.reply_text("⏳ Downloading audio...")

	ydl_opts = {
		"format": "bestaudio/best",
		"outtmpl": "/tmp/%(id)s.%(ext)s",
		"cookies": COOKIES_PATH,

		"js_runtimes": {
			"node": {
				"path": "/usr/bin/node"
			}
		},

		"postprocessors": [{
			"key": "FFmpegExtractAudio",
			"preferredcodec": "mp3",
			"preferredquality": "192",
		}],
		"noplaylist": True,
		"quiet": True,
	}

	try:
		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=True)

		audio_file = f"/tmp/{info['id']}.mp3"

		if not os.path.exists(audio_file):
			raise RuntimeError("Audio file was not created")

		await update.message.reply_audio(
			audio=open(audio_file, "rb"),
			title=info.get("title", "audio"),
		)

		os.remove(audio_file)

	except Exception:
		logging.exception("yt-dlp failed")
		await update.message.reply_text("❌ Failed to download audio")

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
