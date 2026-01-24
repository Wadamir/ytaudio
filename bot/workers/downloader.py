# bot/workers/downloader.py
import logging
import asyncio
from typing import Dict

from telegram import Bot
from i18n.helpers import tr_user


log = logging.getLogger(__name__)


async def process_job(job: Dict):
	"""
	Mock downloader.
	Simulates successful audio processing.
	"""

	log.info("[downloader] received job")

	user = job["user"]
	status_msg = job["status_msg"]
	application = job["application"]

	bot: Bot = application.bot

	# ⏳ simulate processing
	await asyncio.sleep(2)

	# ✏️ update status message
	await bot.edit_message_text(
		chat_id=status_msg.chat_id,
		message_id=status_msg.message_id,
		text=tr_user(user.id, "reading_info"),
	)

	await asyncio.sleep(2)

	# ✅ final result
	await bot.edit_message_text(
		chat_id=status_msg.chat_id,
		message_id=status_msg.message_id,
		text=(
			"✅ <b>Mock download completed</b>\n\n"
			"🎵 Audio processing pipeline is working.\n"
			"(yt-dlp not connected yet)"
		),
		parse_mode="HTML",
	)

	log.info("[downloader] mock job finished successfully")
