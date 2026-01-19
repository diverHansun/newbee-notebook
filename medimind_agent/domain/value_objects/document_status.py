"""
MediMind Agent - Document Status Value Object
"""

from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"      # Uploaded, waiting for processing
    PROCESSING = "processing"  # Being processed
    COMPLETED = "completed"   # Processing completed successfully
    FAILED = "failed"        # Processing failed
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal status."""
        return self in (DocumentStatus.COMPLETED, DocumentStatus.FAILED)
    
    @property
    def is_active(self) -> bool:
        """Check if document is being actively processed."""
        return self in (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


