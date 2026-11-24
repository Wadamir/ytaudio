# bot/downloaders/youtube.py
import yt_dlp # type: ignore
import asyncio
import logging
import random
import time

from pathlib import Path
from typing import Dict, Literal, Optional
from dataclasses import dataclass

from bot.config.downloaders import *
from bot.config.network import (
	YT_PROXY_TYPE,
	YTDLP_JS_RUNTIME_PATH,
	get_alternate_proxy_type,
	get_proxy_candidates,
)

from bot.transport.strategy import iter_routes
from bot.transport.state import mark_403, mark_success
from bot.transport.exceptions import is_route_format_error
from bot.utils.timing import create_ytdlp_download_hook, log_duration

from .base import BaseDownloader, DownloadContext
from .errors import (
	DownloaderError,
	VideoUnavailable,
	LiveStreamNotSupported,
	VideoTooLong,
	DownloadFailed,
	FetchInfoFailed,
	NoUnencryptedAudioFormat,
	YouTubeAuthRequired,
	is_browser_auth_required,
)
from .stages import DownloadStage
from .utils import notify


logger = logging.getLogger(__name__)


def preferred_youtube_proxy() -> str | None:
	candidates = get_proxy_candidates(YT_PROXY_TYPE)
	if not candidates:
		candidates = get_proxy_candidates(get_alternate_proxy_type(YT_PROXY_TYPE))
	return candidates[0][1] if candidates else None


yt_errors = ["youtube_403", "youtube_429", "youtube_503", "youtube_sabr"]


