from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import set_user_language
from bot.i18n.helpers import tr, tr_user
from bot.i18n.service import is_supported_lang
from bot.i18n.keyboards import language_keyboard, user_reply_keyboard
from bot.handlers.commands import plan_handler


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
	
	await query.message.reply_text(
		tr_user(query.from_user.id, "after_language_set"),
		reply_markup=user_reply_keyboard(query.from_user.id)
	)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	user_id = query.from_user.id

	await query.answer()

	if query.data == "menu_language":
		await query.message.reply_text(
			tr_user(user_id, "start_choose_language"),
			reply_markup=language_keyboard()
		)

	elif query.data == "menu_plan":
		await plan_handler(update, context)