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

	# Fetch configuration variables mapping directly from environment contexts
	proxy_url = os.getenv("EXTERNAL_PROXY_URL")
	request_config = None

	if proxy_url:
		from urllib.parse import urlparse
		# Parse the proxy string dynamically without exposing plain credentials in code layout
		parsed_url = urlparse(proxy_url)
		
		proxy_host = f"{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}"
		proxy_user = parsed_url.username
		proxy_password = parsed_url.password

		# Build authorized request configuration object dynamically using variables
		request_config = HTTPXRequest(
			proxy=proxy_host,
			proxy_kwargs={
				"username": proxy_user,
				"password": proxy_password
			},
			connect_timeout=20.0,
			read_timeout=20.0
		)

	app = (
		ApplicationBuilder()
		.token(BOT_TOKEN)
		.request(request_config) if request_config else ApplicationBuilder().token(BOT_TOKEN)
	)
	
	# Apply final orchestration hooks to the builder instances
	app = app.post_init(post_init).build()

	register_handlers(app)

	logging.info("Bot started")
	app.run_polling()



if __name__ == "__main__":
	main()
