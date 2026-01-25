from telegram import InlineKeyboardMarkup, InlineKeyboardButton # type: ignore
from bot.i18n.service import LANGS


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
