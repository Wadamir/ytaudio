import os
from pathlib import Path

# Audio / yt-dlp settings
AUDIO_FORMAT_PREFERRED = "m4a"
AUDIO_BITRATE_PREFERRED = 64
AUDIO_BITRATE_PREFERRED_ARG = f"{AUDIO_BITRATE_PREFERRED}k"

MAX_FILENAME_LENGTH = 150

# yt-dlp behavior
YTDLP_RETRIES = 3
YTDLP_NO_PLAYLIST = True
YTDLP_COOKIES_PATH = Path(os.getenv("YTDLP_COOKIES_PATH", "/cookies.txt"))

# youtube errors
YT_UNAVAILABLE_MAX_ERRORS = 2
YT_UNAVAILABLE_TIMEFRAME_MINUTES = 30

# Limits
MAX_DURATION_SECONDS = 3 * 60 * 60      # 3 hours
MAX_FILE_SIZE_MB = 50                   # Telegram limit-ish

# Temporary storage
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", "/storage/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)