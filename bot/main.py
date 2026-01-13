import os
import uuid
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
COOKIES_PATH = "/cookies.txt"

if APP_ENV == "dev":
    logging.info("Running in DEV mode")
else:
    logging.info("Running in PROD mode")

# --------------------------------------------------
# Constants
# --------------------------------------------------
MAX_TG_AUDIO_MB = 50
FILE_TTL_HOURS = 12

BITRATE_CANDIDATES = [192, 128, 96, 64]

STORAGE_DIR = "/storage/audio"
PUBLIC_BASE_URL = "http://45.9.43.184:8080/audio"

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def estimate_mp3_size_mb(duration_sec: int, bitrate_kbps: int) -> float:
    return duration_sec * bitrate_kbps / 8 / 1024


def choose_bitrate(duration: int) -> int:
    for bitrate in BITRATE_CANDIDATES:
        est = estimate_mp3_size_mb(duration, bitrate)
        if est <= MAX_TG_AUDIO_MB:
            return bitrate
    return BITRATE_CANDIDATES[-1]


def get_real_size_mb(path: str) -> float:
    return os.path.getsize(path) / 1024 / 1024


# --------------------------------------------------
# Handlers
# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Please send a valid YouTube link.")
        return

    await update.message.reply_text("⏳ Checking video information...")

    # --- Step 1: metadata only ---
    try:
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "cookies": COOKIES_PATH,
            "js_runtimes": {
                "node": {
                    "path": "/usr/bin/node"
                }
            },
        }) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        logging.exception("Failed to extract metadata")
        await update.message.reply_text("❌ Failed to read video information.")
        return

    duration = info.get("duration")
    title = info.get("title", "audio")

    if not duration:
        await update.message.reply_text("❌ Unable to determine video duration.")
        return

    bitrate = choose_bitrate(duration)
    estimated_size = estimate_mp3_size_mb(duration, bitrate)

    logging.info(
        f"Video: {title} | "
        f"Duration: {duration}s | "
        f"Chosen bitrate: {bitrate} kbps | "
        f"Estimated size: {estimated_size:.1f} MB"
    )

    await update.message.reply_text(
        f"🎵 Audio will be converted to {bitrate} kbps.\n"
        f"Estimated size: {estimated_size:.1f} MB."
    )

    # --- Step 2: download & convert ---
    file_id = uuid.uuid4().hex
    tmp_template = f"/tmp/{file_id}.%(ext)s"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": tmp_template,
        "cookies": COOKIES_PATH,
        "js_runtimes": {
            "node": {
                "path": "/usr/bin/node"
            }
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(bitrate),
        }],
        "noplaylist": True,
        "quiet": True,
    }

    audio_tmp_path = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        audio_tmp_path = f"/tmp/{info['id']}.mp3"

        if not os.path.exists(audio_tmp_path):
            raise RuntimeError("Audio file was not created")

        real_size = get_real_size_mb(audio_tmp_path)

        logging.info(
            f"Real size: {real_size:.1f} MB | Bitrate: {bitrate} kbps"
        )

        # --- Telegram upload ---
        if real_size <= MAX_TG_AUDIO_MB:
            await update.message.reply_audio(
                audio=open(audio_tmp_path, "rb"),
                title=title,
            )
            return

        # --- Fallback: link ---
        os.makedirs(STORAGE_DIR, exist_ok=True)
        final_name = f"{file_id}.mp3"
        final_path = os.path.join(STORAGE_DIR, final_name)

        os.rename(audio_tmp_path, final_path)

        link = f"{PUBLIC_BASE_URL}/{final_name}"

        await update.message.reply_text(
            "⚠️ The audio file is too large for Telegram.\n\n"
            "Here is a download link (available for 12 hours):\n"
            f"{link}"
        )

    except Exception:
        logging.exception("Download error")
        await update.message.reply_text("❌ Failed to process this video.")

    finally:
        if audio_tmp_path and os.path.exists(audio_tmp_path):
            os.remove(audio_tmp_path)


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
