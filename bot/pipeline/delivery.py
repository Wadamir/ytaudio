# bot/pipeline/delivery.py
from pathlib import Path

from telegram import Bot  # type: ignore
from telegram.error import TelegramError  # type: ignore

from bot.downloaders.base import DownloadContext
from .errors import DeliveryFailed, DeliveryUnsupportedMethod

from bot.config.bot import (
    BOT_USERNAME,
    BOT_CAPTION_PREFIX,
)


async def _send_audio_telegram(bot: Bot, chat_id: int, file: Path, title: str = "", performer: str = "", duration: int = 0, caption: str = ""):
    try:
        with file.open("rb") as f:
            await bot.send_audio(
                chat_id=chat_id, 
                audio=f, 
                title=title, 
                performer=performer, 
                duration=duration,
                caption=caption,
            )
    except TelegramError as e:
        raise DeliveryFailed(f"Telegram delivery failed: {e}") from e


async def deliver(ctx: DownloadContext, bot: Bot, chat_id: int):
    bot_caption = f"{BOT_CAPTION_PREFIX} {BOT_USERNAME}"
    if not ctx.output_files:
        raise DeliveryFailed("No output files to deliver")

    if ctx.delivery_method == "telegram" or ctx.delivery_method == "telegram_split":
        for part in ctx.output_files:
            part_title = ctx.video_title
            part_duration = ctx.duration_seconds / len(ctx.output_files) if ctx.duration_seconds else 0
            if len(ctx.output_files) > 1:
                part_index = ctx.output_files.index(part) + 1
                part_title = f"Part {part_index}/{len(ctx.output_files)} - {ctx.video_title}"
            await _send_audio_telegram(
                bot, 
                chat_id, 
                part, 
                title=part_title, 
                performer=ctx.video_artist, 
                duration=part_duration,
                caption=bot_caption
            )

    elif ctx.delivery_method == "link":
        raise DeliveryFailed("Link delivery not implemented")

    else:
        raise DeliveryUnsupportedMethod(f"Unsupported delivery method: {ctx.delivery_method}")
