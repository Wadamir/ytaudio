from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.config.app import ADMIN_USER_ID
from bot.i18n.helpers import tr_user
from bot.i18n.keyboards import language_keyboard
from bot.handlers.commands import plan_handler, help_handler, donate_handler
from bot.admin.stats import stats_handler, users_stats_handler, downloads_stats_handler
from bot.admin.actions import system_handler
from bot.keyboards.main import ADMIN_MODE_KEY, get_main_keyboard


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
	"""
	Handles reply keyboard menu buttons.
	Returns True if message was handled.
	"""

	user = update.effective_user
	text = update.message.text.strip()

	# --- ADMIN MENU ---
	if user.id == ADMIN_USER_ID:
		if text == tr_user(user.id, "btn_admin_mode"):
			context.user_data[ADMIN_MODE_KEY] = True
			await update.message.reply_text(
				tr_user(user.id, "admin_mode_enabled"),
				reply_markup=get_main_keyboard(user.id, admin_mode=True),
			)
			return True

		if text == tr_user(user.id, "btn_user_mode"):
			context.user_data[ADMIN_MODE_KEY] = False
			await update.message.reply_text(
				tr_user(user.id, "user_mode_enabled"),
				reply_markup=get_main_keyboard(user.id),
			)
			return True

		if context.user_data.get(ADMIN_MODE_KEY, False) and text.startswith("📊"):
			await stats_handler(update, context)
			return True
		
		if context.user_data.get(ADMIN_MODE_KEY, False) and text.startswith("👥"):
			await users_stats_handler(update, context)
			return True
		
		if context.user_data.get(ADMIN_MODE_KEY, False) and text.startswith("📥"):
			await downloads_stats_handler(update, context)
			return True
		
		if context.user_data.get(ADMIN_MODE_KEY, False) and text.startswith("⚙️"):
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
	
	if text.startswith("❓"):
		await help_handler(update, context)
		return True
	
	if text.startswith("⭐"):
		await donate_handler(update, context)
		return True

	return False
