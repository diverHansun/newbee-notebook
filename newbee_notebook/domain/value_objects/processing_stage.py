"""Document processing stage value object."""

from enum import Enum


class ProcessingStage(str, Enum):
    """Processing sub-stages while status=processing."""

    QUEUED = "queued"
    CONVERTING = "converting"
    SPLITTING = "splitting"
    INDEXING_PG = "indexing_pg"
    INDEXING_ES = "indexing_es"
    FINALIZING = "finalizing"

    @property
    def is_conversion_phase(self) -> bool:
        return self == ProcessingStage.CONVERTING

    @property
    def is_indexing_phase(self) -> bool:
        return self in (
            ProcessingStage.SPLITTING,
            ProcessingStage.INDEXING_PG,
            ProcessingStage.INDEXING_ES,
            ProcessingStage.FINALIZING,
        )

