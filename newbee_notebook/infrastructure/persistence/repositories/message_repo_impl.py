"""SQLAlchemy implementation of MessageRepository."""

from typing import List
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.infrastructure.persistence.models import MessageModel
from newbee_notebook.domain.value_objects.mode_type import ModeType, MessageRole


class MessageRepositoryImpl(MessageRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: MessageModel) -> Message:
        return Message(
            message_id=model.id,
            session_id=str(model.session_id),
            mode=ModeType(model.mode),
            role=MessageRole(model.role),
            content=model.content,
            created_at=model.created_at,
        )

    async def create(self, message: Message) -> Message:
        model = MessageModel(
            session_id=uuid.UUID(message.session_id),
            mode=message.mode.value if hasattr(message.mode, "value") else str(message.mode),
            role=message.role.value if hasattr(message.role, "value") else str(message.role),
            content=message.content,
            created_at=message.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        message.message_id = model.id
        return self._to_entity(model)

    async def create_batch(self, messages: List[Message]) -> List[Message]:
        created = []
        for msg in messages:
            created.append(await self.create(msg))
        return created

    async def list_by_session(self, session_id: str, limit: int = 100) -> List[Message]:
        result = await self._session.execute(
            select(MessageModel)
            .where(MessageModel.session_id == uuid.UUID(session_id))
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]
