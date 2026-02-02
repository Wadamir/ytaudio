import logging

from telegram import Update # type: ignore
from telegram.ext import ContextTypes # type: ignore

from bot.db.db import log_donation, extend_supporter
from bot.i18n.helpers import tr_user

logger = logging.getLogger(__name__)


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	logger.info("Pre-checkout query received")

	query = update.pre_checkout_query
	if not query:
		return
	
	await query.answer(ok=True)
	

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	logger.info("Successful payment received")
	if not update.message or not update.message.successful_payment:
		return

	payment = update.message.successful_payment
	stars = payment.total_amount
	
	user_id = update.effective_user.id
	
	# --- Log the donation in the database ---
	log_donation(
		user_id=user_id,
		amount=stars,
		currency="XTR",
		amount_display=float(stars),
		provider="telegram_stars",
		payload=payment.invoice_payload,
		telegram_charge_id=payment.telegram_payment_charge_id,
		provider_charge_id=payment.provider_payment_charge_id,
		status="success",
	)

	# --- Extend supporter status ---
	days = stars // 10  # 10 stars = 1 day of supporter
	extend_supporter(user_id, days)

	await update.message.reply_text(
		tr_user(user_id, "donation_thanks", stars=stars)
	)
