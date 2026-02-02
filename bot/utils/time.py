# bot/utils/time.py
from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


def utc_now_iso() -> str:
	return utc_now().isoformat()


def utc_today_iso() -> str:
	return utc_now().date().isoformat()


def time_until_utc_reset() -> str:
	now = utc_now()
	tomorrow = (now + timedelta(days=1)).date()
	reset_at = datetime.combine(
		tomorrow,
		datetime.min.time(),
		tzinfo=timezone.utc
	)

	delta = reset_at - now
	total_seconds = int(delta.total_seconds())

	hours, remainder = divmod(total_seconds, 3600)
	minutes = remainder // 60

	if hours > 0:
		return f"{hours}h {minutes}m"
	return f"{minutes}m"


def time_ago_from_iso(ts: str) -> str:
	dt = datetime.fromisoformat(ts)
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)

	now = datetime.now(timezone.utc)
	delta = now - dt

	seconds = int(delta.total_seconds())

	if seconds < 60:
		return f"{seconds}s ago"

	minutes = seconds // 60
	if minutes < 60:
		return f"{minutes} min ago"

	hours = minutes // 60
	if hours < 24:
		return f"{hours} h ago"

	days = hours // 24
	return f"{days} d ago"


def parse_iso_datetime(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
    
