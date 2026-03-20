"""Application service for diagrams."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.domain.repositories.diagram_repository import DiagramRepository
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
)
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend


class DiagramNotFoundError(Exception):
    """Raised when a diagram cannot be found."""


class DiagramValidationError(Exception):
    """Raised when diagram content validation fails."""


class DiagramTypeNotFoundError(Exception):
    """Raised when a diagram type is not registered."""


class DiagramFormatMismatchError(Exception):
    """Raised when an operation is not compatible with diagram format."""


def _build_diagram_content_key(notebook_id: str, diagram_id: str, extension: str) -> str:
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return f"diagrams/{notebook_id}/{diagram_id}{normalized_extension}"


class DiagramService:
    """CRUD-style service for notebook diagrams."""

    def __init__(
        self,
        diagram_repo: DiagramRepository,
        storage: Optional[StorageBackend] = None,
        ref_repo: Optional[NotebookDocumentRefRepository] = None,
    ):
        self._diagram_repo = diagram_repo
        self._storage = storage or get_runtime_storage_backend()
        self._ref_repo = ref_repo

    async def create_diagram(
        self,
        notebook_id: str,
        title: str,
        diagram_type: str,
        content: str,
        document_ids: Optional[list[str]] = None,
    ) -> Diagram:
        descriptor = self._get_descriptor(diagram_type)
        descriptor.validator(content)

        resolved_document_ids = list(document_ids or [])
        if not resolved_document_ids and self._ref_repo is not None:
            refs = await self._ref_repo.list_by_notebook(notebook_id)
            resolved_document_ids = [ref.document_id for ref in refs]
        for document_id in resolved_document_ids:
            await self._ensure_document_in_notebook(notebook_id, document_id)

        diagram = Diagram(
            notebook_id=notebook_id,
            title=title.strip() or "Untitled diagram",
            diagram_type=descriptor.name,
            format=descriptor.output_format,
            document_ids=resolved_document_ids,
        )
        diagram.content_path = _build_diagram_content_key(
            notebook_id=notebook_id,
            diagram_id=diagram.diagram_id,
            extension=descriptor.file_extension,
        )

        await self._storage.save_file(
            object_key=diagram.content_path,
            data=BytesIO(content.encode("utf-8")),
            content_type="text/plain; charset=utf-8",
        )
        return await self._diagram_repo.create(diagram)

    async def get_diagram(self, diagram_id: str) -> Diagram:
        diagram = await self._diagram_repo.get(diagram_id)
        if diagram is None:
            raise DiagramNotFoundError(f"Diagram not found: {diagram_id}")
        return diagram

    async def list_diagrams(
        self,
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> list[Diagram]:
        return await self._diagram_repo.list_by_notebook(
            notebook_id=notebook_id,
            document_id=document_id,
        )

    async def get_diagram_content(self, diagram_id: str) -> str:
        diagram = await self.get_diagram(diagram_id)
        try:
            return await self._storage.get_text(diagram.content_path)
        except FileNotFoundError as exc:
            raise DiagramNotFoundError(
                f"Diagram content not found for {diagram_id}: {diagram.content_path}"
            ) from exc

    async def update_diagram_content(
        self,
        diagram_id: str,
        content: str,
        title: Optional[str] = None,
    ) -> Diagram:
        diagram = await self.get_diagram(diagram_id)
        descriptor = self._get_descriptor(diagram.diagram_type)
        descriptor.validator(content)

        await self._storage.save_file(
            object_key=diagram.content_path,
            data=BytesIO(content.encode("utf-8")),
            content_type="text/plain; charset=utf-8",
        )
        if title is not None:
            diagram.title = title.strip() or diagram.title
        diagram.touch()
        return await self._diagram_repo.update(diagram)

    async def update_node_positions(
        self,
        diagram_id: str,
        positions: dict[str, dict[str, float]],
    ) -> Diagram:
        diagram = await self.get_diagram(diagram_id)
        if diagram.format != "reactflow_json":
            raise DiagramFormatMismatchError(
                f"Diagram {diagram_id} uses format {diagram.format}; node positions are unsupported."
            )
        diagram.node_positions = positions
        diagram.touch()
        return await self._diagram_repo.update(diagram)

    async def delete_diagram(self, diagram_id: str) -> bool:
        diagram = await self.get_diagram(diagram_id)
        deleted = await self._diagram_repo.delete(diagram_id)
        if deleted:
            try:
                await self._storage.delete_file(diagram.content_path)
            except FileNotFoundError:
                pass
        return deleted

    @staticmethod
    def _get_descriptor(diagram_type: str):
        from newbee_notebook.skills.diagram.registry import get_descriptor

        return get_descriptor(diagram_type)

    async def _ensure_document_in_notebook(self, notebook_id: str, document_id: str) -> None:
        if self._ref_repo is None:
            return
        ref = await self._ref_repo.get_by_notebook_and_document(notebook_id, document_id)
        if ref is None:
            raise ValueError(
                f"Document {document_id} is not associated with notebook {notebook_id}"
            )
