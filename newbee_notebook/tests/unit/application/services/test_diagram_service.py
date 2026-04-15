from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.diagram_service import (
    DiagramFormatMismatchError,
    DiagramNotFoundError,
    DiagramService,
    DiagramTypeNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.domain.entities.diagram import Diagram


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def diagram_repo():
    return AsyncMock()


@pytest.fixture
def storage():
    return AsyncMock()


@pytest.fixture
def ref_repo():
    return AsyncMock()


@pytest.fixture
def service(diagram_repo, storage, ref_repo):
    return DiagramService(diagram_repo=diagram_repo, storage=storage, ref_repo=ref_repo)


@pytest.mark.anyio
async def test_create_diagram_persists_metadata_and_content(service, diagram_repo, storage):
    created_diagram: Diagram | None = None

    async def _create(diagram: Diagram) -> Diagram:
        nonlocal created_diagram
        created_diagram = diagram
        return diagram

    diagram_repo.create.side_effect = _create

    diagram = await service.create_diagram(
        notebook_id="nb-1",
        title="Chapter 3 map",
        diagram_type="mindmap",
        content='{"nodes":[{"id":"root","label":"Chapter 3"}],"edges":[]}',
        document_ids=["doc-1"],
    )

    assert diagram.diagram_type == "mindmap"
    assert diagram.format == "reactflow_json"
    assert diagram.content_path.startswith("diagrams/nb-1/")
    assert diagram.content_path.endswith(".json")
    assert created_diagram is not None
    assert created_diagram.title == "Chapter 3 map"
    storage.save_file.assert_awaited_once()


@pytest.mark.anyio
async def test_create_diagram_accepts_flowchart_type(service, diagram_repo, storage):
    async def _create(diagram: Diagram) -> Diagram:
        return diagram

    diagram_repo.create.side_effect = _create

    diagram = await service.create_diagram(
        notebook_id="nb-1",
        title="Login flow",
        diagram_type="flowchart",
        content="flowchart TD\nStart[Start] --> Finish[Finish]",
    )

    assert diagram.diagram_type == "flowchart"
    assert diagram.format == "mermaid"
    assert diagram.content_path.endswith(".mmd")
    storage.save_file.assert_awaited_once()


@pytest.mark.anyio
async def test_create_diagram_defaults_to_notebook_documents_when_document_ids_missing(
    service,
    diagram_repo,
    ref_repo,
):
    async def _create(diagram: Diagram) -> Diagram:
        return diagram

    ref_repo.list_by_notebook.return_value = [
        type("NotebookDocumentRef", (), {"document_id": "doc-1"})(),
        type("NotebookDocumentRef", (), {"document_id": "doc-2"})(),
    ]
    diagram_repo.create.side_effect = _create

    diagram = await service.create_diagram(
        notebook_id="nb-1",
        title="Curriculum Map",
        diagram_type="mindmap",
        content='{"nodes":[{"id":"root","label":"Plan"}],"edges":[]}',
    )

    assert diagram.document_ids == ["doc-1", "doc-2"]
    ref_repo.list_by_notebook.assert_awaited_once_with("nb-1")


@pytest.mark.anyio
async def test_create_diagram_raises_for_unknown_type(service):
    with pytest.raises(DiagramTypeNotFoundError):
        await service.create_diagram(
            notebook_id="nb-1",
            title="Unknown",
            diagram_type="unknown",
            content="{}",
        )


@pytest.mark.anyio
async def test_create_diagram_raises_for_invalid_content(service):
    with pytest.raises(DiagramValidationError):
        await service.create_diagram(
            notebook_id="nb-1",
            title="Invalid",
            diagram_type="mindmap",
            content="not json",
        )


@pytest.mark.anyio
async def test_get_diagram_raises_when_missing(service, diagram_repo):
    diagram_repo.get.return_value = None

    with pytest.raises(DiagramNotFoundError):
        await service.get_diagram("missing")


@pytest.mark.anyio
async def test_get_diagram_raises_when_notebook_scope_mismatches(service, diagram_repo):
    diagram_repo.get.return_value = Diagram(
        diagram_id="diag-1",
        notebook_id="nb-2",
        title="Other Notebook",
        diagram_type="mindmap",
        format="reactflow_json",
        content_path="diagrams/nb-2/diag-1.json",
    )

    with pytest.raises(DiagramNotFoundError):
        await service.get_diagram("diag-1", notebook_id="nb-1")


@pytest.mark.anyio
async def test_update_diagram_content_raises_when_notebook_scope_mismatches(
    service,
    diagram_repo,
):
    diagram_repo.get.return_value = Diagram(
        diagram_id="diag-1",
        notebook_id="nb-2",
        title="Other Notebook",
        diagram_type="mindmap",
        format="reactflow_json",
        content_path="diagrams/nb-2/diag-1.json",
    )

    with pytest.raises(DiagramNotFoundError):
        await service.update_diagram_content(
            "diag-1",
            '{"nodes":[{"id":"root","label":"Root"}],"edges":[]}',
            notebook_id="nb-1",
        )


@pytest.mark.anyio
async def test_update_positions_raises_for_non_reactflow_format(service, diagram_repo):
    diagram_repo.get.return_value = Diagram(
        diagram_id="diag-1",
        notebook_id="nb-1",
        title="Sequence",
        diagram_type="sequence",
        format="mermaid",
        content_path="diagrams/nb-1/diag-1.mmd",
    )

    with pytest.raises(DiagramFormatMismatchError):
        await service.update_node_positions("diag-1", {"n1": {"x": 1.0, "y": 2.0}})


@pytest.mark.anyio
async def test_delete_diagram_calls_repo_and_storage(service, diagram_repo, storage):
    diagram_repo.get.return_value = Diagram(
        diagram_id="diag-1",
        notebook_id="nb-1",
        title="Map",
        diagram_type="mindmap",
        format="reactflow_json",
        content_path="diagrams/nb-1/diag-1.json",
    )
    diagram_repo.delete.return_value = True

    deleted = await service.delete_diagram("diag-1")

    assert deleted is True
    storage.delete_file.assert_awaited_once_with("diagrams/nb-1/diag-1.json")
