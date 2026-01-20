"""Message entity for persisted chat history."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from medimind_agent.domain.entities.base import Entity, generate_uuid
from medimind_agent.domain.value_objects.mode_type import ModeType, MessageRole


@dataclass
class Message(Entity):
    message_id: Optional[int] = None
    session_id: str = ""
    mode: ModeType = ModeType.CHAT
    role: MessageRole = MessageRole.USER
    content: str = ""
    created_at: datetime = field(default_factory=datetime.now)
