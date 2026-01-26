from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton # type: ignore
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

def user_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
	return ReplyKeyboardMarkup(
		[
			[
				KeyboardButton(tr_user(user_id, "btn_language")),
				KeyboardButton(tr_user(user_id, "btn_plan")),
			]
		],
		resize_keyboard=True,
		persistent=True,
	)
