import re
from parsers.registry import register_parser

YOUTUBE_RE = re.compile(
	r"(https?://)?(www\.)?(m\.)?(youtube\.com|youtu\.be)/",
	re.IGNORECASE,
)


def is_youtube_url(url: str) -> bool:
	return bool(YOUTUBE_RE.search(url))


# 🔌 auto-register on import
register_parser(is_youtube_url)
