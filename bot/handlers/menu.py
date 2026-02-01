from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.config.app import ADMIN_USER_ID
from bot.i18n.helpers import tr_user
from bot.i18n.keyboards import language_keyboard
from bot.handlers.commands import plan_handler
from bot.admin.stats import stats_handler, users_stats_handler, downloads_stats_handler
from bot.admin.actions import system_handler


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
	"""
	Handles reply keyboard menu buttons.
	Returns True if message was handled.
	"""

	user = update.effective_user
	text = update.message.text.strip()

	# --- ADMIN MENU ---
	if user.id == ADMIN_USER_ID:
		if text.startswith("📊"):
			await stats_handler(update, context)
			return True
		
		if text.startswith("👥"):
			await users_stats_handler(update, context)
			return True
		
		if text.startswith("📥"):
			await downloads_stats_handler(update, context)
			return True
		
		if text.startswith("⚙️"):
			await system_handler(update, context)
			return True


	# --- USER MENU ---
	if text.startswith("🌐"):
		await update.message.reply_text(
			tr_user(user.id, "start_choose_language"),
			reply_markup=language_keyboard()
		)
		return True

	if text.startswith("💳"):
		await plan_handler(update, context)
		return True

	return False
