import logging
from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

# from typing import Optional
from bot.config.app import ADMIN_USER_ID

logger = logging.getLogger(__name__)


def build_system_info_text() -> str:
    # Here you would gather and format the system information
    # For demonstration, we'll return a placeholder string
    system_info = (
        "⚙️ <b>System Information</b>\n"
        "Uptime: 24 hours\n"
        "CPU Usage: 15%\n"
        "Memory Usage: 45%\n"
        "Disk Space: 70% used\n"
        "Active Downloads: 5\n"
        "Queued Downloads: 10\n"
    )
    return system_info

async def system_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        logger.warning(
            "Unauthorized /system attempt by user %s",
            update.effective_user.id
        )		
        return

    text = build_system_info_text()
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )