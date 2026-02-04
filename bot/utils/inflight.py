import time
from typing import Dict, Tuple

# key = (user_id, url)
_inflight: Dict[Tuple[int, str], float] = {}

def is_inflight(user_id: int, url: str) -> bool:
    return (user_id, url) in _inflight

def mark_inflight(user_id: int, url: str):
    _inflight[(user_id, url)] = time.time()

def clear_inflight(user_id: int, url: str):
    _inflight.pop((user_id, url), None)

