import logging

from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import (
	register_user,
	reserve_download_slot,
	clear_download_reservation,
	get_user_language,
	set_user_language,
)
from bot.config.app import ADMIN_USER_ID
from bot.i18n.helpers import tr_user
from bot.keyboards.main import get_main_keyboard_for_context
from bot.utils.time import time_until_utc_reset
from bot.workers.queue import download_queue
from bot.downloaders.registry import is_supported_url
from bot.handlers.menu import handle_menu
from bot.utils.inflight import canonical_inflight_key, mark_inflight, clear_inflight
from bot.utils.urls import is_youtube_post_url

logger = logging.getLogger(__name__)


async def ensure_admin_keyboard_visible(
	update: Update,
	context: ContextTypes.DEFAULT_TYPE,
):
	user = update.effective_user
	message = update.effective_message
	if not user or user.id != ADMIN_USER_ID or not message:
		return

	await message.reply_text(
		tr_user(user.id, "main_keyboard_ready"),
		reply_markup=get_main_keyboard_for_context(user.id, context),
	)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not update.message or not update.message.text:
		return
	
	logger.info("Received message: %s", update.message.text)

	user = update.effective_user
	message = update.message
	register_user(user)

	lang = get_user_language(user.id)
	reply_markup = get_main_keyboard_for_context(user.id, context)
	
	if not lang:
		set_user_language(user.id, 'en')
		context.user_data['lang'] = 'en'
		
	if message.text.startswith("/"):
		# Ignore commands   
		return

	if await handle_menu(update, context):
		return


	url = message.text.strip()

	if is_youtube_post_url(url):
		await message.reply_text(
			tr_user(user.id, "youtube_post_not_video"),
			reply_markup=reply_markup,
		)
		return

	if not is_supported_url(url):
		await message.reply_text(
			tr_user(user.id, "unsupported_platform"),
			reply_markup=reply_markup,
		)
		return

	inflight_key = canonical_inflight_key(url)

	try:
		# send "queued" message
		status_msg = await message.reply_text(
			tr_user(user.id, "queue"),
			reply_markup=reply_markup,
		)
		created_inflight = await mark_inflight(
			user.id,
			inflight_key,
			status_msg.message_id,
		)
		
		if not created_inflight:
			await status_msg.edit_text(
				tr_user(user.id, "already_inflight")
			)
			return

		allowed, used, limit, plan = reserve_download_slot(user.id, url)
		if not allowed:
			await clear_inflight(user.id, inflight_key)
			await status_msg.edit_text(
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
	
		# job contains ONLY DATA, no bot, no application
		job = {
			"user_id": user.id,
			"chat_id": message.chat_id,
			"message_id": status_msg.message_id,
			"url": url,
			"inflight_key": inflight_key,
		}

		await download_queue.put(job)
	except Exception as e:
		logger.error("Failed to enqueue download job: %s", e)
		await message.reply_text(
			tr_user(user.id, "failed_worker"),
			reply_markup=reply_markup,
		)
		clear_download_reservation(user.id, url)
		await clear_inflight(user.id, inflight_key)
		raise e