# bot/utils/format.py
from typing import Optional
import re


def format_duration(seconds: Optional[int]) -> str:
	if not seconds or seconds <= 0:
		return "—"

	hours, remainder = divmod(seconds, 3600)
	minutes, _ = divmod(remainder, 60)

	if hours > 0:
		return f"{hours:02d}:{minutes:02d}"

	return f"{minutes:02d} min"


def format_size_mb(size_mb: Optional[float]) -> str:
	if size_mb is None:
		return "—"
	return f"{size_mb:.1f} MB"


def safe_filename(text: str, max_len: int = 150) -> str:
	text = re.sub(r'[\\/*?:"<>|]', "", text)
	text = re.sub(r"\s+", " ", text).strip()
	return text[:max_len]
