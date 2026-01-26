import re
import asyncio
import logging
import uuid
import yt_dlp # type: ignore
import math

from typing import Optional, Literal, Iterable
from dataclasses import dataclass

from pathlib import Path
from typing import Dict

from telegram import Bot  # type: ignore
from telegram.error import TelegramError  # type: ignore

from bot.utils.format import format_duration, format_size_mb
from bot.utils.text import safe_filename, sanitize_text_field

from bot.db.db import increment_downloads, log_download
from bot.i18n.helpers import tr_user

from bot.config.downloader import (
	AUDIO_DIR,
	AUDIO_FORMAT_PREFERRED,	
	AUDIO_BITRATE_PREFERRED,
	AUDIO_BITRATE_PREFERRED_ARG,
	MAX_FILENAME_LENGTH,
	YTDLP_RETRIES,
	YTDLP_COOKIES_PATH,
	YTDLP_NO_PLAYLIST,	
	MAX_DURATION_SECONDS,
	MAX_FILE_SIZE_MB,
)

from bot.config.telegram import (
	TELEGRAM_MAX_FILESIZE_MB,
)

logger = logging.getLogger(__name__)


@dataclass
class DownloadContext:
	user_id: int
	video_url: str

	# video info
	video_id: Optional[str] = None
	video_title: Optional[str] = None
	duration_seconds: Optional[int] = None

	# processing
	processing_mode: Optional[Literal["fast", "slow"]] = "slow"
	chosen_bitrate: Optional[int] = None

	# result
	status: Literal["success", "failed"] = "failed"
	delivery_method: Optional[Literal["telegram", "telegram_split", "link", "failed"]] = "failed"
	error_message: Optional[str] = None

	# metrics
	estimated_size_mb: Optional[float] = None
	real_size_mb: Optional[float] = None
	processing_time_ms: Optional[int] = None

	# errors
	fallback_reason: Optional[str] = None #too_large | long_video | timeout | NULL
	error_message: Optional[str] = None
@dataclass
class DownloadPlan:
	tmp_id: str
	mode: Literal["fast_mode", "slow_mode"]
	title: str
	uploader: str
	bitrate: int
	out_dir: Path

def ydl_base_opts():
	return {
		"cookies": str(YTDLP_COOKIES_PATH),
		"quiet": True,
		"socket_timeout": 30,
		"retries": YTDLP_RETRIES,
		"fragment_retries": 3,
		"noplaylist": YTDLP_NO_PLAYLIST,
	}

def ydl_fast_mode_opts(plan: DownloadPlan):
	return {
		**ydl_base_opts(),
		"format": "bestaudio[ext=m4a]/bestaudio",
		"outtmpl": str(plan.out_dir / f"{plan.tmp_id}.%(ext)s"),
		"postprocessors": [],
	}

def ydl_slow_mode_opts(plan: DownloadPlan):
	return {
		**ydl_base_opts(),
		"format": "bestaudio/best",
		"outtmpl": str(plan.out_dir / f"{plan.tmp_id}.%(ext)s"),
		"postprocessors": [
			{
				"key": "FFmpegExtractAudio",
				"preferredcodec": AUDIO_FORMAT_PREFERRED,
				"preferredquality": AUDIO_BITRATE_PREFERRED_ARG,
			},
			{
				"key": "FFmpegMetadata",
			},
		],
		"postprocessor_args": [
			"-metadata", f"title={plan.title}",
			"-metadata", f"artist={plan.uploader}",
		],
	}

def can_use_fast_mode(info: Dict) -> bool:
	for f in info.get("formats", []):
		if f.get("ext") != "m4a":
			continue
		if f.get("acodec") != "mp4a.40.2":
			continue

		size = f.get("filesize") or f.get("filesize_approx")
		if size and size / 1024 / 1024 <= MAX_FILE_SIZE_MB:
			return True
	return False

async def ytdlp_download_with_retry(url: str, opts: dict):
	last_exc = None

	for attempt in range(1, YTDLP_RETRIES + 1):
		try:
			return await asyncio.to_thread(
				lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=True)
			)
		except Exception as e:
			last_exc = e
			logger.warning(
				f"[downloader] yt-dlp attempt {attempt}/{YTDLP_RETRIES} failed: {e}"
			)

	raise last_exc

