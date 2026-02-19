"""Pipeline execution context for document tasks."""

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)


@dataclass
class PipelineContext:
    """Execution context shared by pipeline functions."""

    document_id: str
    document: Document
    doc_repo: DocumentRepositoryImpl
    session: AsyncSession
    mode: str
    original_status: DocumentStatus
    indexed_anything: bool = False
    _current_stage: Optional[str] = field(default=None, repr=False)

    async def set_stage(
        self,
        stage: ProcessingStage,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Advance processing stage and persist for observability."""
        self._current_stage = stage.value
        await self.doc_repo.update_status(
            document_id=self.document_id,
            status=DocumentStatus.PROCESSING,
            processing_stage=stage.value,
            processing_meta=meta,
        )
        await self.session.commit()

    async def set_terminal_status(
        self,
        status: DocumentStatus,
        chunk_count: int | None = None,
        page_count: int | None = None,
        content_path: str | None = None,
        content_size: int | None = None,
        content_format: str | None = None,
    ) -> None:
        """Set terminal status and clear transient stage/error fields."""
        await self.doc_repo.update_status(
            document_id=self.document_id,
            status=status,
            chunk_count=chunk_count,
            page_count=page_count,
            content_path=content_path,
            content_size=content_size,
            content_format=content_format,
            error_message=None,
            processing_stage=None,
            processing_meta=None,
        )
        await self.session.commit()

    @property
    def current_stage(self) -> str | None:
        """Return current in-flight stage for diagnostics."""
        return self._current_stage

