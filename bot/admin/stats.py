from telegram import Update
from telegram.ext import ContextTypes

from bot.config import ADMIN_USER_ID
from bot.admin.stats import build_admin_stats_text  # если логика вынесена
# или build_admin_stats_text прямо здесь

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		return

	await update.message.reply_text(
		build_admin_stats_text(),
		parse_mode="HTML",
		disable_web_page_preview=True,
	)
