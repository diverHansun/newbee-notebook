"""Generated image metadata entity."""

from dataclasses import dataclass, field

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class GeneratedImage(Entity):
    """Persisted metadata for one generated image artifact."""

    image_id: str = field(default_factory=generate_uuid)
    session_id: str = ""
    notebook_id: str = ""
    message_id: int | None = None
    tool_call_id: str = ""
    prompt: str = ""
    provider: str = ""
    model: str = ""
    size: str | None = None
    width: int | None = None
    height: int | None = None
    storage_key: str = ""
    file_size: int = 0
