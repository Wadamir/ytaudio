# bot/downloaders/youtube.py
import os
import yt_dlp # type: ignore
import asyncio
import logging

from pathlib import Path
from typing import Dict, Literal, Optional
from dataclasses import dataclass

from bot.db.db import count_youtube_errors_last_minutes

from bot.config.downloaders import *
from bot.config.network import PRIMARY_IPv4, SECONDARY_IPv4

from .base import BaseDownloader, DownloadContext
from .errors import DownloaderError, VideoUnavailable, LiveStreamNotSupported, VideoTooLong, DownloadFailed, FetchInfoFailed
from .stages import DownloadStage
from .utils import notify


logger = logging.getLogger(__name__)



yt_errors = ["youtube_403", "youtube_429", "youtube_503", "youtube_sabr"]

@dataclass
class DownloadPlan:
	tmp_id: str
	mode: Literal["fast_mode", "slow_mode"]
	title: str
	uploader: str
	bitrate: int
	out_dir: Path



class YouTubeDownloader(BaseDownloader):
	name = "youtube"

	def can_handle(self, url: str) -> bool:
		return "youtube.com" in url or "youtu.be" in url
	
	def _should_use_secondary_ip(self) -> bool:
		return (
			count_youtube_errors_last_minutes(
				error_type=yt_errors,
				minutes=YT_UNAVAILABLE_TIMEFRAME_MINUTES,
			) >= YT_UNAVAILABLE_MAX_ERRORS
		)

	def _base_opts(self):
		opts = {
			"cookies": str(YTDLP_COOKIES_PATH),
			"quiet": True,
			"socket_timeout": 30,
			"retries": YTDLP_RETRIES,
			"fragment_retries": 3,
			"noplaylist": YTDLP_NO_PLAYLIST,
			"js_runtime": ["node"],
			"concurrent_fragment_downloads": 1,
			"sleep_interval": 1,
			"max_sleep_interval": 5,
			"http_headers": {
				"User-Agent": (
					"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
					"AppleWebKit/537.36 (KHTML, like Gecko) "
					"Chrome/120.0.0.0 Safari/537.36"
				)
			},		
		}
		if os.getenv("APP_ENV") == "prod":
			if self._should_use_secondary_ip():
				logger.info("[downloader] Using secondary IP for yt-dlp")
				opts["source_address"] = SECONDARY_IPv4
			else:
				opts["source_address"] = PRIMARY_IPv4

		return opts

	def _fast_mode_opts(self, plan: DownloadPlan):
		return {
			**self._base_opts(),
			"format": "bestaudio[ext=m4a]/bestaudio",
			"outtmpl": str(plan.out_dir / f"{plan.tmp_id}.%(ext)s"),
			"postprocessors": [],
		}

	def _slow_mode_opts(self, plan: DownloadPlan):
		return {
			**self._base_opts(),
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

	def _can_use_fast_mode(self, info: Dict) -> bool:
		for f in info.get("formats", []):
			if f.get("ext") != "m4a":
				continue
			if f.get("acodec") != "mp4a.40.2":
				continue

			size = f.get("filesize") or f.get("filesize_approx")
			if size and size / 1024 / 1024 <= MAX_FILE_SIZE_MB:
				return True
		return False

	async def _download_with_retry(self, url: str, opts: dict):
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
	
	async def _fetch_info(self, url: str) -> Dict:
		opts = self._base_opts()
		opts["skip_download"] = True
		return await asyncio.to_thread(
			lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
		)

		
	async def download(self, url: str, ctx:DownloadContext):
		# 0. Notify start
		notify(ctx, DownloadStage.FETCHING_INFO)

		# 1. Get info
		try:
			info = await self._fetch_info(url)		
		except Exception as e:
			if "unavailable" in str(e).lower() or "not available" in str(e).lower():
				raise VideoUnavailable(f"Video is unavailable: {e}") from e
			else:
				raise FetchInfoFailed(f"Failed to get video info: {e}") from e
		
		# 2. Validation (live / duration / unavailable)
		if info.get("is_live"):
			raise LiveStreamNotSupported("Live streams are not supported")
		
		duration = info.get("duration")
		if not isinstance(duration, int):
			duration = None

		ctx.video_id = info.get("id")
		ctx.video_title = info.get("title")			
		ctx.duration_seconds = duration

		notify(ctx, DownloadStage.INFO_READY,
			{"duration_seconds": duration}
		)

		if duration and duration > MAX_DURATION_SECONDS:
			raise VideoTooLong("Video duration exceeds allowed limit")
		
		# 3. Fast/Slow
		use_fast_mode = self._can_use_fast_mode(info)
		if use_fast_mode:
			ctx.processing_mode = "fast_mode"
		else:
			ctx.processing_mode = "slow_mode"

		# 4. Building DownloadPlan
		plan = DownloadPlan(
			tmp_id = f"{ctx.user_id}_{int(asyncio.get_event_loop().time() * 1000)}",
			mode = "fast_mode" if use_fast_mode else "slow_mode",
			title = info.get("title", "unknown_title"),
			uploader = info.get("uploader") or info.get("artist") or info.get("channel") or "YouTube",
			bitrate = AUDIO_BITRATE_PREFERRED if not use_fast_mode else 128,
			out_dir = AUDIO_DIR,
		)
		ctx.chosen_bitrate = plan.bitrate
		ctx.estimated_size_mb = info.get("filesize") / 1024 / 1024 if info.get("filesize") else None

		notify(ctx, DownloadStage.STARTING_DOWNLOAD,
			{
				"duration_seconds": duration,
				"processing_mode": ctx.processing_mode,
				"chosen_bitrate": ctx.chosen_bitrate,
				"estimated_size_mb": ctx.estimated_size_mb,
			}
		)

		# 5. yt-dlp download (with retry)
		if plan.mode == "fast_mode":
			opts = self._fast_mode_opts(plan)
		else:
			opts = self._slow_mode_opts(plan)
		
		try:
			notify(ctx, DownloadStage.DOWNLOADING)

			await self._download_with_retry(url, opts)

			files = list(plan.out_dir.glob(f"{plan.tmp_id}.*"))
			if not files:
				raise DownloadFailed("No output files found after download")
			
			ctx.downloaded_files = files

		except Exception as e:
			raise DownloadFailed(f"Download failed after retries: {e}") from e
		
		# 6. Done
		notify(ctx, DownloadStage.FINISHED)

