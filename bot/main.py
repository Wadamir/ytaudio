import os
import math
import logging
import subprocess
import yt_dlp

from telegram import (
	Update,
	InlineKeyboardButton,
	InlineKeyboardMarkup,
)
from telegram.ext import (
	ApplicationBuilder,
	MessageHandler,
	CallbackQueryHandler,
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

logging.info("Running in %s mode", APP_ENV.upper())

# --------------------------------------------------
# Constants
# --------------------------------------------------
MAX_TG_AUDIO_MB = 50
SAFE_FACTOR = 1.5
MAX_SPLIT_PARTS = 3

BITRATE_STEPS = [192, 160, 128, 96, 64]

# --------------------------------------------------
# In-memory pending splits (simple & safe)
# --------------------------------------------------
PENDING_SPLITS = {}

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
	return duration_sec * bitrate_kbps / 8 / 1024


def real_size_mb(path: str) -> float:
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


def split_mp3(input_path: str, parts: int, duration: int) -> list[str]:
	part_duration = math.ceil(duration / parts)
	output_files = []

	for i in range(parts):
		out = f"{input_path}.part{i+1}.mp3"
		cmd = [
			"ffmpeg",
			"-y",
			"-i", input_path,
			"-ss", str(i * part_duration),
			"-t", str(part_duration),
			"-c", "copy",
			out
		]
		subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		output_files.append(out)

	return output_files


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

	# --- metadata ---
	try:
		with yt_dlp.YoutubeDL(yt_common_opts()) as ydl:
			info = ydl.extract_info(url, download=False)
	except Exception:
		logging.exception("Metadata error")
		await update.message.reply_text("❌ Failed to read video info")
		return

	duration = info.get("duration")
	title = info.get("title", "audio")

	if not duration:
		await update.message.reply_text("❌ Cannot determine duration")
		return

	# --- bitrate selection ---
	chosen_bitrate = None
	estimated_size = None

	for br in BITRATE_STEPS:
		est = estimate_mp3_size_mb(duration, br)
		if est > MAX_TG_AUDIO_MB * SAFE_FACTOR:
			continue
		chosen_bitrate = br
		estimated_size = est
		break

	if not chosen_bitrate:
		await update.message.reply_text("❌ Video is too long")
		return

	logging.info(
		"Video: %s | Duration: %ss | Bitrate: %s kbps | Est: %.1f MB",
		title, duration, chosen_bitrate, estimated_size
	)

	await update.message.reply_text("⏳ Downloading audio...")

	# --- download ---
	audio_file = None
	try:
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

		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=True)

		audio_file = f"/tmp/{info['id']}.mp3"
		size_mb = real_size_mb(audio_file)

		logging.info(
			"Real size: %.1f MB | Bitrate: %s kbps",
			size_mb, chosen_bitrate
		)

		# --- fits ---
		if size_mb <= MAX_TG_AUDIO_MB:
			await update.message.reply_audio(
				audio=open(audio_file, "rb"),
				title=title,
			)
			return

		# --- split decision ---
		parts = math.ceil(size_mb / MAX_TG_AUDIO_MB)

		if parts > MAX_SPLIT_PARTS:
			await update.message.reply_text(
				"❌ Audio is too large even when split.\n"
				"I can only split into max 3 parts."
			)
			return

		PENDING_SPLITS[update.effective_user.id] = {
			"file": audio_file,
			"title": title,
			"duration": duration,
			"parts": parts,
		}

		keyboard = InlineKeyboardMarkup([
			[
				InlineKeyboardButton("✂️ Split", callback_data="split_yes"),
				InlineKeyboardButton("❌ Cancel", callback_data="split_no"),
			]
		])

		await update.message.reply_text(
			f"⚠️ Audio is too large ({size_mb:.1f} MB).\n\n"
			f"It will be split into {parts} parts.\n"
			f"Quality: {chosen_bitrate} kbps.\n\n"
			f"Proceed?",
			reply_markup=keyboard,
		)

	except Exception:
		logging.exception("Download error")
		await update.message.reply_text("❌ Failed to process audio")

# --------------------------------------------------
# Split confirmation
# --------------------------------------------------
async def handle_split_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	user_id = query.from_user.id
	data = PENDING_SPLITS.pop(user_id, None)

	if not data:
		await query.edit_message_text("❌ Nothing to split")
		return

	if query.data == "split_no":
		os.remove(data["file"])
		await query.edit_message_text("❌ Cancelled")
		return

	parts = split_mp3(
		data["file"],
		data["parts"],
		data["duration"]
	)

	for idx, part in enumerate(parts, 1):
		await query.message.reply_audio(
			audio=open(part, "rb"),
			title=f"{data['title']} (Part {idx}/{len(parts)})",
		)
		os.remove(part)

	os.remove(data["file"])
	await query.edit_message_text("✅ Done")

# --------------------------------------------------
# Bootstrap
# --------------------------------------------------
def main():
	app = ApplicationBuilder().token(BOT_TOKEN).build()

	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
	app.add_handler(CallbackQueryHandler(handle_split_callback))

	logging.info("Bot started")
	app.run_polling()


if __name__ == "__main__":
	main()
