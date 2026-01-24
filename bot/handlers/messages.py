from telegram import Update
from telegram.ext import ContextTypes

from bot.db.db import register_user, can_user_download
from bot.i18n.helpers import tr
from bot.utils.time import time_until_utc_reset
from bot.workers.queue import download_queue
from bot.parsers.registry import is_supported_url


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return

	user = update.effective_user
	message = update.message

	# register / update user
	register_user(user)

	# check limits
	allowed, used, limit, plan = can_user_download(user.id)
	if not allowed:
		await message.reply_text(
			tr(
				context,
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
			tr(context, "invalid_link")
		)
		return

	# send "queued" message
	status_msg = await message.reply_text(
		tr(context, "queue")
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
