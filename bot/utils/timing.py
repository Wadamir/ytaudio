import logging
import time

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
	**fields: object,
):
	state: dict[str, object] = {}

	def hook(progress: dict) -> None:
		if not LOG_TIME:
			return

		status = progress.get("status")
		now = time.perf_counter()
		if status == "downloading":
			state.setdefault("started_at", now)
		elif status == "finished":
			state["finished_at"] = now
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
