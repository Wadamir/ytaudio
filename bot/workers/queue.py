import asyncio
import logging
from telegram import Bot  # type: ignore

from bot.workers.download_worker import process_job

DOWNLOAD_WORKERS = 2

download_queue: asyncio.Queue = asyncio.Queue()


async def download_worker(worker_id: int, bot: Bot):
	logging.info(f"[worker {worker_id}] started")

	while True:
		job = await download_queue.get()
		try:
			logging.info(f"[worker {worker_id}] processing job")
			await process_job(job, bot)
		except Exception:
			logging.exception(f"[worker {worker_id}] job failed")
		finally:
			download_queue.task_done()


async def start_workers(bot: Bot):
	for i in range(DOWNLOAD_WORKERS):
		asyncio.create_task(
			download_worker(i + 1, bot)
		)
