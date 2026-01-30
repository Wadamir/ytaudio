from enum import Enum


class DownloadStage(str, Enum):
    FETCHING_INFO = "fetching_info"
    INFO_READY = "info_ready"

    STARTING_DOWNLOAD = "starting_download"
    DOWNLOADING = "downloading"

    FINISHED = "finished"
