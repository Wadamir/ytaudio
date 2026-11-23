import os
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters # type: ignore
from telegram.request import HTTPXRequest

from bot.db.db import init_db
from bot.i18n.validate import validate_translations
from bot.handlers import register_handlers
from bot.workers.queue import start_workers

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Configure global application logging output layout
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Mute verbose third-party polling connection library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


async def post_init(app):
	await start_workers(app.bot)


def main():
	init_db()
	validate_translations()

	# Fetch configuration variables mapping directly from hidden environment context
	proxy_url = os.getenv("EXTERNAL_PROXY_URL")
	request_config = None

	if proxy_url:
		# Build a native authorized request object directly passing the proxy URL string
		request_config = HTTPXRequest(
			proxy=proxy_url,
			connect_timeout=20.0,
			read_timeout=20.0
		)
		logging.info("Native proxy architecture verified and injected into request core.")

	# Configure the application builder lifecycle cleanly
	builder = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init)
	if request_config:
		builder = builder.request(request_config)

	app = builder.build()

	register_handlers(app)

	logging.info("Bot started")
	app.run_polling()



if __name__ == "__main__":
	main()
