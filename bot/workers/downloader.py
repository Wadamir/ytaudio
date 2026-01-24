# bot/workers/downloader.py
import logging
import asyncio

from typing import Dict


async def process_job(job: Dict):
	"""
	Process single download job.
	All heavy logic lives here.
	"""
	from bot.main_old import _process_job_impl  # временно, см. ниже

	return await _process_job_impl(job)
