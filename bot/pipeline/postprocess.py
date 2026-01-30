# SPLIT / CONVERT / TAG
# bot/pipeline/postprocess.py
import math
import asyncio

from pathlib import Path

from bot.downloaders.base import DownloadContext
from bot.config.telegram import (
	TELEGRAM_MAX_FILESIZE_MB,
)
from bot.config.downloaders import (
	AUDIO_BITRATE_PREFERRED,
	AUDIO_BITRATE_PREFERRED_ARG,
)

from .errors import PostProcessingFailed, PostProcessingNoDuration

def calculate_part_duration(duration: float, total_parts: int) -> float:
	return duration / total_parts

def calculate_parts(file_size_mb: float, part_size_mb: float = TELEGRAM_MAX_FILESIZE_MB) -> int:
	return math.ceil(file_size_mb / part_size_mb)

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
			raise PostProcessingFailed("ffmpeg split failed: " + stderr.decode("utf-8", errors="ignore"))

		parts.append(out_file)

	return parts

async def postprocess(ctx: DownloadContext):
	if not ctx.downloaded_files or len(ctx.downloaded_files) == 0:
		raise PostProcessingFailed("No downloaded files to process")
	
	file = ctx.downloaded_files[0]

	size_mb = file.stat().st_size / 1024 / 1024
	ctx.real_size_mb = round(size_mb, 2)

	if size_mb <= TELEGRAM_MAX_FILESIZE_MB:
		ctx.delivery_method = "telegram"
		return

	# 🔪 need split
	ctx.delivery_method = "telegram_split"

	duration = ctx.duration_seconds
	if duration is None or duration <= 0:
		raise PostProcessingNoDuration("Cannot split audio: duration unknown")
	
	total_parts = calculate_parts(size_mb, TELEGRAM_MAX_FILESIZE_MB)

	parts = await split_audio_by_time(
		src=file,
		out_dir=file.parent,
		part_duration=calculate_part_duration(duration, total_parts),
		total_parts=total_parts,
		prefix=file.stem,
		ext=file.suffix.lstrip("."),
	)

	ctx.output_files = parts

