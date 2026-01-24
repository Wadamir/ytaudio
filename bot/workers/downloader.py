# bot/workers/downloader.py

import logging
from typing import Dict


async def process_job(job: Dict):
	"""
	Process single download job.

	This is a temporary MVP implementation.
	Real download logic will be added later.
	"""

	logging.info("[downloader] received job")

	# For now, just log job contents
	logging.debug(f"[downloader] job payload: {job}")

	# Explicitly fail to make it clear that downloader is not ready yet
	raise NotImplementedError(
		"Downloader logic is not implemented yet"
	)
