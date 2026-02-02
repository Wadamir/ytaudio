import os
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters # type: ignore

from bot.db.db import init_db
from bot.i18n.validate import validate_translations
from bot.handlers import register_handlers
from bot.workers.queue import start_workers

BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🔹 1. basicConfig
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# 🔹 2. Mute libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


async def post_init(app):
	await start_workers(app.bot)
	

# Test
# async def log_all_updates(update: object, context):
# 	print("RAW UPDATE:", update)



def main():
	init_db()
	validate_translations()

	app = (
		ApplicationBuilder()
		.token(BOT_TOKEN)
		.post_init(post_init)
		.build()
	)

	register_handlers(app)
	# app.add_handler(MessageHandler(filters.ALL, log_all_updates), group=-1)

	logging.info("Bot started")
	app.run_polling()


if __name__ == "__main__":
	main()
