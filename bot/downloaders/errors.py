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


class YouTubeAuthRequired(FetchInfoFailed):
    """YouTube explicitly requires browser authorization."""
    pass


def is_browser_auth_required(error: Exception) -> bool:
	message = str(error).lower()
	return any(marker in message for marker in (
		"sign in to confirm",
		"confirm you're not a bot",
		"login required",
		"authentication required",
	))


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


class NoUnencryptedAudioFormat(DownloaderError):
	"""No downloadable, unencrypted audio format is available."""
	pass