USER_AGENT_PROFILES = {
	"desktop_chrome": {
		"user_agent": (
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
			"AppleWebKit/537.36 (KHTML, like Gecko) "
			"Chrome/120.0.0.0 Safari/537.36"
		),
	},
	"android": {
		"user_agent": (
			"Mozilla/5.0 (Linux; Android 13; Pixel 7) "
			"AppleWebKit/537.36 (KHTML, like Gecko) "
			"Chrome/120.0.0.0 Mobile Safari/537.36"
		),
	},
	"ios": {
		"user_agent": (
			"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
			"AppleWebKit/605.1.15 (KHTML, like Gecko) "
			"Version/17.0 Mobile/15E148 Safari/604.1"
		),
	},
}


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

	@staticmethod
	def _is_youtube_block_error(error: Exception) -> bool:
		message = str(error).lower()
		return any(marker in message for marker in (
			"403",
			"429",
			"forbidden",
			"too many requests",
			"confirm you're not a bot",
			"sign in to confirm",
		))

	@staticmethod
	def _is_route_connection_error(error: Exception) -> bool:
		message = str(error).lower()
		return any(marker in message for marker in (
			"proxyerror",
			"proxy error",
			"proxy authentication",
			"407",
			"socks5",
			"malformed reply",
			"invalid response version",
			"expected 05 got 00",
			"connection refused",
			"connection reset",
			"connection aborted",
			"connection timed out",
			"timed out",
			"timeout",
			"temporary failure",
			"name or service not known",
			"failed to resolve",
			"getaddrinfo failed",
			"network is unreachable",
			"no route to host",
			"unable to connect",
			"unable to establish",
			"remote end closed connection",
			"tunnel connection failed",
			"sslerror",
			"ssl:",
			"tls",
			"502",
			"503",
			"504",
		))

	def can_handle(self, url: str) -> bool:
		from urllib.parse import urlparse

		try:
			parsed = urlparse(url.strip())
		except (TypeError, ValueError):
			return False

		if parsed.scheme not in {"http", "https"}:
			return False

		host = (parsed.hostname or "").lower().rstrip(".")
		return (
			host == "youtube.com"
			or host.endswith(".youtube.com")
			or host == "youtu.be"
		)

	@staticmethod
	def _has_audio_format(info: Dict) -> bool:
		formats = info.get("formats")
		return isinstance(formats, list) and any(
			isinstance(format_info, dict)
			and format_info.get("acodec") not in (None, "none")
			for format_info in formats
		)
	
	def _extract_info_with_strategy(self, url: str, ctx: DownloadContext):
		# Validate local cookie configuration before trying the persisted route.
		try:
			logger.info("=== PRE-FLIGHT COOKIE CONFIG DIAGNOSTICS ===")

			try:
				cookie_file = YTDLP_COOKIES_PATH
				if not cookie_file.exists():
					logger.error("[diag] Active cookies file is missing at %s", cookie_file)
				elif cookie_file.stat().st_size == 0:
					logger.error("[diag] Active cookies file is empty")
				else:
					with open(cookie_file, "r") as f:
						first_line = f.readline().strip()
					if "netscape" in first_line.lower() or "cookie" in first_line.lower():
						logger.info("[diag] cookies.txt layout verified successfully (Netscape format detected)")
					else:
						logger.warning("[diag] Active cookies file lacks a Netscape header")
			except Exception as e:
				logger.error("[diag] Failed to read or parse cookies.txt file mapping layout: %s", e)

			logger.info("==============================================")
		except Exception as diag_global_err:
			logger.error("[diag-global] Diagnostic sequence interrupted: %s", diag_global_err)

		last_route_error: Exception | None = None
		last_auth_error: Exception | None = None
		for route in iter_routes():
			logger.info(
				"[downloader] Trying to fetch info via route: %s (proxy=%s)",
				route.key,
				"yes" if route.proxy else "no",
			)
			route_started_at = time.perf_counter()
			route_result = "error"
			try:
				opts = self._base_opts(ctx)

				if route.proxy:
					opts["proxy"] = route.proxy
				else:
					opts.pop("proxy", None)

				info = yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
				if not self._has_audio_format(info):
					raise yt_dlp.utils.DownloadError(
						"Only images are available for download"
					)
				ctx.transport_route = route.key
				ctx.transport_proxy = route.proxy
				route_result = "success"
				return info

			except yt_dlp.utils.DownloadError as e:
				if is_browser_auth_required(e):
					last_auth_error = e
				if self._is_youtube_block_error(e):
					mark_403(route.key)
					logger.warning(
						"[downloader] route %s was rejected by YouTube; trying next route",
						route.key,
					)
					continue
				if self._is_route_connection_error(e):
					logger.warning(
						"[downloader] route %s connection failed (%s); trying next route",
						route.key,
						type(e).__name__,
					)
					last_route_error = e
					continue
				if is_route_format_error(e):
					logger.warning(
						"[downloader] route %s returned no usable formats; trying next route",
						route.key,
					)
					last_route_error = e
					continue
				raise
			except OSError as e:
				if not self._is_route_connection_error(e):
					raise
				logger.warning(
					"[downloader] route %s connection failed (%s); trying next route",
					route.key,
					type(e).__name__,
				)
				last_route_error = e
				continue
			finally:
				log_duration(
					logger,
					"youtube_info_route",
					route_started_at,
					route=route.key,
					result=route_result,
				)

		if last_auth_error:
			raise YouTubeAuthRequired(
				f"YouTube requires browser authorization: {last_auth_error}"
			) from last_auth_error
		if last_route_error:
			raise last_route_error
		raise FetchInfoFailed("All transport routes failed")

	def _pick_ua_profile(self) -> str:
		# For future use: pick different UA profiles based on some criteria
		# 70% desktop
		# 20% android
		# 10% ios
		roll = random.random()
		if roll < 0.7:
			return "desktop_chrome"
		elif roll < 0.9:
			return "android"
		else:
			return "ios"
		
	def _base_opts(self, ctx: Optional[DownloadContext] = None):
		if ctx.ua_profile:
			ua_profile = ctx.ua_profile
		else:
			ua_profile = self._pick_ua_profile()
			ctx.ua_profile = ua_profile

		profile = USER_AGENT_PROFILES.get(ua_profile, USER_AGENT_PROFILES["desktop_chrome"])

		if ctx:
			ctx.ua_profile = ua_profile

		opts = {
			"cookiefile": str(YTDLP_COOKIES_PATH),
			"quiet": True,
			"socket_timeout": 30,
			"retries": YTDLP_RETRIES,
			"fragment_retries": 3,
			"skip_unavailable_fragments": True,
			"noplaylist": YTDLP_NO_PLAYLIST,
			"js_runtimes": {
				"node": {
					"path": YTDLP_JS_RUNTIME_PATH
				}
			},
			"remote_components": ["ejs:github"],
			"concurrent_fragment_downloads": 1,
			"sleep_interval": 1,
			"max_sleep_interval": 5,
			"http_headers": {
				"Connection": "close",
				"User-Agent": profile["user_agent"]
			},		
			"extractor_args": {
				"youtube": {
					"player_client": ["web", "android"],
				},
				"youtubepot-bgutilhttp": {
					"base_url": ["http://bgutil-provider:4416"],
				}
			},
		}		

		if ctx and ctx.transport_route == "direct":
			opts.pop("proxy", None)
		elif ctx and ctx.transport_proxy:
			opts["proxy"] = ctx.transport_proxy
		elif proxy_url := preferred_youtube_proxy():
			opts["proxy"] = proxy_url

		return opts

	def _fast_mode_opts(self, plan: DownloadPlan, ctx: DownloadContext):
		return {
			**self._base_opts(ctx),
			"format": "bestaudio[ext=m4a]/bestaudio",
			"outtmpl": str(plan.out_dir / f"{plan.tmp_id}.%(ext)s"),
			"postprocessors": [],
		}

	def _slow_mode_opts(self, plan: DownloadPlan, ctx: DownloadContext):
		return {
			**self._base_opts(ctx),
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
				if "drm protected" in str(e).lower():
					raise NoUnencryptedAudioFormat(
						"No unencrypted audio format is available"
					) from e
				if self._is_youtube_block_error(e) or self._is_route_connection_error(e):
					raise
				last_exc = e
				logger.warning(
					f"[downloader] yt-dlp attempt {attempt}/{YTDLP_RETRIES} failed: {e}"
				)

		raise last_exc

	@staticmethod
	def _cleanup_partial_download(plan: DownloadPlan) -> None:
		for path in plan.out_dir.glob(f"{plan.tmp_id}.*"):
			if not path.is_file():
				continue
			try:
				path.unlink(missing_ok=True)
			except OSError as e:
				logger.warning(
					"[downloader] could not remove partial output (%s)",
					type(e).__name__,
				)

	async def _download_with_routes(
		self,
		url: str,
		plan: DownloadPlan,
		ctx: DownloadContext,
	) -> None:
		routes = list(iter_routes())
		for index, route in enumerate(routes):
			if route.key == ctx.transport_route:
				routes.insert(0, routes.pop(index))
				break

		if not routes:
			raise DownloadFailed("No transport routes are available")

		last_route_error: Exception | None = None
		for route in routes:
			ctx.transport_route = route.key
			ctx.transport_proxy = route.proxy
			route_started_at = time.perf_counter()
			route_result = "error"
			opts = (
				self._fast_mode_opts(plan, ctx)
				if plan.mode == "fast_mode"
				else self._slow_mode_opts(plan, ctx)
			)
			progress_hook, transfer_state = create_ytdlp_download_hook(
				logger,
				progress_callback=lambda progress: notify(
					ctx,
					DownloadStage.DOWNLOADING,
					{
						"processing_mode": plan.mode,
						"duration_seconds": ctx.duration_seconds,
						**progress,
					},
				),
				route=route.key,
				mode=plan.mode,
				video_id=ctx.video_id,
			)
			opts.setdefault("progress_hooks", []).append(progress_hook)

			try:
				await self._download_with_retry(url, opts)
				mark_success(route.key)
				route_result = "success"
				return
			except NoUnencryptedAudioFormat:
				raise
			except Exception as e:
				format_error = is_route_format_error(e)
				if not (
					self._is_youtube_block_error(e)
					or self._is_route_connection_error(e)
					or format_error
				):
					raise

				if self._is_youtube_block_error(e):
					mark_403(route.key)
				if format_error:
					logger.warning(
						"[downloader] download route %s returned no usable formats; trying next route",
						route.key,
					)
				else:
					logger.warning(
						"[downloader] download route %s failed (%s); trying next route",
						route.key,
						type(e).__name__,
					)
				last_route_error = e
				self._cleanup_partial_download(plan)
			finally:
				transfer_finished_at = transfer_state.get("finished_at")
				if (
					plan.mode == "slow_mode"
					and isinstance(transfer_finished_at, (int, float))
					and route_result == "success"
				):
					log_duration(
						logger,
						"youtube_transcode",
						transfer_finished_at,
						route=route.key,
						mode=plan.mode,
						video_id=ctx.video_id,
					)
				log_duration(
					logger,
					"youtube_download_route",
					route_started_at,
					route=route.key,
					mode=plan.mode,
					video_id=ctx.video_id,
					result=route_result,
				)

		if last_route_error:
			raise last_route_error
		raise DownloadFailed("All transport routes failed")
	
	# async def _fetch_info(self, url: str, ctx: DownloadContext) -> Dict:
	# 	opts = self._base_opts(ctx)
	# 	opts["skip_download"] = True
	# 	return await asyncio.to_thread(
	# 		lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
	# 	)

		
	async def download(self, url: str, ctx:DownloadContext):
		# 0. Notify start
		notify(ctx, DownloadStage.FETCHING_INFO)

		# 1. Get info
		info_started_at = time.perf_counter()
		try:
			# info = await self._fetch_info(url, ctx)		
			# new with strategy
			info = await asyncio.to_thread(
				lambda: self._extract_info_with_strategy(url, ctx)
			)
		except FetchInfoFailed:
			raise
		except Exception as e:
			if "unavailable" in str(e).lower() or "not available" in str(e).lower():
				raise VideoUnavailable(f"Video is unavailable: {e}") from e
			else:
				raise FetchInfoFailed(f"Failed to get video info: {e}") from e
		finally:
			log_duration(
				logger,
				"youtube_info",
				info_started_at,
				video_id=ctx.video_id,
				route=ctx.transport_route,
			)
		
		# 2. Validation (live / duration / unavailable)
		if info.get("is_live"):
			raise LiveStreamNotSupported("Live streams are not supported")
		
		duration = info.get("duration")
		if not isinstance(duration, int):
			duration = None

		ctx.video_id = info.get("id")
		ctx.video_title = info.get("title")			
		ctx.video_artist = info.get("uploader") or info.get("artist") or info.get("channel") or "YouTube"
		ctx.duration_seconds = duration

		if duration and duration > MAX_DURATION_SECONDS:
			raise VideoTooLong("Video duration exceeds allowed limit")
		
		notify(ctx, DownloadStage.INFO_READY,
			{"duration_seconds": duration}
		)		
		
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

		# 5. yt-dlp download (preferred route, then protocol fallback)
		try:
			notify(ctx, DownloadStage.DOWNLOADING,
				{
					"duration_seconds": duration,
					"processing_mode": ctx.processing_mode,
					"chosen_bitrate": ctx.chosen_bitrate,
					"estimated_size_mb": ctx.estimated_size_mb,
				}   
			)

			download_started_at = time.perf_counter()
			try:
				await self._download_with_routes(url, plan, ctx)
			finally:
				log_duration(
					logger,
					"youtube_download",
					download_started_at,
					video_id=ctx.video_id,
					mode=plan.mode,
					route=ctx.transport_route,
				)

			files = list(plan.out_dir.glob(f"{plan.tmp_id}.*"))
			if not files:
				raise DownloadFailed("No output files found after download")
			
			ctx.downloaded_files = files

		except NoUnencryptedAudioFormat:
			raise
		except Exception as e:
			raise DownloadFailed(f"Download failed after retries: {e}") from e
		
		# 6. Done
		notify(ctx, DownloadStage.FINISHED)

