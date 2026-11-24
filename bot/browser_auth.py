import time
from urllib.parse import quote

import aiohttp

from bot.config.app import ADMIN_USER_ID


_last_alert_at = 0.0
ALERT_COOLDOWN_SECONDS = 15 * 60


async def browser_auth_status():
    url = __import__("os").getenv(
        "YOUTUBE_AUTH_URL",
        "http://youtube-auth:8081",
    )
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{url}/health") as response:
            response.raise_for_status()
            return await response.json()


async def export_browser_cookies():
    url = __import__("os").getenv(
        "YOUTUBE_AUTH_URL",
        "http://youtube-auth:8081",
    )
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{url}/export") as response:
            response.raise_for_status()
            return await response.json()


async def notify_admin_auth_required(bot):
    global _last_alert_at

    now = time.monotonic()
    if now - _last_alert_at < ALERT_COOLDOWN_SECONDS:
        return
    _last_alert_at = now

    import os

    novnc_url = os.getenv(
        "YOUTUBE_AUTH_NOVNC_URL",
        "http://localhost:6080/vnc.html",
    )

    await bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=(
            "YouTube требует ручную авторизацию.\n\n"
            f"Откройте браузер: {novnc_url}\n"
            "Зайдите в YouTube, выполните 2FA/Captcha, затем отправьте "
            "/auth_youtube или используйте кнопку экспорта."
        ),
        disable_web_page_preview=True,
    )
