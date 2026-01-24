import logging
from telegram.ext import ApplicationBuilder

from bot.db.db import init_db
from bot.i18n.validate import validate_translations
from bot.handlers import register_handlers
from bot.workers.queue import start_workers

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


async def post_init(app):
	await start_workers()


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
