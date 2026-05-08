"""Uploaded chat image metadata entity."""

from dataclasses import dataclass, field
from datetime import datetime

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class ChatImage(Entity):
    """Persisted metadata for one user-uploaded chat image."""

    image_id: str = field(default_factory=generate_uuid)
    session_id: str = ""
    storage_key: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    width: int | None = None
    height: int | None = None
    sha256: str = ""
    deleted_at: datetime | None = None
