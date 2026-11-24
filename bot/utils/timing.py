import logging
import time
from collections.abc import Callable

from bot.config.app import LOG_TIME


def log_duration(
	logger: logging.Logger,
	stage: str,
	started_at: float,
	**fields: object,
) -> None:
	if not LOG_TIME:
		return

	duration_ms = round((time.perf_counter() - started_at) * 1000)
	details = " ".join(
		f"{name}={value}"
		for name, value in fields.items()
		if value is not None
	)
	logger.info(
		"[timing] stage=%s duration_ms=%d%s",
		stage,
		duration_ms,
		f" {details}" if details else "",
	)


def create_ytdlp_download_hook(
	logger: logging.Logger,
	*,
	progress_callback: Callable[[int], None] | None = None,
	**fields: object,
):
	state: dict[str, object] = {}
	last_reported_percent: int | None = None
	last_reported_at = 0.0

	def hook(progress: dict) -> None:
		nonlocal last_reported_percent, last_reported_at
		if not LOG_TIME and progress_callback is None:
			return

		status = progress.get("status")
		now = time.perf_counter()
		if status == "downloading":
			state.setdefault("started_at", now)
			downloaded_bytes = progress.get("downloaded_bytes")
			total_bytes = (
				progress.get("total_bytes")
				or progress.get("total_bytes_estimate")
			)
			if (
				progress_callback is not None
				and isinstance(downloaded_bytes, int)
				and isinstance(total_bytes, int)
				and total_bytes > 0
			):
				percent = min(99, round(downloaded_bytes * 100 / total_bytes))
				if last_reported_percent is not None:
					percent = max(last_reported_percent, percent)
				if last_reported_percent is None or (
					percent - last_reported_percent >= 5
					and now - last_reported_at >= 10
				):
					last_reported_percent = percent
					last_reported_at = now
					progress_callback(percent)
		elif status == "finished":
			state["finished_at"] = now
			if progress_callback is not None and last_reported_percent != 100:
				last_reported_percent = 100
				progress_callback(100)

			if not LOG_TIME:
				return
			started_at = state.get("started_at")
			if not isinstance(started_at, float):
				return

			downloaded_bytes = progress.get("downloaded_bytes")
			elapsed_seconds = now - started_at
			average_speed = (
				round(downloaded_bytes / elapsed_seconds)
				if isinstance(downloaded_bytes, int) and elapsed_seconds > 0
				else None
			)
			log_duration(
				logger,
				"youtube_transfer",
				started_at,
				**fields,
				downloaded_bytes=downloaded_bytes,
				average_bytes_per_second=average_speed,
			)

	return hook, state
