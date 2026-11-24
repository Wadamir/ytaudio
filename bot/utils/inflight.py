import time
from asyncio import Lock
from typing import TypedDict, Tuple, List, Dict
from urllib.parse import parse_qs, urlsplit

_lock = Lock()

class InflightEntry(TypedDict):
	started_at: float
	messages: List[int]

_inflight: Dict[Tuple[int, str], InflightEntry] = {}


def canonical_inflight_key(url: str) -> str:
	normalized_url = url.strip()
	try:
		parsed = urlsplit(normalized_url)
	except ValueError:
		return normalized_url

	host = (parsed.hostname or "").lower().rstrip(".")
	segments = [segment for segment in parsed.path.split("/") if segment]
	video_id = None

	if host == "youtu.be" and segments:
		video_id = segments[0]
	elif host == "youtube.com" or host.endswith(".youtube.com"):
		if parsed.path.rstrip("/") == "/watch":
			video_id = parse_qs(parsed.query).get("v", [None])[0]
		elif len(segments) > 1 and segments[0] in {
			"embed",
			"live",
			"shorts",
			"v",
		}:
			video_id = segments[1]

	return f"youtube:{video_id}" if video_id else normalized_url


async def is_inflight(user_id: int, url: str) -> bool:
	async with _lock:
		return (user_id, url) in _inflight

# async def mark_inflight(user_id: int, url: str, message_id: int):
# 	async with _lock:
# 		key = (user_id, url)
# 		entry = _inflight.get(key)

# 		if entry:
# 			entry["messages"].append(message_id)
# 		else:
# 			_inflight[key] = {
# 				"started_at": time.time(),
# 				"messages": [message_id],
# 			}

async def mark_inflight(
	user_id: int,
	url: str,
	message_id: int,
) -> bool:
	"""
	Returns True if this is a new inflight entry,
	False if already existed.
	"""
	async with _lock:
		key = (user_id, url)
		entry = _inflight.get(key)

		if entry:
			entry["messages"].append(message_id)
			return False

		_inflight[key] = {
			"started_at": time.time(),
			"messages": [message_id],
		}
		return True

async def get_inflight_messages(user_id: int, url: str) -> List[int]:
	async with _lock:
		return list(_inflight.get((user_id, url), {}).get("messages", []))
	
# async def add_inflight_message(user_id: int, url: str, message_id: int):
# 	async with _lock:
# 		entry = _inflight.get((user_id, url))
# 		if entry:
# 			entry["messages"].append(message_id)

async def pop_inflight_messages(user_id: int, url: str) -> List[int]:
	async with _lock:
		return list(_inflight.pop((user_id, url), {}).get("messages", []))

async def clear_inflight(user_id: int, url: str):
	async with _lock:
		_inflight.pop((user_id, url), None)