async def split_audio_by_time(
	src: Path,
	out_dir: Path,
	part_duration: float,
	total_parts: int,
	prefix: str,
	ext: str,
):
	parts = []

	for i in range(total_parts):
		out_file = out_dir / f"{prefix}_part{i + 1}.{ext}"
		start = i * part_duration

		cmd = [
			"ffmpeg",
			"-y",
			"-i", str(src),
			"-ss", str(start),
			"-t", str(part_duration),
			"-vn",
			"-acodec", "libmp3lame",
			"-ab", f"{AUDIO_BITRATE_PREFERRED}k",
			str(out_file),
		]

		proc = await asyncio.create_subprocess_exec(
			*cmd,
			stdout=asyncio.subprocess.DEVNULL,
			stderr=asyncio.subprocess.PIPE,
		)

		_, stderr = await proc.communicate()
		if proc.returncode != 0:
			raise RuntimeError(stderr.decode("utf-8", errors="ignore"))

		parts.append(out_file)

	return parts

def cleanup_files(paths: Iterable[Path | None]):
	for p in paths:
		if not p:
			continue
		try:
			p.unlink(missing_ok=True)
			logger.debug(f"[downloader] cleaned up {p}")
		except Exception as e:
			logger.warning(f"[downloader] failed to cleanup {p}: {e}")



