from telegram import Update
from telegram.ext import ContextTypes

from bot.db.db import set_user_language
from bot.i18n.helpers import tr
from bot.i18n.service import is_supported_lang


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	lang = query.data.removeprefix("lang_")

	if not is_supported_lang(lang):
		return

	set_user_language(query.from_user.id, lang)
	context.user_data["lang"] = lang

	await query.edit_message_text(
		tr(context, "language_set")
	)
