import asyncio
from unittest.mock import AsyncMock, Mock

from newbee_notebook.application.services.document_service import DocumentService
from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.entities.reference import NotebookDocumentRef


def test_delete_document_detaches_document_from_diagrams(monkeypatch):
    document_repo = AsyncMock()
    document_repo.get = AsyncMock(
        return_value=Document(
            document_id="doc-1",
            title="Document",
        )
    )
    document_repo.delete = AsyncMock(return_value=True)

    ref_repo = AsyncMock()
    ref_repo.list_by_document = AsyncMock(
        return_value=[
            NotebookDocumentRef(reference_id="ref-1", notebook_id="nb-1", document_id="doc-1"),
            NotebookDocumentRef(reference_id="ref-2", notebook_id="nb-2", document_id="doc-1"),
        ]
    )
    ref_repo.delete_by_document = AsyncMock(return_value=2)

    diagram_repo = AsyncMock()
    diagram_repo.list_by_notebook = AsyncMock(
        side_effect=[
            [
                Diagram(
                    diagram_id="diag-1",
                    notebook_id="nb-1",
                    title="Mindmap",
                    diagram_type="mindmap",
                    format="reactflow_json",
                    document_ids=["doc-1", "doc-2"],
                )
            ],
            [
                Diagram(
                    diagram_id="diag-2",
                    notebook_id="nb-2",
                    title="Flowchart",
                    diagram_type="flowchart",
                    format="mermaid",
                    document_ids=["doc-1"],
                )
            ],
        ]
    )
    diagram_repo.update = AsyncMock(side_effect=lambda diagram: diagram)

    delete_task = Mock()
    monkeypatch.setattr(
        "newbee_notebook.infrastructure.tasks.document_tasks.delete_document_nodes_task.delay",
        delete_task,
        raising=False,
    )

    service = DocumentService(
        document_repo=document_repo,
        library_repo=AsyncMock(),
        notebook_repo=AsyncMock(),
        ref_repo=ref_repo,
        reference_repo=AsyncMock(),
        diagram_repo=diagram_repo,
    )

    async def _run():
        deleted = await service.delete_document("doc-1")
        assert deleted is True

    asyncio.run(_run())
    diagram_lookup_calls = [call.kwargs for call in diagram_repo.list_by_notebook.await_args_list]
    assert {"notebook_id": "nb-1", "document_id": "doc-1"} in diagram_lookup_calls
    assert {"notebook_id": "nb-2", "document_id": "doc-1"} in diagram_lookup_calls
    assert diagram_repo.update.await_count == 2
    updated_diagrams = [call.args[0] for call in diagram_repo.update.await_args_list]
    assert updated_diagrams[0].document_ids == ["doc-2"]
    assert updated_diagrams[1].document_ids == []
    ref_repo.delete_by_document.assert_awaited_once_with("doc-1")
    delete_task.assert_called_once_with("doc-1")