async def process_job(job: Dict, bot: Bot):
	logger.info("[downloader] received job")

	try:
		user_id: int = job["user_id"]
		chat_id: int = job["chat_id"]
		message_id: int = job["message_id"]
		url: str = job["url"]
		
		ctx = DownloadContext(
			user_id=user_id,
			video_url=url,
		)        

		tmp_files: list[Path] = []

		tmp_id = uuid.uuid4().hex

		info = None

		# notify user
		try:
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "reading_info"),
			)
		except TelegramError as e:
			logger.warning(f"[downloader] notify failed: {e}")
		except Exception as e:
			logger.exception("[downloader] unexpected error during notify")

		start_ts = asyncio.get_event_loop().time()

		try:
			opts = ydl_base_opts()
			opts["skip_download"] = True

			info = await asyncio.to_thread(
				lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
			)
			logger.debug(f"[downloader] video info: {info}")
		except Exception as e:
			logger.exception("[downloader] failed reading video info")
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "failed_reading_info"),
			)
			return
		
		if info.get("is_live"):
			logger.warning("[downloader] live streams are not supported")
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "live_stream_not_supported"),
			)
			return
		
		duration = info.get("duration")
		if not isinstance(duration, int):
			duration = None
		
		if duration and duration > MAX_DURATION_SECONDS:
			logger.warning("[downloader] video duration exceeds limit")
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "duration_exceeds_limit").format(max_duration=MAX_DURATION_SECONDS),
			)
			return
		
		mode = "fast_mode" if can_use_fast_mode(info) else "slow_mode"

		plan = DownloadPlan(
			tmp_id=tmp_id,
			mode=mode,
			title=info.get("title", "audio"),
			uploader=info.get("uploader") or info.get("artist") or info.get("channel") or "YouTube",
			bitrate=AUDIO_BITRATE_PREFERRED,
			out_dir=AUDIO_DIR,
		)
		
		ctx.video_id = info.get("id")
		ctx.video_title = plan.title
		ctx.duration_seconds = duration
		ctx.chosen_bitrate = plan.bitrate

		if plan.mode == "fast_mode":
			ctx.processing_mode = "fast"
			opts = ydl_fast_mode_opts(plan)
		else:
			ctx.processing_mode = "slow"
			opts = ydl_slow_mode_opts(plan)
		
		#notify user about download start
		try:
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, plan.mode, duration=format_duration(duration)),
			)
		except TelegramError as e:
			logger.warning(f"[downloader] notify failed: {e}")
		except Exception as e:
			logger.exception("[downloader] unexpected error during notify")				



		# download audio
		try:
			await ytdlp_download_with_retry(
				url=url,
				opts=opts,
			)

			files = list(AUDIO_DIR.glob(f"{tmp_id}.*"))
			if not files:
				raise RuntimeError("yt-dlp finished but no files found")
			
			tmp_path = files[0]
			tmp_files.append(tmp_path)

			real_size_mb = round(tmp_path.stat().st_size / 1024 / 1024 , 2)
			ctx.real_size_mb = real_size_mb
			logger.debug(f"[downloader] downloaded file size: {format_size_mb(real_size_mb)}")

		except Exception as e:
			logger.exception("[downloader] failed downloading audio")
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "failed_download"),
			)
			# log_download(
			# 	user_id=user_id,
			# 	video_url=url,
			# 	video_id=None,
			# 	video_title=None,
			# 	duration_seconds=None,
			# 	chosen_bitrate=plan.bitrate,
			# 	estimated_size_mb=None,
			# 	real_size_mb=None,
			# 	processing_mode="yt-dlp",
			# 	processing_time_ms=None,
			# 	delivery_method="failed",
			# 	status="failed",
			# 	error_message=str(e)[:500],
			# )
			ctx.delivery_method = "failed"
			ctx.status = "failed"
			ctx.fallback_reason = "download_failed"
			ctx.error_message = str(e)[:500]

			return
		


		# Telegram send audio
		if real_size_mb <= TELEGRAM_MAX_FILESIZE_MB:
			try:
				with open(tmp_path, "rb") as audio_f:
					await bot.send_audio(
						chat_id=chat_id,
						audio=audio_f,
						filename=safe_filename(plan.title, max_len=MAX_FILENAME_LENGTH) + f".{AUDIO_FORMAT_PREFERRED}",
						title=plan.title,
						performer=plan.uploader,
						duration=info.get("duration"),
						caption=tr_user(user_id, "audio_ready_caption"),
						parse_mode="HTML",
					)
				ctx.status = "success"
				ctx.delivery_method = "telegram"
			except Exception as e:
				logger.exception("[downloader] failed sending audio via Telegram")
				await bot.edit_message_text(
					chat_id=chat_id,
					message_id=message_id,
					text=tr_user(user_id, "failed_sending_audio"),
				)
				# log_download(
				# 	user_id=user_id,
				# 	video_url=url,
				# 	video_id=None,
				# 	video_title=plan.title,
				# 	duration_seconds=info.get("duration"),
				# 	chosen_bitrate=plan.bitrate,
				# 	estimated_size_mb=None,
				# 	real_size_mb=format_size_mb(real_size_mb),
				# 	processing_mode="yt-dlp",
				# 	processing_time_ms=None,
				# 	delivery_method="telegram",
				# 	status="failed",
				# 	error_message=str(e)[:500],
				# )
				ctx.delivery_method = "failed"				
				ctx.status = "failed"
				ctx.fallback_reason = "sending_failed"
				ctx.error_message = str(e)[:500]

				return
		else:
			part_size_mb = TELEGRAM_MAX_FILESIZE_MB - 5
			total_parts = math.ceil(real_size_mb / part_size_mb)

			if not duration:
				raise RuntimeError("Cannot split audio without duration")

			part_duration = duration / total_parts

			try:
				parts = await split_audio_by_time(
					src=tmp_path,
					out_dir=AUDIO_DIR,
					part_duration=part_duration,
					total_parts=total_parts,
					prefix=f"{plan.tmp_id}_{safe_filename(plan.title, MAX_FILENAME_LENGTH)}",
					ext=AUDIO_FORMAT_PREFERRED,
				)
				tmp_files.extend(parts)

				for p in parts:
					size_mb = p.stat().st_size / 1024 / 1024
					if size_mb > TELEGRAM_MAX_FILESIZE_MB:
						raise RuntimeError(
							f"Split part exceeds Telegram limit: {size_mb:.2f} MB"
						)				

				for idx, part_path in enumerate(parts, start=1):
					with open(part_path, "rb") as audio_f:
						await bot.send_audio(
							chat_id=chat_id,
							audio=audio_f,
							filename=part_path.name,
							title=f"(Part {idx}/{total_parts}) - {plan.title}",
							performer=plan.uploader,
							duration=int(part_duration) if part_duration else None,
							caption=tr_user(user_id, "audio_ready_caption"),
							parse_mode="HTML",
						)
						await asyncio.sleep(0.7)  # to avoid hitting Telegram limits

				ctx.status = "success"
				ctx.delivery_method = f"telegram_split"
			except Exception as e:
				logger.exception("[downloader] failed sending split audio via Telegram")
				await bot.edit_message_text(
					chat_id=chat_id,
					message_id=message_id,
					text=tr_user(user_id, "failed_sending_audio"),
				)
				# log_download(
				# 	user_id=user_id,
				# 	video_url=url,
				# 	video_id=None,
				# 	video_title=plan.title,
				# 	duration_seconds=info.get("duration"),
				# 	chosen_bitrate=plan.bitrate,
				# 	estimated_size_mb=None,
				# 	real_size_mb=format_size_mb(real_size_mb),
				# 	processing_mode="yt-dlp",
				# 	processing_time_ms=None,
				# 	delivery_method="telegram",
				# 	status="failed",
				# 	error_message=str(e)[:500],
				# )
				ctx.delivery_method = "failed"
				ctx.status = "failed"
				ctx.error_message = str(e)[:500]
				ctx.fallback_reason = "sending_failed"

				return

	finally:
		cleanup_files(tmp_files)

		# temporary exit after Telegram send
		processing_time_ms = int((asyncio.get_event_loop().time() - start_ts) * 1000)
		ctx.processing_time_ms = processing_time_ms
		log_download(**ctx.__dict__)

		if ctx.status == "success":
			increment_downloads(ctx.user_id)
			logger.info("[downloader] audio sent to %s via Telegram successfully in %d ms", user_id, processing_time_ms)
		else:
			logger.info("[downloader] processing for %s failed after %d ms: %s", user_id, processing_time_ms, ctx.error_message)
		return
