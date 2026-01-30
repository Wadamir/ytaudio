from telegram.constants import ParseMode # type: ignore

# Message formatting
DEFAULT_PARSE_MODE = ParseMode.HTML

# Telegram limits
TELEGRAM_MAX_CAPTION_LENGTH = 1024
TELEGRAM_MAX_FILENAME_LENGTH = 255
TELEGRAM_MAX_FILESIZE_MB = 45  # sendAudio without premium

# Behavior
EDIT_MESSAGE_RETRIES = 2
SEND_RETRY_DELAY_SEC = 1
