import asyncio
from unittest.mock import AsyncMock

from newbee_notebook.application.services.notebook_service import NotebookService
from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.domain.entities.notebook import Notebook


def test_delete_notebook_removes_diagram_content_before_notebook_delete():
    notebook_repo = AsyncMock()
    notebook_repo.get = AsyncMock(return_value=Notebook(notebook_id="nb-1", title="Notebook"))
    notebook_repo.delete = AsyncMock(return_value=True)

    document_repo = AsyncMock()
    document_repo.delete_by_notebook = AsyncMock(return_value=0)

    ref_repo = AsyncMock()
    ref_repo.delete_by_notebook = AsyncMock(return_value=0)

    diagram_repo = AsyncMock()
    diagram_repo.list_by_notebook = AsyncMock(
        return_value=[
            Diagram(
                diagram_id="diag-1",
                notebook_id="nb-1",
                title="Mindmap",
                diagram_type="mindmap",
                format="reactflow_json",
                content_path="diagrams/nb-1/diag-1.json",
            )
        ]
    )

    storage = AsyncMock()

    service = NotebookService(
        notebook_repo=notebook_repo,
        document_repo=document_repo,
        session_repo=AsyncMock(),
        ref_repo=ref_repo,
        diagram_repo=diagram_repo,
        storage=storage,
    )

    async def _run():
        deleted = await service.delete("nb-1")
        assert deleted is True

    asyncio.run(_run())
    diagram_repo.list_by_notebook.assert_awaited_once_with("nb-1")
    storage.delete_file.assert_awaited_once_with("diagrams/nb-1/diag-1.json")
    ref_repo.delete_by_notebook.assert_awaited_once_with("nb-1")
    document_repo.delete_by_notebook.assert_awaited_once_with("nb-1")
    notebook_repo.delete.assert_awaited_once_with("nb-1")


def test_delete_notebook_ignores_missing_diagram_content():
    notebook_repo = AsyncMock()
    notebook_repo.get = AsyncMock(return_value=Notebook(notebook_id="nb-1", title="Notebook"))
    notebook_repo.delete = AsyncMock(return_value=True)

    diagram_repo = AsyncMock()
    diagram_repo.list_by_notebook = AsyncMock(
        return_value=[
            Diagram(
                diagram_id="diag-2",
                notebook_id="nb-1",
                title="Flowchart",
                diagram_type="flowchart",
                format="mermaid",
                content_path="diagrams/nb-1/diag-2.mmd",
            )
        ]
    )

    storage = AsyncMock()
    storage.delete_file = AsyncMock(side_effect=FileNotFoundError("missing"))

    service = NotebookService(
        notebook_repo=notebook_repo,
        document_repo=AsyncMock(delete_by_notebook=AsyncMock(return_value=0)),
        session_repo=AsyncMock(),
        ref_repo=AsyncMock(delete_by_notebook=AsyncMock(return_value=0)),
        diagram_repo=diagram_repo,
        storage=storage,
    )

    async def _run():
        deleted = await service.delete("nb-1")
        assert deleted is True

    asyncio.run(_run())
    notebook_repo.delete.assert_awaited_once_with("nb-1")
