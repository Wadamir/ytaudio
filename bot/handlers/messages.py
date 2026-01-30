import logging

from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import register_user, can_user_download, get_user_language, set_user_language
from bot.i18n.helpers import tr, tr_user
from bot.i18n.keyboards import user_reply_keyboard, language_keyboard
from bot.handlers.commands import plan_handler
from bot.utils.time import time_until_utc_reset
from bot.workers.queue import download_queue
from bot.downloaders.registry import is_supported_url

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return
	
	logger.info("Received message: %s", update.message.text)

	user = update.effective_user
	message = update.message

	lang = get_user_language(user.id)
	
	if not lang:
		set_user_language(user.id, 'en')
		context.user_data['lang'] = 'en'


	# --- MENU BUTTONS ---
	text = message.text.strip()

	if text.startswith("🌐"):
		await message.reply_text(
			tr_user(user.id, "start_choose_language"),
			reply_markup=language_keyboard()
		)
		return

	if text.startswith("💳"):
		await plan_handler(update, context)
		return


	# check limits
	allowed, used, limit, plan = can_user_download(user.id)
	if not allowed:
		await message.reply_text(
			tr_user(
				user.id,
				"daily_limit_reached",
				plan=plan,
				used=used,
				limit=limit,
				reset_in=time_until_utc_reset(),
			),
			parse_mode="HTML",
		)
		return

	url = message.text.strip()

	if not is_supported_url(url):
		await message.reply_text(
			tr_user(user.id, "invalid_link")
		)
		return

	# send "queued" message
	status_msg = await message.reply_text(
		tr_user(user.id, "queue")
	)

	# IMPORTANT:
	# job contains ONLY DATA, no bot, no application
	job = {
		"user_id": user.id,
		"chat_id": message.chat_id,
		"message_id": status_msg.message_id,
		"url": url,
	}

	await download_queue.put(job)
