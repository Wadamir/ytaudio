# bot/workers/download_worker.py
import asyncio
import logging
import time

from typing import Iterable

from pathlib import Path
from typing import Dict

from telegram import Bot  # type: ignore
from telegram.error import BadRequest, TelegramError  # type: ignore

from bot.db.db import (
	increment_downloads,
	log_download,
	log_youtube_error,
	clear_download_reservation,
)
from bot.utils.timing import log_duration
from bot.i18n.helpers import tr_user
from bot.utils.format import (
	format_download_progress,
	format_duration,
	format_eta,
	format_size_bytes,
)

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
	NoUnencryptedAudioFormat,
	YouTubeAuthRequired,
)

from bot.pipeline.delivery import deliver
from bot.pipeline.postprocess import postprocess
from bot.pipeline.errors import (
	PipelineError,
	PostProcessingFailed,
	PostProcessingNoDuration,
	FileTooLarge,
	DeliveryFailed,
	DeliveryUnsupportedMethod,
)

from bot.utils.inflight import pop_inflight_messages, clear_inflight
from bot.browser_auth import notify_admin_auth_required

from bot.config.downloaders import MAX_DURATION_SECONDS


logger = logging.getLogger(__name__)



YOUTUBE_ERRORS = {
	"video_unavailable", 
	"live_stream", 
	"long_video",
	"info_unavailable", 
	"failed_download",
	"no_unencrypted_audio",
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
	start_ts = time.perf_counter()
	inflight_key: str | None = None


	# progress handler
	progress_text: str | None = None
	progress_lock = asyncio.Lock()
	progress_status_key = "reading_info"
	progress_status_data: dict = {}
	progress_variant_index = 0
	progress_active = True
	heartbeat_task: asyncio.Task | None = None

	async def update_progress_status(
		*,
		status_key: str | None = None,
		status_data: dict | None = None,
		advance_variant: bool = False,
	):
		nonlocal progress_text, progress_status_key
		nonlocal progress_status_data, progress_variant_index

		if not progress_active:
			return

		async with progress_lock:
			if not progress_active:
				return
			if status_key is not None:
				progress_status_key = status_key
				progress_status_data = status_data or {}
			if advance_variant:
				progress_variant_index = (progress_variant_index + 1) % 10

			base_text = tr_user(
				user_id,
				progress_status_key,
				**progress_status_data,
			)
			update_text = tr_user(
				user_id,
				f"progress_{progress_variant_index + 1}",
			)
			download_percent = progress_status_data.get("download_percent")
			download_lines = []
			progress_amount = format_download_progress(
				progress_status_data.get("downloaded_size"),
				progress_status_data.get("total_size"),
				download_percent,
			)
			if progress_amount is not None:
				download_text = tr_user(
					user_id,
					"download_progress",
					amount=progress_amount,
				)
				download_lines.append(download_text)
			download_eta = progress_status_data.get("download_eta")
			if (
				download_percent is not None
				and download_percent >= 5
				and download_eta is not None
			):
				download_lines.append(
					tr_user(user_id, "download_eta", eta=download_eta)
				)
			if download_lines:
				text = f"{base_text}\n" + "\n".join(download_lines) + f"\n\n{update_text}"
			else:
				text = f"{base_text}\n\n{update_text}"
			if text == progress_text:
				return

			try:
				await bot.edit_message_text(
					chat_id=chat_id,
					message_id=message_id,
					text=text,
				)
				progress_text = text
			except BadRequest as e:
				if "message is not modified" not in str(e).lower():
					logger.warning("[worker] progress notify failed: %s", e)
			except TelegramError as e:
				logger.warning("[worker] progress notify failed: %s", e)

	async def handle_progress(stage: DownloadStage, data: dict):
		if stage == DownloadStage.INFO_READY:
			await update_progress_status(
				status_key="info_ready",
				status_data={
					"duration": format_duration(data.get("duration_seconds")),
				},
			)
		elif stage in {
			DownloadStage.STARTING_DOWNLOAD,
			DownloadStage.DOWNLOADING,
		}:
			await update_progress_status(
				status_key=(
					"fast_mode"
					if data.get("processing_mode") == "fast_mode"
					else "slow_mode"
				),
				status_data={
					"duration": format_duration(data.get("duration_seconds")),
					"download_percent": data.get("percent"),
					"downloaded_size": format_size_bytes(
						data.get("downloaded_bytes")
					),
					"total_size": format_size_bytes(data.get("total_bytes")),
					"download_eta": format_eta(data.get("eta_seconds")),
				},
			)

	async def progress_heartbeat():
		while True:
			await asyncio.sleep(10)
			await update_progress_status(advance_variant=True)


	try:
		user_id = job["user_id"]
		chat_id = job["chat_id"]
		message_id = job["message_id"]
		url = job["url"]
		inflight_key = str(job.get("inflight_key", url))

		ctx = DownloadContext(
			user_id=user_id,
			video_url=url,
		)

		loop = asyncio.get_running_loop()
		ctx.on_progress = lambda stage, data: loop.call_soon_threadsafe(
			lambda: asyncio.create_task(handle_progress(stage, data))
		)

		# notify user
		try:
			await update_progress_status(status_key="reading_info")
			heartbeat_task = asyncio.create_task(progress_heartbeat())
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
			download_started_at = time.perf_counter()
			download_result = "error"
			try:
				await downloader.download(url, ctx)
				download_result = "success"
			finally:
				log_duration(
					logger,
					"downloader_total",
					download_started_at,
					video_id=ctx.video_id,
					result=download_result,
				)

			postprocess_started_at = time.perf_counter()
			postprocess_result = "error"
			try:
				await postprocess(ctx)
				postprocess_result = "success"
			finally:
				log_duration(
					logger,
					"postprocess",
					postprocess_started_at,
					video_id=ctx.video_id,
					result=postprocess_result,
				)

			delivery_started_at = time.perf_counter()
			delivery_result = "error"
			try:
				await deliver(ctx, bot, chat_id)
				delivery_result = "success"
			finally:
				log_duration(
					logger,
					"telegram_delivery",
					delivery_started_at,
					video_id=ctx.video_id,
					method=ctx.delivery_method,
					result=delivery_result,
				)
			
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
			if isinstance(e, YouTubeAuthRequired):
				try:
					await notify_admin_auth_required(bot)
				except Exception as alert_exc:
					logger.warning(
						"[worker] failed to notify admin about browser auth: %s",
						alert_exc,
					)

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

		except NoUnencryptedAudioFormat as e:
			ctx.status = "failed"
			ctx.fallback_reason = "no_unencrypted_audio"
			ctx.error_message = str(e)

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

		except DeliveryUnsupportedMethod as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_processing"
			ctx.error_message = str(e)

		except PipelineError as e:
			ctx.status = "failed"
			ctx.fallback_reason = "failed_processing"
			ctx.error_message = str(e)

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

		progress_active = False
		if heartbeat_task:
			heartbeat_task.cancel()
			try:
				await heartbeat_task
			except asyncio.CancelledError:
				pass

		try:
			ctx.processing_time_ms = int((time.perf_counter() - start_ts) * 1000)
			log_duration(
				logger,
				"job_total",
				start_ts,
				user_id=ctx.user_id,
				video_id=ctx.video_id,
				result=ctx.status,
			)
			try:
				log_download(**build_log_payload(ctx))
			except Exception as e:
				logger.exception("[worker] failed to log download result: %s", e)

			text_key = ctx.fallback_reason or "failed_worker"

			if ctx.status == "success":
				try:
					increment_downloads(ctx.user_id)
				except Exception as e:
					logger.exception("[worker] failed to increment download count: %s", e)
				logger.info(
					"[worker] job success for %s in %d ms",
					ctx.user_id,
					ctx.processing_time_ms,
				)
				text_key = "job_completed"
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
				message_ids = await pop_inflight_messages(
					ctx.user_id,
					inflight_key or ctx.video_url,
				)
				async with progress_lock:
					for msg_id in message_ids:
						logger.debug(f"[worker] updating inflight message {msg_id} for user {ctx.user_id}")
						try:
							await bot.edit_message_text(
								chat_id=chat_id,
								message_id=msg_id,
								text=tr_user(user_id, text_key),
							)
						except TelegramError:
							pass
			except Exception as e:
				logger.exception("[worker] failed to update inflight messages: %s", e)
				await clear_inflight(ctx.user_id, inflight_key or ctx.video_url)
		finally:
			clear_download_reservation(ctx.user_id, ctx.video_url)
			cleanup_files(ctx.downloaded_files)
			cleanup_files(ctx.output_files)
