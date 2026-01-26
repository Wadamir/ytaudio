from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore
from bot.config.app import ADMIN_USER_ID


def build_admin_stats_text() -> str:
	return "📊 Stats placeholder"


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		return

	text = build_admin_stats_text()
	await update.message.reply_text(text)