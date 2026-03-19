"""Note domain entity."""

from dataclasses import dataclass, field

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class Note(Entity):
    """A notebook-scoped plain text note."""

    note_id: str = field(default_factory=generate_uuid)
    notebook_id: str = ""
    title: str = ""
    content: str = ""
    document_ids: list[str] = field(default_factory=list)
    mark_ids: list[str] = field(default_factory=list)
