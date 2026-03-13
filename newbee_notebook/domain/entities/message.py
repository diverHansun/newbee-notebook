"""Message entity for persisted chat history."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from newbee_notebook.domain.entities.base import Entity, generate_uuid
from newbee_notebook.domain.value_objects.mode_type import ModeType, MessageRole


@dataclass
class Message(Entity):
    message_id: Optional[int] = None
    session_id: str = ""
    mode: ModeType = ModeType.AGENT
    role: MessageRole = MessageRole.USER
    content: str = ""
    created_at: datetime = field(default_factory=datetime.now)
