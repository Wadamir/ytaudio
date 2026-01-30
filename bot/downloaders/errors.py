# bot/downloaders/errors.py

from typing import Optional


class DownloaderError(Exception):
	"""
	Base class for all downloader-related errors.
	Worker layer should catch only this family of exceptions.
	"""
	def __init__(self, message: str = "", *, details: Optional[str] = None):
		super().__init__(message)
		self.message = message
		self.details = details

class FetchInfoFailed(DownloaderError):
    """Failed to fetch video info."""
    pass


class VideoUnavailable(DownloaderError):
	"""Video exists but is unavailable (private, deleted, region blocked)."""
	pass


class LiveStreamNotSupported(DownloaderError):
	"""Live streams are not supported."""
	pass


class VideoTooLong(DownloaderError):
	"""Video duration exceeds allowed limit."""
	pass


class DownloadFailed(DownloaderError):
	"""Download failed after retries (network, yt-dlp, ffmpeg)."""
	pass
