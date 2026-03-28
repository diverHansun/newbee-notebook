"""ASR-specific infrastructure exceptions."""


class AsrTranscriptionError(RuntimeError):
    """Raised when an ASR provider request cannot be completed."""
