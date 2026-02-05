import time
from typing import Dict, Tuple

# key = (user_id, url)
_inflight: Dict[Tuple[int, str], dict] = {}

def is_inflight(user_id: int, url: str) -> bool:
	return (user_id, url) in _inflight

def mark_inflight(user_id: int, url: str, message_id: int):
	if is_inflight(user_id, url):
		add_inflight_message(user_id, url, message_id)
	else:
		_inflight[(user_id, url)] = {
			"started_at": time.time(),
			"messages": [message_id],  # store message ids to later edit them if needed
		}

def add_inflight_message(user_id: int, url: str, message_id: int):
	entry = _inflight.get((user_id, url))
	if entry:
		entry["messages"].append(message_id)

def get_inflight_messages(user_id: int, url: str) -> list:
	entry = _inflight.get((user_id, url))
	if entry:
		return entry["messages"]
	return []

def pop_inflight_messages(user_id: int, url: str) -> list:
	entry = _inflight.pop((user_id, url), None)
	if entry:
		return entry["messages"]
	return []
	
def clear_inflight(user_id: int, url: str):
	_inflight.pop((user_id, url), None)