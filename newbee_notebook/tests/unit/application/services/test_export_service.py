from __future__ import annotations

import json
import zipfile
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.entities.mark import Mark
from newbee_notebook.domain.entities.notebook import Notebook
from newbee_notebook.domain.entities.note import Note
from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.domain.value_objects.document_type import DocumentType


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_service():
    from newbee_notebook.application.services.export_service import ExportService

    notebook_service = AsyncMock()
    notebook_document_service = AsyncMock()
    document_service = AsyncMock()
    note_service = AsyncMock()
    mark_service = AsyncMock()
    diagram_service = AsyncMock()
    video_service = AsyncMock()

    service = ExportService(
        notebook_service=notebook_service,
        notebook_document_service=notebook_document_service,
        document_service=document_service,
        note_service=note_service,
        mark_service=mark_service,
        diagram_service=diagram_service,
        video_service=video_service,
    )
    return (
        service,
        notebook_service,
        notebook_document_service,
        document_service,
        note_service,
        mark_service,
        diagram_service,
        video_service,
    )


@pytest.mark.anyio
async def test_export_notebook_builds_manifest_and_zip_for_full_types():
    (
        service,
        notebook_service,
        notebook_document_service,
        document_service,
        note_service,
        mark_service,
        diagram_service,
        video_service,
    ) = _build_service()

    notebook_service.get_or_raise.return_value = Notebook(
        notebook_id="nb-1",
        title="Notebook Export",
        description="export all",
        created_at=datetime(2026, 4, 15, 9, 0, 0),
        updated_at=datetime(2026, 4, 15, 9, 0, 0),
    )

    document = Document(
        document_id="doc-1",
        title="Doc One",
        content_type=DocumentType.PDF,
        page_count=8,
        chunk_count=32,
    )
    notebook_document_service.list_documents.return_value = ([(document, datetime(2026, 4, 15, 9, 0, 0))], 1)
    document_service.get_document_content.return_value = (document, "# Doc One")

    note_service.list_by_notebook.return_value = [
        Note(
            note_id="note-1",
            notebook_id="nb-1",
            title="Note One",
            content="## note body",
            document_ids=["doc-1"],
            mark_ids=["mark-1"],
        )
    ]
    mark_service.list_by_notebook.return_value = [
        Mark(
            mark_id="mark-1",
            document_id="doc-1",
            anchor_text="anchor",
            char_offset=10,
            context_text="context",
        )
    ]
    diagram_service.list_diagrams.return_value = [
        Diagram(
            diagram_id="diagram-1",
            notebook_id="nb-1",
            title="Concept Map",
            diagram_type="concept_map",
            format="mermaid",
            document_ids=["doc-1"],
        )
    ]
    diagram_service.get_diagram_content.return_value = "graph TD;A-->B"
    video_service.list_by_notebook.return_value = [
        VideoSummary(
            summary_id="summary-1",
            notebook_id="nb-1",
            platform="bilibili",
            video_id="BV1xx411c7mD",
            title="Video One",
            summary_content="## video summary",
            status="completed",
        )
    ]

    buffer, filename = await service.export_notebook(
        "nb-1",
        {"documents", "notes", "marks", "diagrams", "video_summaries"},
    )

    assert filename.endswith(".zip")
    assert "Notebook Export-export-" in filename

    with zipfile.ZipFile(buffer, "r") as zipped:
        names = set(zipped.namelist())
        assert "manifest.json" in names
        assert "documents/Doc One_doc-1.md" in names
        assert "notes/Note One_note-1.md" in names
        assert "marks/marks.json" in names
        assert "diagrams/Concept Map_diagram-1.mmd" in names
        assert "video-summaries/Video One_summary-1.md" in names

        manifest = json.loads(zipped.read("manifest.json").decode("utf-8"))
        assert manifest["version"] == "1.0"
        assert manifest["notebook"]["title"] == "Notebook Export"
        assert manifest["documents"][0]["document_id"] == "doc-1"
        assert manifest["notes"][0]["note_id"] == "note-1"
        assert manifest["marks"]["count"] == 1
        assert manifest["diagrams"][0]["diagram_id"] == "diagram-1"
        assert manifest["video_summaries"][0]["summary_id"] == "summary-1"
        assert manifest["sessions"] == []


@pytest.mark.anyio
async def test_export_notebook_skips_failed_entries_and_writes_error_report():
    (
        service,
        notebook_service,
        notebook_document_service,
        document_service,
        note_service,
        mark_service,
        diagram_service,
        video_service,
    ) = _build_service()

    notebook_service.get_or_raise.return_value = Notebook(
        notebook_id="nb-1",
        title="Notebook Export",
        description=None,
    )

    first_doc = Document(document_id="doc-ok", title="Doc OK", content_type=DocumentType.PDF)
    failed_doc = Document(document_id="doc-fail", title="Doc Fail", content_type=DocumentType.PDF)
    notebook_document_service.list_documents.return_value = (
        [
            (first_doc, datetime(2026, 4, 15, 9, 0, 0)),
            (failed_doc, datetime(2026, 4, 15, 9, 0, 0)),
        ],
        2,
    )

    async def _get_document_content(document_id: str, format: str = "markdown"):
        if document_id == "doc-fail":
            raise RuntimeError("document not ready")
        return first_doc, "# ok"

    document_service.get_document_content.side_effect = _get_document_content
    note_service.list_by_notebook.return_value = []
    mark_service.list_by_notebook.return_value = []
    diagram_service.list_diagrams.return_value = []
    video_service.list_by_notebook.return_value = []

    buffer, _filename = await service.export_notebook("nb-1", {"documents"})

    with zipfile.ZipFile(buffer, "r") as zipped:
        names = set(zipped.namelist())
        assert "documents/Doc OK_doc-ok.md" in names
        assert "documents/Doc Fail_doc-fail.md" not in names
        assert "export-errors.txt" in names

        errors_text = zipped.read("export-errors.txt").decode("utf-8")
        assert "doc-fail" in errors_text

        manifest = json.loads(zipped.read("manifest.json").decode("utf-8"))
        assert [item["document_id"] for item in manifest["documents"]] == ["doc-ok"]
