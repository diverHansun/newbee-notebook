"""
Newbee Notebook - Base Entity

Provides the base class for all domain entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


@dataclass
class Entity:
    """
    Base class for all domain entities.
    
    Provides common attributes and methods for entity identification
    and timestamp tracking.
    """
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()


