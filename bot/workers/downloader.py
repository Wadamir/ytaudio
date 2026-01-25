import re
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict

from telegram import Bot  # type: ignore

from bot.db.db import increment_downloads, log_download
from bot.i18n.helpers import tr_user

logger = logging.getLogger(__name__)

AUDIO_DIR = Path("/storage/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(text: str) -> str:
	text = text.strip()
	text = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
	text = re.sub(r"\s+", "_", text)
	return text[:150] or "audio"


async def process_job(job: Dict, bot: Bot):
	logger.info("[downloader] received job")

	user_id: int = job["user_id"]
	chat_id: int = job["chat_id"]
	message_id: int = job["message_id"]
	url: str = job["url"]

	tmp_id = uuid.uuid4().hex
	out_tpl = AUDIO_DIR / f"{tmp_id}.%(ext)s"

	# notify user
	await bot.edit_message_text(
		chat_id=chat_id,
		message_id=message_id,
		text=tr_user(user_id, "reading_info"),
	)

	start_ts = asyncio.get_event_loop().time()

	cmd = [
		"yt-dlp",
		"-f", "bestaudio",
		"--extract-audio",
		"--audio-format", "mp3",
		"--audio-quality", "192K",
		"--no-playlist",
		"--print", "title",
		"--print", "duration",
		"--cookies", "/cookies.txt",
		"-o", str(out_tpl),
		url,
	]

	proc = await asyncio.create_subprocess_exec(
		*cmd,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE,
	)

	stdout, stderr = await proc.communicate()

	if proc.returncode != 0:
		err = stderr.decode("utf-8", errors="ignore")

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
			chosen_bitrate=192,
			estimated_size_mb=None,
			real_size_mb=None,
			processing_mode="yt-dlp",
			processing_time_ms=None,
			delivery_method="failed",
			status="failed",
			error_message=err[:500],
		)
		return

	# parse metadata
	lines = stdout.decode("utf-8", errors="ignore").splitlines()
	title = lines[0] if len(lines) > 0 else "audio"
	duration_seconds = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else None

	filename = f"{safe_filename(title)}.mp3"

	# find file
	files = list(AUDIO_DIR.glob(f"{tmp_id}.*"))
	if not files:
		raise RuntimeError("yt-dlp finished but file not found")

	audio_file = files[0]
	size_mb = audio_file.stat().st_size / 1024 / 1024
	processing_ms = int((asyncio.get_event_loop().time() - start_ts) * 1000)

	file_link = f"https://example.com/downloads/{audio_file.name}"

	# send audio
	with open(audio_file, "rb") as f:
		await bot.send_audio(
			chat_id=chat_id,
			audio=f,
			filename=filename,
			caption=tr_user(user_id, "audio_ready_caption"),
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
