import re
import asyncio
import logging
import uuid
import json
import yt_dlp # type: ignore

from typing import Literal
from dataclasses import dataclass

from pathlib import Path
from typing import Dict

from telegram import Bot  # type: ignore
from telegram.error import TelegramError  # type: ignore

from bot.db.db import increment_downloads, log_download
from bot.i18n.helpers import tr_user

from bot.config.downloader import (
	AUDIO_DIR,
	AUDIO_FORMAT_PREFERRED,	
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
class DownloadPlan:
	tmp_id: str
	mode: Literal["fast_audio", "slow_audio"]
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

def ydl_fast_audio_opts(plan: DownloadPlan):
	return {
		**ydl_base_opts(),
		"format": "bestaudio[ext=m4a]/bestaudio",
		"outtmpl": str(plan.out_dir / f"{plan.tmp_id}.%(ext)s"),
		"postprocessors": [],
	}

def ydl_slow_audio_opts(plan: DownloadPlan):
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

async def ytdlp_download_with_retry(
	url: str,
	opts: dict,
):
	for attempt in range(1, YTDLP_RETRIES + 1):
		try:
			return await asyncio.to_thread(
				lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=True)
			)

		except Exception as e:
			logger.warning(f"[downloader] yt-dlp attempt {attempt} failed: {e}")
			# --- fatal or retries exhausted ---
			raise


def safe_filename(text: str) -> str:
	text = text.strip()
	text = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
	text = re.sub(r"\s+", "_", text)
	return text[:MAX_FILENAME_LENGTH] or "audio"



