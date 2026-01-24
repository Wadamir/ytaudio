# bot/workers/queue.py
import asyncio
import logging
from telegram import Bot # type: ignore

from bot.workers.downloader import process_job

DOWNLOAD_WORKERS = 2
download_queue: asyncio.Queue = asyncio.Queue()


async def download_worker(worker_id: int, bot):
	while True:
		job = await download_queue.get()
		try:
			await process_job(job, bot)
		finally:
			download_queue.task_done()


async def start_workers(bot: Bot):
	for i in range(DOWNLOAD_WORKERS):
		asyncio.create_task(download_worker(i + 1, bot))
