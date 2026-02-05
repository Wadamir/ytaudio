import logging

from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import register_user, can_user_download, get_user_language, set_user_language
from bot.i18n.helpers import tr, tr_user
from bot.i18n.keyboards import user_reply_keyboard
from bot.utils.time import time_until_utc_reset
from bot.workers.queue import download_queue
from bot.downloaders.registry import is_supported_url
from bot.handlers.menu import handle_menu
from bot.utils.inflight import is_inflight, mark_inflight, clear_inflight

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
		
	if message.text.startswith("/"):
		# Ignore commands   
		return

	if await handle_menu(update, context):
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
			tr_user(user.id, "unsupported_platform")
		)
		return
		
	if await is_inflight(user.id, url):
		status = await update.message.reply_text(
			tr_user(user.id, "already_inflight")
		)
		await mark_inflight(user.id, url, status.message_id)
		return

	await mark_inflight(user.id, url, message.message_id)

	try:
		# send "queued" message
		status_msg = await message.reply_text(
			tr_user(user.id, "queue"),
			# reply_markup=user_reply_keyboard(user.id)
		)

		# job contains ONLY DATA, no bot, no application
		job = {
			"user_id": user.id,
			"chat_id": message.chat_id,
			"message_id": status_msg.message_id,
			"url": url,
		}

		await download_queue.put(job)
	except Exception as e:
		logger.error("Failed to enqueue download job: %s", e)
		await message.reply_text(
			tr_user(user.id, "failed_worker")
		)
		await clear_inflight(user.id, url)
		raise e