from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import set_user_language
from bot.i18n.helpers import tr_user
from bot.i18n.service import is_supported_lang
from bot.keyboards.main import get_main_keyboard


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	lang = query.data.removeprefix("lang_")

	if not is_supported_lang(lang):
		return

	set_user_language(query.from_user.id, lang)
	context.user_data["lang"] = lang

	await query.edit_message_text(
		tr_user(query.from_user.id, "language_set")
	)
	
	await query.message.reply_text(
		tr_user(query.from_user.id, "after_language_set"),
		reply_markup=get_main_keyboard(query.from_user.id)
	)