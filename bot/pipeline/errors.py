# bot/pipeline/errors.py

from typing import Optional

class PipelineError(Exception):
    """
    Base class for all pipeline-related errors.
    Worker layer should catch only this family of exceptions.
    """
    def __init__(self, message: str = "", *, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details

class PostProcessingFailed(PipelineError):
    """Post-processing (e.g., re-encoding) failed."""
    pass

class PostProcessingNoDuration(PipelineError):
    """Post-processing failed due to missing duration info."""
    pass

class FileTooLarge(PipelineError):
    """The resulting file exceeds the allowed size limit."""
    pass

class DeliveryFailed(PipelineError):
    """Delivery of the file failed."""
    pass

class DeliveryUnsupportedMethod(PipelineError):
    """The specified delivery method is unsupported."""
    pass