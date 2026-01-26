from telegram import InlineKeyboardMarkup, InlineKeyboardButton # type: ignore
from bot.i18n.service import LANGS
from bot.i18n.helpers import tr_user


def language_keyboard() -> InlineKeyboardMarkup:
	buttons = []

	row = []
	for code, meta in LANGS.items():
		text = f"{meta['flag']} {meta['label']}"
		row.append(
			InlineKeyboardButton(
				text,
				callback_data=f"lang_{code}"
			)
		)

		# 2 buttons per row
		if len(row) == 2:
			buttons.append(row)
			row = []

	if row:
		buttons.append(row)

	return InlineKeyboardMarkup(buttons)

def user_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup([
		[
			InlineKeyboardButton(
				tr_user(user_id, "btn_language"),
				callback_data="menu_language"
			),
			InlineKeyboardButton(
				tr_user(user_id, "btn_plan"),
				callback_data="menu_plan"
			),
		]
	])