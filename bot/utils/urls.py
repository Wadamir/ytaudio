from urllib.parse import urlsplit


def is_youtube_post_url(url: str) -> bool:
	try:
		parsed = urlsplit(url.strip())
		host = (parsed.hostname or "").lower().rstrip(".")
	except (AttributeError, ValueError):
		return False

	if parsed.scheme not in {"http", "https"}:
		return False

	if host != "youtube.com" and not host.endswith(".youtube.com"):
		return False

	path_segments = [segment for segment in parsed.path.split("/") if segment]
	return bool(path_segments) and path_segments[0].lower() == "post"
