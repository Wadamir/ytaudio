# bot/keyboards/main.py
from bot.config.app import ADMIN_USER_ID
from bot.i18n.keyboards import user_reply_keyboard
from bot.admin.keyboards import admin_reply_keyboard

def get_main_keyboard(user_id: int):
	if user_id == ADMIN_USER_ID:
		return admin_reply_keyboard()
	return user_reply_keyboard(user_id)
