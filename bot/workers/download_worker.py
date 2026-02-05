# bot/workers/download_worker.py
import asyncio
import logging

from typing import Iterable

from pathlib import Path
from typing import Dict

from telegram import Bot  # type: ignore
from telegram.error import TelegramError  # type: ignore

from bot.db.db import increment_downloads, log_download, log_youtube_error
from bot.i18n.helpers import tr_user
from bot.utils.format import format_duration

from bot.downloaders.base import DownloadContext
from bot.downloaders.registry import get_downloader
from bot.downloaders.stages import DownloadStage
from bot.downloaders.errors import (
	DownloaderError,
	VideoUnavailable,
	LiveStreamNotSupported,
	VideoTooLong,
	DownloadFailed,
	FetchInfoFailed,
)

from bot.pipeline.delivery import deliver
from bot.pipeline.postprocess import postprocess
from bot.pipeline.errors import (
	PipelineError,
	PostProcessingFailed,
	PostProcessingNoDuration,
	FileTooLarge,
	DeliveryFailed,
)

from bot.utils.inflight import get_inflight_messages, pop_inflight_messages, clear_inflight

from bot.config.downloaders import MAX_DURATION_SECONDS


logger = logging.getLogger(__name__)



YOUTUBE_ERRORS = {
	"video_unavailable", 
	"live_stream", 
	"long_video",
	"info_unavailable", 
	"failed_download"
}



def build_log_payload(ctx: DownloadContext) -> dict:
	return {
		"user_id": ctx.user_id,
		"video_url": ctx.video_url,
		"video_id": ctx.video_id,
		"video_title": ctx.video_title,
		"duration_seconds": ctx.duration_seconds,
		"chosen_bitrate": ctx.chosen_bitrate,
		"estimated_size_mb": ctx.estimated_size_mb,
		"real_size_mb": ctx.real_size_mb,
		"processing_mode": ctx.processing_mode,
		"processing_time_ms": ctx.processing_time_ms,
		"delivery_method": ctx.delivery_method,
		"status": ctx.status,		
		"file_path": ",".join(str(p) for p in ctx.output_files) if ctx.output_files else None,
		"download_url": None,
		"fallback_reason": ctx.fallback_reason,
		"error_message": ctx.error_message,
	}


def cleanup_files(paths: Iterable[Path | None]):
	if not paths:
		return
	
	for p in paths:
		if not p:
			continue
		try:
			p.unlink(missing_ok=True)
			logger.debug(f"[downloader] cleaned up {p}")
		except Exception as e:
			logger.warning(f"[downloader] failed to cleanup {p}: {e}")



