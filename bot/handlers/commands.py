from telegram import Update
from telegram.ext import ContextTypes

from bot.main import build_admin_stats_text
from bot.main import ADMIN_USER_ID

from bot.db.db import (
	register_user,
	can_user_download,
)
from bot.i18n.helpers import tr
from bot.i18n.keyboards import language_keyboard

from bot.utils.time import time_until_utc_reset


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	await update.message.reply_text(
		tr(context, "start_choose_language"),
		reply_markup=language_keyboard()
	)


async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	allowed, used, limit, plan = can_user_download(user.id)
	reset_in = time_until_utc_reset()

	text = tr(
		context,
		"plan_info",
		plan_name=plan.capitalize(),
		limit=limit,
		used=used,
		reset_in=reset_in,
	)

	if not allowed:
		text += "\n\n" + tr(context, "plan_limit_reached")

	text += "\n\n" + tr(context, "plan_info_upgrade")

	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
	)



async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if update.effective_user.id != ADMIN_USER_ID:
		return

	await update.message.reply_text(
		build_admin_stats_text(),
		parse_mode="HTML",
		disable_web_page_preview=True,
	)