"""Mark domain entity."""

from dataclasses import dataclass, field
from typing import Optional

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class Mark(Entity):
    """A saved text anchor inside a document."""

    mark_id: str = field(default_factory=generate_uuid)
    document_id: str = ""
    anchor_text: str = ""
    char_offset: int = 0
    context_text: Optional[str] = None
