from telegram import ReplyKeyboardMarkup, KeyboardButton # type: ignore
from bot.i18n.helpers import tr_user


def admin_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
	return ReplyKeyboardMarkup(
		[
			[
				KeyboardButton("📊 Stats"),
				KeyboardButton("👥 Users"),
			],
			[
				KeyboardButton("📥 Downloads"),
				KeyboardButton("⚙️ System"),
			],
			[KeyboardButton(tr_user(user_id, "btn_user_mode"))],
		],
		resize_keyboard=True,
	)
