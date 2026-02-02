import logging

from telegram import Update, LabeledPrice # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import (
	register_user,
	can_user_download,
	is_supporter,
)
from bot.i18n.helpers import tr, tr_user
from bot.i18n.keyboards import language_keyboard, user_reply_keyboard, donate_keyboard

from bot.utils.time import time_until_utc_reset

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	is_new = register_user(user)

	if is_new:
		text = tr_user(user.id, "start_welcome_new")
		await update.message.reply_text(
			text,
			reply_markup=language_keyboard()
		)
	else:
		text = tr_user(user.id, "start_welcome_back")
		await update.message.reply_text(
			text,
			reply_markup=user_reply_keyboard(user.id)
		)


async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	allowed, used, limit, plan = can_user_download(user.id)
	reset_in = time_until_utc_reset()

	text = tr_user(
		user.id,
		"plan_info",
		plan_name=plan.capitalize(),
		limit=limit,
		used=used,
		reset_in=reset_in,
	)
	
	if is_supporter(user.id):
		supporter_text = tr_user(user.id, "supporter_info")
		text = supporter_text + text


	if not allowed:
		text += tr_user(user.id, "plan_limit_reached")
	text += tr_user(user.id, "plan_info_upgrade")

	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
	)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	text = tr_user(user.id, "help_text")

	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
	)


async def donate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)
	
	await update.message.reply_text(
		tr_user(user.id, "donate_prompt"),
		reply_markup=donate_keyboard(user.id)
	)