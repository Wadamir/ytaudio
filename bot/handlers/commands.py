from telegram import Update, ReplyKeyboardRemove # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import (
	register_user,
	can_user_download,
)
from bot.i18n.helpers import tr, tr_user
from bot.i18n.keyboards import language_keyboard, user_reply_keyboard

from bot.utils.time import time_until_utc_reset


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	is_new = register_user(user)

	if is_new:
		await update.message.reply_text(
			tr_user(user.id, "start_welcome_new"),
			reply_markup=language_keyboard()
		)
	else:
		# Show menu to returning users
		await update.message.reply_text(
			tr_user(user.id, "welcome_back"),
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

	if not allowed:
		text += tr_user(user.id, "plan_limit_reached")
	text += tr_user(user.id, "plan_info_upgrade")

	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
	)