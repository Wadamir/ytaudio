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
	register_user(user)

	allowed, used, limit, plan = can_user_download(user.id)
	if not allowed:
		await update.message.reply_text(
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

	url = update.message.text.strip()

	if not is_supported_url(url):
		await update.message.reply_text(
			tr(
				context, 
				"invalid_link"
			)
		)
		return

	status_msg = await update.message.reply_text(
		tr(
			context, 
			"queue"
		)
	)

	await download_queue.put({
		"user": user,
		"url": url,
		"status_msg": status_msg,
		"application": context.application,
	})
