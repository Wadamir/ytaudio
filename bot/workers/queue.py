# bot/workers/queue.py
import asyncio
import logging

from workers.downloader import process_job

DOWNLOAD_WORKERS = 2
download_queue: asyncio.Queue = asyncio.Queue()


async def download_worker(worker_id: int):
	logging.info(f"[worker {worker_id}] started")

	while True:
		job = await download_queue.get()
		try:
			await process_job(job)
		except Exception:
			logging.exception(f"[worker {worker_id}] job failed")
		finally:
			download_queue.task_done()


async def start_workers():
	for i in range(DOWNLOAD_WORKERS):
		asyncio.create_task(download_worker(i + 1))
