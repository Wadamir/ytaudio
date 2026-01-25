import os
import logging
from telegram.ext import ApplicationBuilder # type: ignore

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

	logging.info("Bot started")
	app.run_polling()


if __name__ == "__main__":
	main()
