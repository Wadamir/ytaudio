import logging

from telegram import Update, LabeledPrice # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import (
	register_user,
	can_user_download,
	is_supporter,
)
from bot.i18n.helpers import tr, tr_user
from bot.i18n.keyboards import language_keyboard, donate_keyboard

from bot.utils.time import time_until_utc_reset
from bot.config.app import ADMIN_USER_ID
from bot.keyboards.main import get_main_keyboard, get_main_keyboard_for_context
from bot.browser_auth import browser_auth_status
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	is_new = register_user(user)

	if is_new:
		text = tr_user(user.id, "start_welcome_new")
		await update.message.reply_text(
			text,
			reply_markup=(
				get_main_keyboard(user.id)
				if user.id == ADMIN_USER_ID
				else language_keyboard()
			)
		)
	else:
		text = tr_user(user.id, "start_welcome_back")
		await update.message.reply_text(
			text,
			reply_markup=get_main_keyboard_for_context(user.id, context)
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
		reply_markup=get_main_keyboard_for_context(user.id, context),
	)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)

	text = tr_user(user.id, "help_text")

	await update.message.reply_text(
		text,
		parse_mode="HTML",
		disable_web_page_preview=True,
		reply_markup=get_main_keyboard_for_context(user.id, context),
	)


async def donate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	register_user(user)
	
	await update.message.reply_text(
		tr_user(user.id, "donate_prompt"),
		reply_markup=donate_keyboard(user.id),
	)
	if user.id == ADMIN_USER_ID:
		await update.message.reply_text(
			tr_user(user.id, "main_keyboard_ready"),
			reply_markup=get_main_keyboard_for_context(user.id, context),
		)


async def auth_youtube_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	if user.id != ADMIN_USER_ID:
		return

	try:
		status = await browser_auth_status()
	except Exception as exc:
		await update.message.reply_text(
			f"Browser auth service unavailable: {str(exc)[:200]}",
			reply_markup=get_main_keyboard_for_context(user.id, context),
		)
		return

	import os

	novnc_url = os.getenv(
		"YOUTUBE_AUTH_NOVNC_URL",
		"http://localhost:6080/vnc.html",
	)
	keyboard_rows = [
		[InlineKeyboardButton("Export cookies", callback_data="auth_export")],
		[InlineKeyboardButton("Check status", callback_data="auth_status")],
	]

	if novnc_url.startswith(("https://", "tg://")):
		keyboard_rows.insert(
			0,
			[InlineKeyboardButton("Open browser", url=novnc_url)],
		)

	keyboard = InlineKeyboardMarkup(keyboard_rows)

	await update.message.reply_text(
		(
			"<b>YouTube browser authorization</b>\n"
			f"Status: {status.get('status')}\n"
			f"Cookies file: {'available' if status.get('cookies_file') else 'not available'}\n"
			f"noVNC: {novnc_url}\n"
			"Log in to YouTube in the browser, complete 2FA/Captcha, "
			"then export cookies."
		),
		parse_mode="HTML",
		reply_markup=keyboard,
		disable_web_page_preview=True,
	)
	await update.message.reply_text(
		tr_user(user.id, "main_keyboard_ready"),
		reply_markup=get_main_keyboard_for_context(user.id, context),
	)