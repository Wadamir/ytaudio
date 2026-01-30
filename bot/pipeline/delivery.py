# bot/pipeline/delivery.py
from pathlib import Path

from telegram import Bot  # type: ignore
from telegram.error import TelegramError  # type: ignore

from bot.downloaders.base import DownloadContext
from .errors import DeliveryFailed


async def _send_audio_telegram(bot: Bot, chat_id: int, file: Path):
    try:
        with file.open("rb") as f:
            await bot.send_audio(chat_id=chat_id, audio=f)
    except TelegramError as e:
        raise DeliveryFailed(f"Telegram delivery failed: {e}") from e


async def deliver(ctx: DownloadContext, bot: Bot, chat_id: int):
    if not ctx.output_files:
        raise DeliveryFailed("No output files to deliver")

    if ctx.delivery_method == "telegram":
        await _send_audio_telegram(bot, chat_id, ctx.output_files[0])

    elif ctx.delivery_method == "telegram_split":
        for part in ctx.output_files:
            await _send_audio_telegram(bot, chat_id, part)

    elif ctx.delivery_method == "link":
        raise DeliveryFailed("Link delivery not implemented")

    else:
        raise DeliveryFailed(f"Unsupported delivery method: {ctx.delivery_method}")
