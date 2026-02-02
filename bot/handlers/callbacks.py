import logging

from telegram import Update, LabeledPrice  # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import set_user_language
from bot.i18n.helpers import tr, tr_user
from bot.i18n.service import is_supported_lang
from bot.keyboards.main import get_main_keyboard

logger = logging.getLogger(__name__)

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
	

async def donate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	logger.info("Donate callback triggered")
	
	query = update.callback_query
	await query.answer()

	option = query.data  # donate stars
	logger.info("Donate option selected: %s", option)

	user_id = query.from_user.id

	prices_map = {
		"donate_10_stars": [LabeledPrice(tr_user(user_id, "donate_10_stars"), 10)],
		"donate_100_stars": [LabeledPrice(tr_user(user_id, "donate_100_stars"), 100)],
		"donate_300_stars": [LabeledPrice(tr_user(user_id, "donate_300_stars"), 300)],
		"donate_500_stars": [LabeledPrice(tr_user(user_id, "donate_500_stars"), 500)],
	}

	if option not in prices_map:
		return

	await context.bot.send_invoice(
		chat_id=query.from_user.id,
		title=tr_user(user_id, "donation_title"),
		description=tr_user(user_id, "donation_description"),
		payload=option,
		provider_token="STAR",  # 🔥 Important!
		currency="XTR",
		prices=prices_map[option],
	)
