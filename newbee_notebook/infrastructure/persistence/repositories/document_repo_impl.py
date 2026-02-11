"""
Newbee Notebook - Document Repository Implementation
"""

from typing import Optional, List, Any
from datetime import datetime
import json
import uuid

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.document_type import DocumentType
from newbee_notebook.domain.repositories.document_repository import DocumentRepository
from newbee_notebook.infrastructure.persistence.models import DocumentModel


class DocumentRepositoryImpl(DocumentRepository):
    """
    SQLAlchemy implementation of DocumentRepository.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _serialize_processing_meta(processing_meta: Optional[dict[str, Any]]) -> Optional[str]:
        if processing_meta is None:
            return None
        return json.dumps(processing_meta, ensure_ascii=False)

    @staticmethod
    def _deserialize_processing_meta(raw_meta: Optional[str]) -> Optional[dict[str, Any]]:
        if not raw_meta:
            return None
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"raw": raw_meta}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _to_entity(self, model: DocumentModel) -> Document:
        """Convert ORM model to domain entity."""
        status = (
            DocumentStatus(model.status)
            if model.status in DocumentStatus._value2member_map_
            else DocumentStatus.PENDING
        )
        doc_type = (
            DocumentType(model.content_type)
            if model.content_type in DocumentType._value2member_map_
            else DocumentType.TXT
        )

        return Document(
            document_id=str(model.id),
            title=model.title,
            content_type=doc_type,
            file_path=model.file_path or "",
            status=status,
            library_id=str(model.library_id) if model.library_id else None,
            notebook_id=str(model.notebook_id) if model.notebook_id else None,
            url=model.url,
            page_count=model.page_count,
            chunk_count=model.chunk_count,
            file_size=model.file_size,
            content_path=model.content_path,
            content_format=model.content_format or "markdown",
            content_size=model.content_size,
            error_message=model.error_message,
            processing_stage=model.processing_stage,
            stage_updated_at=model.stage_updated_at,
            processing_meta=self._deserialize_processing_meta(model.processing_meta),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _status_filter(self, query, status: Optional[DocumentStatus]):
        """Apply status filter if provided."""
        if status:
            query = query.where(DocumentModel.status == status.value)
        return query

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    async def get(self, document_id: str) -> Optional[Document]:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id == uuid.UUID(document_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_batch(self, document_ids: List[str]) -> List[Document]:
        if not document_ids:
            return []
        uuids = [uuid.UUID(doc_id) for doc_id in document_ids]
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id.in_(uuids))
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_library(
        self, limit: int = 50, offset: int = 0, status: Optional[DocumentStatus] = None
    ) -> List[Document]:
        query = (
            select(DocumentModel)
            .where(DocumentModel.library_id.is_not(None))
            .order_by(DocumentModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        query = self._status_filter(query, status)
        result = await self._session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_notebook(
        self, notebook_id: str, limit: int = 50, offset: int = 0
    ) -> List[Document]:
        result = await self._session.execute(
            select(DocumentModel)
            .where(
                DocumentModel.notebook_id == uuid.UUID(notebook_id),
                DocumentModel.library_id.is_(None),
            )
            .order_by(DocumentModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_library(self, status: Optional[DocumentStatus] = None) -> int:
        query = select(func.count(DocumentModel.id)).where(
            DocumentModel.library_id.is_not(None)
        )
        query = self._status_filter(query, status)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def count_by_notebook(self, notebook_id: str) -> int:
        result = await self._session.execute(
            select(func.count(DocumentModel.id)).where(
                DocumentModel.notebook_id == uuid.UUID(notebook_id),
                DocumentModel.library_id.is_(None),
            )
        )
        return result.scalar() or 0

    async def create(self, document: Document) -> Document:
        model = DocumentModel(
            id=uuid.UUID(document.document_id),
            library_id=uuid.UUID(document.library_id) if document.library_id else None,
            notebook_id=uuid.UUID(document.notebook_id)
            if document.notebook_id
            else None,
            title=document.title,
            content_type=document.content_type.value,
            file_path=document.file_path,
            url=document.url,
            status=document.status.value,
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            file_size=document.file_size,
            content_path=document.content_path,
            content_format=document.content_format,
            content_size=document.content_size,
            processing_stage=document.processing_stage,
            stage_updated_at=document.stage_updated_at,
            processing_meta=self._serialize_processing_meta(document.processing_meta),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, document: Document) -> Document:
        await self._session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == uuid.UUID(document.document_id))
            .values(
                title=document.title,
                content_type=document.content_type.value,
                file_path=document.file_path,
                url=document.url,
                status=document.status.value,
                page_count=document.page_count,
                chunk_count=document.chunk_count,
                file_size=document.file_size,
                content_path=document.content_path,
                content_format=document.content_format,
                content_size=document.content_size,
                processing_stage=document.processing_stage,
                stage_updated_at=document.stage_updated_at,
                processing_meta=self._serialize_processing_meta(document.processing_meta),
                updated_at=datetime.now(),
            )
        )
        await self._session.flush()
        return document

    async def delete(self, document_id: str) -> bool:
        result = await self._session.execute(
            delete(DocumentModel).where(DocumentModel.id == uuid.UUID(document_id))
        )
        await self._session.flush()
        return result.rowcount > 0

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        chunk_count: Optional[int] = None,
        page_count: Optional[int] = None,
        content_path: Optional[str] = None,
        content_size: Optional[int] = None,
        content_format: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_stage: Optional[str] = None,
        stage_updated_at: Optional[datetime] = None,
        processing_meta: Optional[dict[str, Any]] = None,
    ) -> None:
        values = {
            "status": status.value,
            "updated_at": datetime.now(),
        }
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if page_count is not None:
            values["page_count"] = page_count
        if content_path is not None:
            values["content_path"] = content_path
        if content_size is not None:
            values["content_size"] = content_size
        if content_format is not None:
            values["content_format"] = content_format
        if error_message is not None or status != DocumentStatus.FAILED:
            values["error_message"] = error_message
        if processing_stage is not None:
            values["processing_stage"] = processing_stage
            if processing_meta is None:
                values["processing_meta"] = None
        if processing_meta is not None:
            values["processing_meta"] = self._serialize_processing_meta(processing_meta)
        if stage_updated_at is not None:
            values["stage_updated_at"] = stage_updated_at
        elif processing_stage is not None or processing_meta is not None:
            values["stage_updated_at"] = datetime.now()

        await self._session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == uuid.UUID(document_id))
            .values(**values)
        )
        await self._session.flush()

    async def claim_processing(
        self,
        document_id: str,
        from_statuses: Optional[List[DocumentStatus]] = None,
        processing_stage: Optional[str] = None,
        processing_meta: Optional[dict[str, Any]] = None,
    ) -> bool:
        allowed = from_statuses or [
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.FAILED,
        ]
        allowed_values = [status.value for status in allowed]
        now = datetime.now()
        values: dict[str, Any] = {
            "status": DocumentStatus.PROCESSING.value,
            "updated_at": now,
            "error_message": None,
            "processing_meta": self._serialize_processing_meta(processing_meta) if processing_meta is not None else None,
        }
        if processing_stage is not None:
            values["processing_stage"] = processing_stage
            values["stage_updated_at"] = now
        else:
            values["processing_stage"] = None
            values["stage_updated_at"] = None
        if processing_meta is not None and "stage_updated_at" not in values:
            values["stage_updated_at"] = now
        result = await self._session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == uuid.UUID(document_id),
                DocumentModel.status.in_(allowed_values),
            )
            .values(**values)
        )
        await self._session.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def commit(self) -> None:
        await self._session.commit()

    async def delete_by_notebook(self, notebook_id: str) -> int:
        result = await self._session.execute(
            delete(DocumentModel).where(
                DocumentModel.notebook_id == uuid.UUID(notebook_id),
                DocumentModel.library_id.is_(None),
            )
        )
        await self._session.flush()
        return result.rowcount

    async def count_all(self, status: Optional[DocumentStatus] = None) -> int:
        query = select(func.count(DocumentModel.id))
        query = self._status_filter(query, status)
        result = await self._session.execute(query)
        return result.scalar() or 0


