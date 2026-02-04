import logging
import time
import random
from collections import defaultdict

from bot.config.network import (
	YT_IP_403_THRESHOLD,
	YT_IP_403_COOLDOWN_MIN,
	YT_IP_403_COOLDOWN_MAX,
)

logger = logging.getLogger(__name__)

_state = defaultdict(lambda: {
	"errors_403": 0,
	"blocked_until": 0,
})


def is_blocked(route_key: str) -> bool:
	return time.time() < _state[route_key]["blocked_until"]

def mark_403(route_key: str):
	s = _state[route_key]
	s["errors_403"] += 1

	if s["errors_403"] >= YT_IP_403_THRESHOLD:
		cooldown = random.randint(YT_IP_403_COOLDOWN_MIN, YT_IP_403_COOLDOWN_MAX)
		s["blocked_until"] = time.time() + cooldown
		s["errors_403"] = 0
		
		logger.warning(
			"Route %s blocked for %ss after %s 403s",
			route_key,
			cooldown,
			YT_IP_403_THRESHOLD,
		)


def mark_success(route_key: str):
	_state[route_key] = {
		"errors_403": 0,
		"blocked_until": 0,
	}

