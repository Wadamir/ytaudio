import asyncio
import os
import logging
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from telegram.ext import ApplicationBuilder, MessageHandler, filters # type: ignore
from telegram.request import HTTPXRequest

from bot.config.downloaders import (
	YTDLP_COOKIES_PATH,
	YTDLP_INITIAL_COOKIES_PATH,
)
from bot.config.network import (
	TG_PROXY_TYPE,
	get_alternate_proxy_type,
	get_proxy_candidates,
)
from bot.db.db import (
	get_last_successful_route,
	init_db,
	set_last_successful_route,
)
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


def _copy_cookie_file(source: Path, destination: Path, *, atomic: bool) -> None:
	destination.parent.mkdir(parents=True, exist_ok=True)
	if atomic:
		tmp_path = destination.with_name(f"{destination.name}.startup.tmp")
		tmp_path.write_bytes(source.read_bytes())
		os.chmod(tmp_path, 0o600)
		os.replace(tmp_path, destination)
	else:
		destination.write_bytes(source.read_bytes())
	os.chmod(destination, 0o600)


def sync_cookie_files_by_mtime() -> None:
	root_cookies = YTDLP_INITIAL_COOKIES_PATH
	auth_cookies = YTDLP_COOKIES_PATH
	if root_cookies.resolve() == auth_cookies.resolve():
		return

	root_valid = root_cookies.is_file() and root_cookies.stat().st_size > 0
	auth_valid = auth_cookies.is_file() and auth_cookies.stat().st_size > 0
	if not root_valid and not auth_valid:
		logging.warning("[cookies] Neither cookie file contains data; skipping sync")
		return

	if root_valid and (
		not auth_valid
		or root_cookies.stat().st_mtime_ns > auth_cookies.stat().st_mtime_ns
	):
		_copy_cookie_file(root_cookies, auth_cookies, atomic=True)
		logging.info("[cookies] Root cookies are newer; updated auth cookie file")
	elif auth_valid and (
		not root_valid
		or auth_cookies.stat().st_mtime_ns > root_cookies.stat().st_mtime_ns
	):
		_copy_cookie_file(auth_cookies, root_cookies, atomic=False)
		logging.info("[cookies] Auth cookies are newer; updated root cookie file")
	else:
		logging.info("[cookies] Cookie files have equal timestamps; no sync needed")


async def probe_telegram_route(
	route_name: str,
	proxy_url: str | None,
	bot_token: str | None,
) -> tuple[str, str | None, float] | None:
	if not bot_token:
		logging.error("[%s] BOT_TOKEN is not configured; cannot call getMe", route_name)
		return None

	try:
		proxy_scheme = urlsplit(proxy_url).scheme.lower() if proxy_url else ""
	except ValueError as e:
		logging.error(
			"[telegram-startup] %s proxy configuration is invalid (%s)",
			route_name,
			type(e).__name__,
		)
		return None
	protocol = (
		"SOCKS5" if proxy_scheme.startswith("socks5")
		else "HTTPS" if proxy_scheme.startswith("https")
		else "HTTP" if proxy_scheme.startswith("http")
		else "proxy"
	)
	request_url = f"https://api.telegram.org/bot{bot_token}/getMe"
	started_at = time.perf_counter()
	try:
		async with httpx.AsyncClient(
			proxy=proxy_url or None,
			timeout=10.0,
			trust_env=False,
		) as client:
			response = await client.get(request_url)
	except (httpx.HTTPError, ImportError, ValueError) as e:
		logging.error(
			"[telegram-startup] %s connection failed (%s)",
			route_name,
			type(e).__name__,
		)
		return None

	latency_ms = (time.perf_counter() - started_at) * 1000
	connection_label = (
		f"{route_name} {protocol} handshake/tunnel"
		if proxy_url
		else "direct connection"
	)
	logging.info(
		"[telegram-startup] %s reached Telegram API (HTTP %s, %.0f ms)",
		connection_label,
		response.status_code,
		latency_ms,
	)

	try:
		result = response.json()
	except ValueError:
		logging.error(
			"[telegram-startup] %s getMe returned invalid JSON (HTTP %s)",
			route_name,
			response.status_code,
		)
		return None

	if response.is_success and isinstance(result, dict) and result.get("ok") is True:
		user = result.get("result")
		username = user.get("username") if isinstance(user, dict) else None
		logging.info(
			"[telegram-startup] %s Telegram getMe OK (bot=@%s, %.0f ms)",
			route_name,
			username or "unknown",
			latency_ms,
		)
		return route_name, proxy_url, latency_ms

	error_code = result.get("error_code") if isinstance(result, dict) else None
	logging.error(
		"[telegram-startup] %s Telegram getMe rejected (HTTP %s, API error=%s)",
		route_name,
		response.status_code,
		error_code or "unknown",
	)
	return None


async def select_telegram_proxy(bot_token: str | None) -> str | None:
	preferred_routes = [("direct", None), *get_proxy_candidates(TG_PROXY_TYPE)]
	fallback_routes = get_proxy_candidates(get_alternate_proxy_type(TG_PROXY_TYPE))
	routes = [*preferred_routes, *fallback_routes]

	last_successful_route = get_last_successful_route("telegram")
	if last_successful_route:
		saved_route = next(
			(route for route in routes if route[0] == last_successful_route),
			None,
		)
		if saved_route:
			logging.info(
				"[telegram-startup] Trying last successful route %s",
				last_successful_route,
			)
			result = await probe_telegram_route(
				saved_route[0],
				saved_route[1],
				bot_token,
			)
			if result:
				logging.info(
					"[telegram-startup] Reusing last successful route %s",
					last_successful_route,
				)
				return result[1]
			logging.warning(
				"[telegram-startup] Last successful route %s failed; rechecking all routes",
				last_successful_route,
			)
		else:
			logging.info(
				"[telegram-startup] Saved route %s is no longer configured; checking all routes",
				last_successful_route,
			)

	results = await asyncio.gather(*(
		probe_telegram_route(name, proxy_url, bot_token)
		for name, proxy_url in routes
	))
	preferred_names = {name for name, _ in preferred_routes}
	preferred_working = [
		result for result in results
		if result is not None and result[0] in preferred_names
	]
	fallback_working = [
		result for result in results
		if result is not None and result[0] not in preferred_names
	]
	working_routes = preferred_working or fallback_working

	if not working_routes:
		logging.error(
			"[telegram-startup] No route passed getMe; falling back to direct"
		)
		return None

	route_name, proxy_url, latency_ms = min(
		working_routes,
		key=lambda route: route[2],
	)
	set_last_successful_route("telegram", route_name)
	logging.info(
		"[telegram-startup] Selected %s for Telegram API (preferred_type=%s, %.0f ms)",
		route_name,
		TG_PROXY_TYPE,
		latency_ms,
	)
	return proxy_url


async def post_init(app):
	await start_workers(app.bot)


def main():
	sync_cookie_files_by_mtime()
	init_db()
	validate_translations()

	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	telegram_proxy = loop.run_until_complete(select_telegram_proxy(BOT_TOKEN))
	request_config = HTTPXRequest(
		proxy=telegram_proxy,
		connect_timeout=20.0,
		read_timeout=20.0,
		httpx_kwargs={"trust_env": False},
	)

	# Configure the application builder lifecycle cleanly
	builder = (
		ApplicationBuilder()
		.token(BOT_TOKEN)
		.request(request_config)
		.post_init(post_init)
	)

	app = builder.build()

	register_handlers(app)

	logging.info("Bot started")
	app.run_polling()



if __name__ == "__main__":
	main()
