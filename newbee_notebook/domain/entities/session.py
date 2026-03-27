from dataclasses import dataclass, field

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class Session(Entity):
    session_id: str = field(default_factory=generate_uuid)
    notebook_id: str = ""
    title: str | None = None
    message_count: int = 0
    compaction_boundary_id: int | None = None
    include_ec_context: bool = False

    def increment_message_count(self, delta: int = 1) -> None:
        """Increment the message count."""
        self.message_count += delta
        self.touch()
