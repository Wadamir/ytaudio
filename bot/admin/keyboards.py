from telegram import ReplyKeyboardMarkup, KeyboardButton # type: ignore

def admin_reply_keyboard() -> ReplyKeyboardMarkup:
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
		],
		resize_keyboard=True,
	)
