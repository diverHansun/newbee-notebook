"""Notebook export orchestration service."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from newbee_notebook.application.services.diagram_service import DiagramService
from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.application.services.mark_service import MarkService
from newbee_notebook.application.services.notebook_document_service import NotebookDocumentService
from newbee_notebook.application.services.notebook_service import NotebookService
from newbee_notebook.application.services.note_service import NoteService
from newbee_notebook.application.services.video_service import VideoService


DEFAULT_EXPORT_TYPES = {
    "documents",
    "notes",
    "marks",
    "diagrams",
    "video_summaries",
}

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_SAFE_TITLE_LENGTH = 80
_DOCUMENT_PAGE_SIZE = 100


def _sanitize_export_title(raw_title: str, fallback: str = "untitled") -> str:
    title = _INVALID_FILENAME_CHARS.sub("_", str(raw_title or "").strip())
    title = title.strip(". ").strip()
    if not title:
        return fallback
    if len(title) > _MAX_SAFE_TITLE_LENGTH:
        return title[:_MAX_SAFE_TITLE_LENGTH].rstrip()
    return title


def _format_export_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _diagram_extension(diagram_format: str) -> str:
    return ".json" if diagram_format == "reactflow_json" else ".mmd"


class ExportService:
    """Compose notebook content into a ZIP package with manifest.json."""

    def __init__(
        self,
        *,
        notebook_service: NotebookService,
        notebook_document_service: NotebookDocumentService,
        document_service: DocumentService,
        note_service: NoteService,
        mark_service: MarkService,
        diagram_service: DiagramService,
        video_service: VideoService,
    ) -> None:
        self._notebook_service = notebook_service
        self._notebook_document_service = notebook_document_service
        self._document_service = document_service
        self._note_service = note_service
        self._mark_service = mark_service
        self._diagram_service = diagram_service
        self._video_service = video_service

    async def export_notebook(
        self,
        notebook_id: str,
        types: set[str],
    ) -> tuple[BytesIO, str]:
        notebook = await self._notebook_service.get_or_raise(notebook_id)
        requested_types = set(types or DEFAULT_EXPORT_TYPES)

        manifest: dict[str, Any] = {
            "version": "1.0",
            "exported_at": _format_export_timestamp(),
            "exporter": "newbee-notebook",
            "notebook": {
                "title": notebook.title,
                "description": notebook.description,
            },
            "documents": [],
            "notes": [],
            "marks": {"file": "", "count": 0},
            "diagrams": [],
            "video_summaries": [],
            "sessions": [],
        }
        errors: list[str] = []

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            if "documents" in requested_types:
                await self._write_documents(notebook_id, archive, manifest, errors)
            if "notes" in requested_types:
                await self._write_notes(notebook_id, archive, manifest)
            if "marks" in requested_types:
                await self._write_marks(notebook_id, archive, manifest)
            if "diagrams" in requested_types:
                await self._write_diagrams(notebook_id, archive, manifest, errors)
            if "video_summaries" in requested_types:
                await self._write_video_summaries(notebook_id, archive, manifest, errors)

            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            if errors:
                archive.writestr("export-errors.txt", "\n".join(errors))

        zip_buffer.seek(0)
        safe_notebook_title = _sanitize_export_title(notebook.title, fallback="notebook")
        filename = f"{safe_notebook_title}-export-{datetime.now().date().isoformat()}.zip"
        return zip_buffer, filename

    async def _write_documents(
        self,
        notebook_id: str,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
        errors: list[str],
    ) -> None:
        offset = 0
        total = 1
        while offset < total:
            page, total = await self._notebook_document_service.list_documents(
                notebook_id=notebook_id,
                limit=_DOCUMENT_PAGE_SIZE,
                offset=offset,
            )
            if not page:
                break

            for document, _ref_created_at in page:
                try:
                    resolved_document, markdown = await self._document_service.get_document_content(
                        document.document_id,
                        format="markdown",
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        f"type=documents id={document.document_id} reason={self._safe_error_message(exc)}"
                    )
                    continue

                safe_title = _sanitize_export_title(resolved_document.title)
                file_path = f"documents/{safe_title}_{resolved_document.document_id}.md"
                archive.writestr(file_path, markdown or "")
                manifest["documents"].append(
                    {
                        "document_id": resolved_document.document_id,
                        "title": resolved_document.title,
                        "content_type": getattr(resolved_document.content_type, "value", str(resolved_document.content_type)),
                        "page_count": int(resolved_document.page_count or 0),
                        "chunk_count": int(resolved_document.chunk_count or 0),
                        "file": file_path,
                    }
                )

            offset += len(page)

    async def _write_notes(
        self,
        notebook_id: str,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
    ) -> None:
        notes = await self._note_service.list_by_notebook(notebook_id)
        for note in notes:
            safe_title = _sanitize_export_title(note.title)
            file_path = f"notes/{safe_title}_{note.note_id}.md"
            archive.writestr(file_path, note.content or "")
            manifest["notes"].append(
                {
                    "note_id": note.note_id,
                    "title": note.title,
                    "file": file_path,
                    "document_ids": list(note.document_ids),
                    "mark_ids": list(note.mark_ids),
                }
            )

    async def _write_marks(
        self,
        notebook_id: str,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
    ) -> None:
        marks = await self._mark_service.list_by_notebook(notebook_id)
        marks_file = "marks/marks.json"
        marks_payload = [
            {
                "mark_id": mark.mark_id,
                "document_id": mark.document_id,
                "anchor_text": mark.anchor_text,
                "context_text": mark.context_text,
                "char_offset": mark.char_offset,
            }
            for mark in marks
        ]
        archive.writestr(marks_file, json.dumps(marks_payload, ensure_ascii=False, indent=2))
        manifest["marks"] = {
            "file": marks_file,
            "count": len(marks_payload),
        }

    async def _write_diagrams(
        self,
        notebook_id: str,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
        errors: list[str],
    ) -> None:
        diagrams = await self._diagram_service.list_diagrams(notebook_id)
        for diagram in diagrams:
            try:
                content = await self._diagram_service.get_diagram_content(
                    diagram.diagram_id,
                    notebook_id=notebook_id,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"type=diagrams id={diagram.diagram_id} reason={self._safe_error_message(exc)}"
                )
                continue

            safe_title = _sanitize_export_title(diagram.title)
            extension = _diagram_extension(diagram.format)
            file_path = f"diagrams/{safe_title}_{diagram.diagram_id}{extension}"
            archive.writestr(file_path, content or "")
            manifest["diagrams"].append(
                {
                    "diagram_id": diagram.diagram_id,
                    "title": diagram.title,
                    "diagram_type": diagram.diagram_type,
                    "format": diagram.format,
                    "file": file_path,
                    "document_ids": list(diagram.document_ids),
                }
            )

    async def _write_video_summaries(
        self,
        notebook_id: str,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
        errors: list[str],
    ) -> None:
        summaries = await self._video_service.list_by_notebook(notebook_id)
        for summary in summaries:
            if summary.status != "completed":
                errors.append(
                    f"type=video_summaries id={summary.summary_id} reason=summary_not_completed"
                )
                continue

            safe_title = _sanitize_export_title(summary.title, fallback=summary.video_id or "video-summary")
            file_path = f"video-summaries/{safe_title}_{summary.summary_id}.md"
            archive.writestr(file_path, summary.summary_content or "")
            manifest["video_summaries"].append(
                {
                    "summary_id": summary.summary_id,
                    "title": summary.title,
                    "platform": summary.platform,
                    "video_id": summary.video_id,
                    "file": file_path,
                }
            )

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        message = str(exc).strip().replace("\n", " ")
        return message or exc.__class__.__name__