async def process_job(job: Dict, bot: Bot):
	logger.info("[downloader] received job")

	user_id: int = job["user_id"]
	chat_id: int = job["chat_id"]
	message_id: int = job["message_id"]
	url: str = job["url"]

	tmp_id = uuid.uuid4().hex
	out_tpl = AUDIO_DIR / f"{tmp_id}.%(ext)s"

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
	
	if info.get("duration") and info["duration"] > MAX_DURATION_SECONDS:
		logger.warning("[downloader] video duration exceeds limit")
		await bot.edit_message_text(
			chat_id=chat_id,
			message_id=message_id,
			text=tr_user(user_id, "duration_exceeds_limit").format(max_duration=MAX_DURATION_SECONDS),
		)
		return
	
	mode = "fast_audio" if can_use_fast_mode(info) else "slow_audio"

	plan = DownloadPlan(
		tmp_id=tmp_id,
		mode=mode,
		title=info.get("title", "audio"),
		uploader=info.get("uploader") or info.get("artist") or info.get("channel") or "YouTube",
		bitrate=AUDIO_BITRATE_PREFERRED_ARG,
		out_dir=AUDIO_DIR,
	)

	opts = (
		ydl_fast_audio_opts
		if plan.mode == "fast_audio"
		else ydl_slow_audio_opts(plan)
	)


	# download audio
	try:
		await bot.edit_message_text(
			chat_id=chat_id,
			message_id=message_id,
			text=tr_user(user_id, "downloading_audio"),
		)
	except TelegramError as e:
		logger.warning(f"[downloader] notify failed: {e}")
	except Exception as e:
		logger.exception("[downloader] unexpected error during notify")

	try:
		await ytdlp_download_with_retry(
			url=url,
			opts=opts(plan) if callable(opts) else opts,
		)

		files = list(AUDIO_DIR.glob(f"{tmp_id}.*"))
		if not files:
			raise RuntimeError("yt-dlp finished but no files found")
		
		tmp_path = files[0]

		real_size_mb = round(tmp_path.stat().st_size / 1024 / 1024 , 2)
		logger.debug(f"[downloader] downloaded file size: {real_size_mb} MB")

	except Exception as e:
		logger.exception("[downloader] failed downloading audio")
		await bot.edit_message_text(
			chat_id=chat_id,
			message_id=message_id,
			text=tr_user(user_id, "failed_download"),
		)
		log_download(
			user_id=user_id,
			video_url=url,
			video_id=None,
			video_title=None,
			duration_seconds=None,
			chosen_bitrate=plan.bitrate,
			estimated_size_mb=None,
			real_size_mb=None,
			processing_mode="yt-dlp",
			processing_time_ms=None,
			delivery_method="failed",
			status="failed",
			error_message=str(e)[:500],
		)
		return
	


	# Telegram send audio
	if real_size_mb <= TELEGRAM_MAX_FILESIZE_MB:
		try:
			with open(tmp_path, "rb") as audio_f:
				await bot.send_audio(
					chat_id=chat_id,
					audio=audio_f,
					filename=safe_filename(plan.title) + f".{AUDIO_FORMAT_PREFERRED}",
					title=plan.title,
					performer=plan.uploader,
					duration=info.get("duration"),
					caption=tr_user(user_id, "audio_ready_caption"),
					parse_mode="HTML",
				)
		except Exception as e:
			logger.exception("[downloader] failed sending audio via Telegram")
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=tr_user(user_id, "failed_sending_audio"),
			)
			log_download(
				user_id=user_id,
				video_url=url,
				video_id=None,
				video_title=plan.title,
				duration_seconds=info.get("duration"),
				chosen_bitrate=plan.bitrate,
				estimated_size_mb=None,
				real_size_mb=real_size_mb,
				processing_mode="yt-dlp",
				processing_time_ms=None,
				delivery_method="telegram",
				status="failed",
				error_message=str(e)[:500],
			)
			return



	# temporary exit after Telegram send
	logger.info("[downloader] audio sent via Telegram")
	return

	
	# # --- legacy: subprocess yt-dlp ---

	# cmd = [
	# 	"yt-dlp",
	# 	"-f", "bestaudio",
	# 	"--extract-audio",
	# 	"--audio-format", "mp3",
	# 	"--audio-quality", "192K",
	# 	"--no-playlist",
	# 	"--write-info-json",
	# 	"--cookies", "/cookies.txt",
	# 	"-o", str(out_tpl),
	# 	url,
	# ]	

	# proc = await asyncio.create_subprocess_exec(
	# 	*cmd,
	# 	stdout=asyncio.subprocess.PIPE,
	# 	stderr=asyncio.subprocess.PIPE,
	# )

	# stdout, stderr = await proc.communicate()

	# if proc.returncode != 0:
	# 	err = stderr.decode("utf-8", errors="ignore")

	# 	await bot.edit_message_text(
	# 		chat_id=chat_id,
	# 		message_id=message_id,
	# 		text=tr_user(user_id, "failed_download"),
	# 	)

	# 	log_download(
	# 		user_id=user_id,
	# 		video_url=url,
	# 		video_id=None,
	# 		video_title=None,
	# 		duration_seconds=None,
	# 		chosen_bitrate=192,
	# 		estimated_size_mb=None,
	# 		real_size_mb=None,
	# 		processing_mode="yt-dlp",
	# 		processing_time_ms=None,
	# 		delivery_method="failed",
	# 		status="failed",
	# 		error_message=err[:500],
	# 	)
	# 	return

	# parse metadata
	# lines = stdout.decode("utf-8", errors="ignore").splitlines()
	# title = lines[0] if len(lines) > 0 else "audio"
	# duration_seconds = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else None
	# file_info = list(AUDIO_DIR.glob(f"{tmp_id}.info.json"))
	# if not file_info:
	# 	raise RuntimeError("yt-dlp finished but info.json not found")
	
	# with open(file_info[0], "r", encoding="utf-8") as f:
	# 	info = json.load(f)

	# logger.debug(f"[downloader] yt-dlp info: {info}")

	# title = info.get("title", "audio")
	# author = info.get("uploader") or info.get("artist") or info.get("channel") or "YouTube"
	# duration_seconds = info.get("duration")
	# if not isinstance(duration_seconds, int):
	# 	duration_seconds = None


	# filename = f"{safe_filename(title)}.mp3"

	# # find file
	# files = list(AUDIO_DIR.glob(f"{tmp_id}.*"))
	# if not files:
	# 	raise RuntimeError("yt-dlp finished but file not found")

	# audio_file = files[0]
	# size_mb = audio_file.stat().st_size / 1024 / 1024
	# processing_ms = int((asyncio.get_event_loop().time() - start_ts) * 1000)

	# file_link = f"https://example.com/downloads/{audio_file.name}"

	# send audio
	with open(audio_file, "rb") as f:
		await bot.send_audio(
			chat_id=chat_id,
			audio=f,
			filename=filename,
			title=title,
			performer=author,
			duration=duration_seconds,
			caption=tr_user(user_id, "audio_ready_caption"),
			parse_mode="HTML",
		)

	await bot.edit_message_text(
		chat_id=chat_id,
		message_id=message_id,
		text="✅ Done",
	)

	increment_downloads(user_id)

	log_download(
		user_id=user_id,
		video_url=url,
		video_id=None,
		video_title=title,
		duration_seconds=duration_seconds,
		chosen_bitrate=192,
		estimated_size_mb=None,
		real_size_mb=round(size_mb, 2),
		processing_mode="yt-dlp",
		processing_time_ms=processing_ms,
		delivery_method="telegram",
		status="success",
		file_path=str(audio_file),
	)

	logger.info("[downloader] job finished successfully")
