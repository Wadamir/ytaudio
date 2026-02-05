import time
from asyncio import Lock
from typing import TypedDict, Tuple, List, Dict

_lock = Lock()

class InflightEntry(TypedDict):
	started_at: float
	messages: List[int]

_inflight: Dict[Tuple[int, str], InflightEntry] = {}

async def is_inflight(user_id: int, url: str) -> bool:
	async with _lock:
		return (user_id, url) in _inflight

async def mark_inflight(user_id: int, url: str, message_id: int):
	async with _lock:
		key = (user_id, url)
		entry = _inflight.get(key)

		if entry:
			entry["messages"].append(message_id)
		else:
			_inflight[key] = {
				"started_at": time.time(),
				"messages": [message_id],
			}

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
