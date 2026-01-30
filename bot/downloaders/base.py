# bot/downloaders/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Callable
from pathlib import Path
from .stages import DownloadStage


ProgressCallback = Callable[[DownloadStage, dict], None]



@dataclass
class DownloadContext:
	user_id: int
	video_url: str

	# video info
	video_id: Optional[str] = None
	video_title: Optional[str] = None
	video_artist: Optional[str] = 'YouTube'
	duration_seconds: Optional[int] = None

	# processing
	processing_mode: Optional[Literal["fast_mode", "slow_mode"]] = None
	chosen_bitrate: Optional[int] = None

	# result
	status: Literal["success", "failed"] = "failed"
	delivery_method: Optional[Literal["telegram", "telegram_split", "link", "failed"]] = "failed"
	downloaded_files: Optional[list[Path]] = None
	output_files: Optional[list[Path]] = None

	# metrics
	estimated_size_mb: Optional[float] = None
	real_size_mb: Optional[float] = None
	processing_time_ms: Optional[int] = None

	# errors
	fallback_reason: Optional[str] = None
	error_message: Optional[str] = None
	ua_profile: Optional[str] = None
	
    #stages
	on_progress: Optional[ProgressCallback] = None


class BaseDownloader(ABC):
	name: str

	@abstractmethod
	def can_handle(self, url: str) -> bool:
		pass
	
	@abstractmethod
	async def download(self, url: str, ctx: DownloadContext) -> None:
		pass    

	# @abstractmethod
	# async def fetch_info(self, url: str) -> Dict:
	# 	pass
