# bot/utils/format.py
from math import ceil, isfinite
from typing import Optional


def format_duration(seconds: Optional[int]) -> str:
	if not seconds or seconds <= 0:
		return "—"

	hours, remainder = divmod(seconds, 3600)
	minutes, _ = divmod(remainder, 60)

	if hours > 0:
		return f"{hours:02d} h {minutes:02d} min"

	return f"{minutes:02d} min"

def format_size_mb(size_mb: Optional[float]) -> str:
	if size_mb is None:
		return "—"
	return f"{size_mb:.1f} MB"


def format_size_bytes(size_bytes: Optional[int | float]) -> Optional[str]:
	if (
		not isinstance(size_bytes, (int, float))
		or not isfinite(size_bytes)
		or size_bytes < 0
	):
		return None

	size = float(size_bytes)
	units = ("B", "KiB", "MiB", "GiB", "TiB")
	for unit in units:
		if size < 1024 or unit == units[-1]:
			if unit == "B":
				return f"{int(size)} {unit}"
			return f"{size:.1f} {unit}"
		size /= 1024

	return None


def format_eta(seconds: Optional[int | float]) -> Optional[str]:
	if (
		not isinstance(seconds, (int, float))
		or not isfinite(seconds)
		or seconds < 0
	):
		return None

	remaining = ceil(seconds)
	if remaining < 60:
		return f"{remaining} sec"

	minutes, seconds = divmod(remaining, 60)
	hours, minutes = divmod(minutes, 60)
	if hours:
		return f"{hours} h {minutes} min"
	if seconds:
		return f"{minutes} min {seconds} sec"
	return f"{minutes} min"


def fmt_int(value: Optional[float | int]) -> str:
	if value is None:
		return "—"
	return f"{int(value):,}".replace(",", " ")