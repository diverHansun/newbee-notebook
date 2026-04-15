"""SQLAlchemy implementation of MessageRepository."""

from typing import List, Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.infrastructure.persistence.models import MessageModel
from newbee_notebook.domain.value_objects.mode_type import MessageRole, MessageType, ModeType


class MessageRepositoryImpl(MessageRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: MessageModel) -> Message:
        return Message(
            message_id=model.id,
            session_id=str(model.session_id),
            mode=ModeType(model.mode),
            role=MessageRole(model.role),
            message_type=MessageType(model.message_type),
            content=model.content,
            created_at=model.created_at,
        )

    async def create(self, message: Message) -> Message:
        model = MessageModel(
            session_id=uuid.UUID(message.session_id),
            mode=message.mode.value if hasattr(message.mode, "value") else str(message.mode),
            role=message.role.value if hasattr(message.role, "value") else str(message.role),
            message_type=(
                message.message_type.value
                if hasattr(message.message_type, "value")
                else str(message.message_type)
            ),
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

    async def list_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        modes: Optional[List[ModeType]] = None,
        descending: bool = False,
    ) -> List[Message]:
        order_columns = (
            (MessageModel.created_at.desc(), MessageModel.id.desc())
            if descending
            else (MessageModel.created_at.asc(), MessageModel.id.asc())
        )
        query = (
            select(MessageModel)
            .where(MessageModel.session_id == uuid.UUID(session_id))
            .order_by(*order_columns)
            .limit(limit)
            .offset(offset)
        )
        if modes is not None:
            mode_values = [mode.value for mode in modes]
            if not mode_values:
                return []
            query = query.where(MessageModel.mode.in_(mode_values))

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_after_boundary(
        self,
        session_id: str,
        boundary_message_id: int | None,
        track_modes: Optional[List[ModeType]] = None,
    ) -> List[Message]:
        query = (
            select(MessageModel)
            .where(MessageModel.session_id == uuid.UUID(session_id))
            .order_by(MessageModel.created_at.asc(), MessageModel.id.asc())
        )
        if boundary_message_id is not None:
            query = query.where(MessageModel.id >= boundary_message_id)
        if track_modes is not None:
            mode_values = [mode.value for mode in track_modes]
            if not mode_values:
                return []
            query = query.where(MessageModel.mode.in_(mode_values))

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_session(
        self,
        session_id: str,
        modes: Optional[List[ModeType]] = None,
    ) -> int:
        query = select(func.count()).select_from(MessageModel).where(
            MessageModel.session_id == uuid.UUID(session_id)
        )
        if modes is not None:
            mode_values = [mode.value for mode in modes]
            if not mode_values:
                return 0
            query = query.where(MessageModel.mode.in_(mode_values))

        result = await self._session.execute(query)
        return int(result.scalar() or 0)
