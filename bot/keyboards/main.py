# bot/keyboards/main.py
from bot.config.app import ADMIN_USER_ID
from bot.i18n.keyboards import user_reply_keyboard
from bot.admin.keyboards import admin_reply_keyboard

ADMIN_MODE_KEY = "admin_keyboard_mode"


def get_main_keyboard(user_id: int, admin_mode: bool = False):
	if user_id == ADMIN_USER_ID:
		if admin_mode:
			return admin_reply_keyboard(user_id)
		return user_reply_keyboard(user_id, include_admin_button=True)
	return user_reply_keyboard(user_id)


def get_main_keyboard_for_context(user_id: int, context):
	return get_main_keyboard(
		user_id,
		admin_mode=bool(context.user_data.get(ADMIN_MODE_KEY, False)),
	)
