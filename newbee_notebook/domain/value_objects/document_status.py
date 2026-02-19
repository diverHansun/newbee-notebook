"""
Newbee Notebook - Document Status Value Object
"""

from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"        # Queued for worker execution
    UPLOADED = "uploaded"      # File saved, waiting to be added to notebook
    PROCESSING = "processing"  # Worker claimed and is processing
    CONVERTED = "converted"    # Converted to markdown, waiting for indexing
    COMPLETED = "completed"    # Processing completed successfully
    FAILED = "failed"          # Processing failed
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal status."""
        return self in (DocumentStatus.COMPLETED, DocumentStatus.FAILED)

    @property
    def is_stable(self) -> bool:
        """Check if status can be a stable waiting point."""
        return self in (
            DocumentStatus.UPLOADED,
            DocumentStatus.CONVERTED,
            DocumentStatus.COMPLETED,
            DocumentStatus.FAILED,
        )

    @property
    def is_blocking(self) -> bool:
        """Check if status blocks chat/retrieval usage."""
        return self in (
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.CONVERTED,
        )

    @property
    def can_start_conversion(self) -> bool:
        """Check if conversion can start from this status."""
        return self in (DocumentStatus.UPLOADED, DocumentStatus.FAILED)

    @property
    def can_start_indexing(self) -> bool:
        """Check if indexing can start from this status."""
        return self == DocumentStatus.CONVERTED
    
    @property
    def is_active(self) -> bool:
        """Check if document is being actively processed."""
        return self in (DocumentStatus.PENDING, DocumentStatus.UPLOADED, DocumentStatus.PROCESSING)