async def process_job(job: Dict, bot: Bot):
	logger.info("[worker] received job")

	ctx: DownloadContext | None = None
	start_ts = asyncio.get_event_loop().time()


	# progress handler
	async def handle_progress(stage: DownloadStage, data: dict):
		try:
			if stage == DownloadStage.INFO_READY:
				await bot.edit_message_text(
					chat_id=chat_id,
					message_id=message_id,
					text=tr_user(
						user_id,
						"info_ready",
						duration=format_duration(data.get("duration_seconds")),
					),
				)

			elif stage == DownloadStage.STARTING_DOWNLOAD or stage == DownloadStage.DOWNLOADING:
				await bot.edit_message_text(
					chat_id=chat_id,
					message_id=message_id,
					text=tr_user(
						user_id,
						"fast_mode" if data.get("processing_mode") == "fast_mode" else "slow_mode",
						duration=format_duration(data.get("duration_seconds")),
					),
				)
		except TelegramError as e:
			# ⚠️ ignore errors here to not break the download flow
			logger.warning("[worker] progress notify failed: %s", e)


	try:
		user_id = job["user_id"]
		chat_id = job["chat_id"]
		message_id = job["message_id"]
		url = job["url"]

		ctx = DownloadContext(
			user_id=user_id,
			video_url=url,
		)

		ctx.on_progress = lambda stage, data: asyncio.create_task(
			handle_progress(stage, data)
		)		

		# notify user
		try:
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "reading_info"),
			)
		except TelegramError as e:
			logger.warning(f"[worker] notify failed: {e}")

		downloader = get_downloader(url)
		if not downloader:
			ctx.status = "failed"
			ctx.fallback_reason = "unsupported_platform"
			ctx.error_message = "Unsupported platform"
			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "unsupported_platform"),
			# )
			return

		try:
			await downloader.download(url, ctx)
			await postprocess(ctx)
			await deliver(ctx, bot, chat_id)
			
			ctx.status = "success"

		except VideoUnavailable:
			ctx.status = "failed"
			ctx.fallback_reason = "video_unavailable"
			ctx.error_message = "Video is unavailable"

			# log_youtube_error(
			# 	error_type="unavailable",
			# 	video_id=ctx.video_id,
			# 	video_url=ctx.video_url,
			# 	ua_profile=ctx.ua_profile,
			# 	error_message=ctx.error_message,
			# )

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "video_unavailable"),
			# )

		except LiveStreamNotSupported:
			ctx.status = "failed"
			ctx.fallback_reason = "live_stream"
			ctx.error_message = "Live streams are not supported"

			# log_youtube_error(
			# 	error_type="live",
			# 	video_id=ctx.video_id,
			# 	video_url=ctx.video_url,
			# 	ua_profile=ctx.ua_profile,
			# 	error_message=ctx.error_message,
			# )

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "live_not_supported"),
			# )

		except VideoTooLong:
			ctx.status = "failed"
			ctx.fallback_reason = "long_video"
			ctx.error_message = "Video duration exceeds allowed limit"

			# log_youtube_error(
			# 	error_type="too_long",
			# 	video_id=ctx.video_id,
			# 	video_url=ctx.video_url,
			# 	ua_profile=ctx.ua_profile,
			# 	error_message=ctx.error_message,
			# )

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "video_too_long", max_duration=format_duration(MAX_DURATION_SECONDS)),
			# )
		except FetchInfoFailed as e:
			ctx.status = "failed"
			ctx.fallback_reason = "info_unavailable"
			ctx.error_message = str(e)

			# log_youtube_error(
			# 	error_type="fetch_info",
			# 	video_id=ctx.video_id,
			# 	video_url=ctx.video_url,
			# 	ua_profile=ctx.ua_profile,
			# 	error_message=ctx.error_message,
			# )

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_reading_info"),
			# )

		except DownloadFailed as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_download"			
			ctx.error_message = str(e)
			# log_youtube_error(
			# 	error_type="unknown",
			# 	video_id=ctx.video_id,
			# 	video_url=ctx.video_url,
			# 	ua_profile=ctx.ua_profile,
			# 	error_message=ctx.error_message,
			# )

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_download"),
			# )

		except PipelineError as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_processing"			
			ctx.error_message = str(e)

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_processing"),
			# )	

		except PostProcessingFailed as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_processing"
			ctx.error_message = str(e)			

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_processing"),
			# )

		except PostProcessingNoDuration as e:
			ctx.status = "failed"
			ctx.fallback_reason = "no_duration"
			ctx.error_message = str(e)			

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_processing"),
			# )

		except FileTooLarge as e:
			ctx.status = "failed"
			ctx.fallback_reason = "large_file"
			ctx.error_message = str(e)			

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "large_file"),
			# )

		except DeliveryFailed as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_delivery"			
			ctx.error_message = str(e)

			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "failed_sending_audio"),
			# )

	except Exception as e:
		logger.exception("[worker] unexpected fatal error")

		if ctx:
			ctx.status = "failed"
			ctx.fallback_reason = "internal_error"
			ctx.error_message = str(e)[:500]

			# try:
			# 	await bot.edit_message_text(
			# 		chat_id=chat_id,
			# 		message_id=message_id,
			# 		text=tr_user(user_id, "failed_worker"),
			# 	)
			# except TelegramError:
			# 	pass

	finally:
		if not ctx:
			return
		
		ctx.processing_time_ms = int(
			(asyncio.get_event_loop().time() - start_ts) * 1000
		)
		log_download(**build_log_payload(ctx))

		text_key = ctx.fallback_reason or "failed_worker"

		if ctx.status == "success":
			increment_downloads(ctx.user_id)
			logger.info(
				"[worker] job success for %s in %d ms",
				ctx.user_id,
				ctx.processing_time_ms,
			)
			text_key = "job_completed"
			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, "job_completed"),
			# )
			# for msg_id in pop_inflight_messages(ctx.user_id, ctx.video_url):
			# 	try:
			# 		await bot.edit_message_text(
			# 			chat_id=chat_id,
			# 			message_id=msg_id,
			# 			text=tr_user(user_id, "job_completed"),
			# 		)
			# 	except TelegramError:
			# 		pass
		else:
			logger.info(
				"[worker] job failed for %s in %d ms: %s",
				ctx.user_id,
				ctx.processing_time_ms,
				ctx.fallback_reason or ctx.error_message,
			)
			if ctx.fallback_reason in YOUTUBE_ERRORS:
				try:
					log_youtube_error(
						error_type=ctx.fallback_reason,
						video_id=ctx.video_id,
						video_url=ctx.video_url,
						ua_profile=ctx.ua_profile,
						error_message=ctx.error_message
					)
				except Exception as e:
					logger.warning(f"[worker] failed to log youtube error: {e}")

		try:
			# await bot.edit_message_text(
			# 	chat_id=chat_id,
			# 	message_id=message_id,
			# 	text=tr_user(user_id, text_key),
			# )
			for msg_id in pop_inflight_messages(ctx.user_id, ctx.video_url):
				try:
					await bot.edit_message_text(
						chat_id=chat_id,
						message_id=msg_id,
						text=tr_user(user_id, text_key),
					)
				except TelegramError:
					pass
		except TelegramError:
			pass

		#try clean inflight
		clear_inflight(ctx.user_id, ctx.video_url)
		
		# cleanup files
		cleanup_files(ctx.downloaded_files)
		cleanup_files(ctx.output_files)	
