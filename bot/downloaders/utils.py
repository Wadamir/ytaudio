from .stages import DownloadStage
from .base import DownloadContext


def notify(ctx: DownloadContext, stage: DownloadStage, data: dict | None = None):
    if ctx.on_progress:
        ctx.on_progress(stage, data or {})
