# bot/downloaders/registry.py
from .youtube import YouTubeDownloader

DOWNLOADERS = [
	YouTubeDownloader(),
]

def get_downloader(url: str):
	for d in DOWNLOADERS:
		if d.can_handle(url):
			return d
	return None

def is_supported_url(url: str) -> bool:
    return get_downloader(url) is not None