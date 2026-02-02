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
			],
			[
				KeyboardButton(tr_user(user_id, "btn_donate")),
				KeyboardButton(tr_user(user_id, "btn_help")),
			],
		],
		resize_keyboard=True,
	)

def donate_keyboard(user_id: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup([
		[
			InlineKeyboardButton(
				tr_user(user_id, "donate_10_stars"),
				callback_data="donate_10_stars"
			),
			InlineKeyboardButton(
				tr_user(user_id, "donate_100_stars"),
				callback_data="donate_100_stars"
			),
		],
		[
			InlineKeyboardButton(
				tr_user(user_id, "donate_300_stars"),
				callback_data="donate_300_stars"
			),
			InlineKeyboardButton(
				tr_user(user_id, "donate_500_stars"),
				callback_data="donate_500_stars"
			),
		],
	])
