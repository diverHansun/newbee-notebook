from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.diagram_service import (
    DiagramNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.core.skills import SkillContext
from newbee_notebook.domain.entities.diagram import Diagram
from newbee_notebook.skills.diagram.provider import DiagramSkillProvider
from newbee_notebook.skills.diagram.tools import (
    _build_confirm_diagram_type_tool,
    _build_create_diagram_tool,
    _build_delete_diagram_tool,
    _build_list_diagrams_tool,
    _build_read_diagram_tool,
    _build_update_diagram_positions_tool,
    _build_update_diagram_tool,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def diagram_service():
    return AsyncMock()


def _make_diagram(diagram_id: str = "diag-1") -> Diagram:
    return Diagram(
        diagram_id=diagram_id,
        notebook_id="nb-1",
        title="Chapter Map",
        diagram_type="mindmap",
        format="reactflow_json",
        content_path=f"diagrams/nb-1/{diagram_id}.json",
        document_ids=["doc-1"],
    )


@pytest.mark.anyio
async def test_list_diagrams_tool_formats_items(diagram_service):
    diagram_service.list_diagrams.return_value = [_make_diagram()]
    tool = _build_list_diagrams_tool(service=diagram_service, notebook_id="nb-1")

    result = await tool.execute({})

    assert result.error is None
    assert "Found 1 diagram(s)" in result.content
    assert "Chapter Map" in result.content
    diagram_service.list_diagrams.assert_awaited_once_with(notebook_id="nb-1", document_id=None)


@pytest.mark.anyio
async def test_read_diagram_tool_returns_content_and_metadata(diagram_service):
    diagram_service.get_diagram.return_value = _make_diagram("diag-2")
    diagram_service.get_diagram_content.return_value = '{"nodes":[],"edges":[]}'
    tool = _build_read_diagram_tool(service=diagram_service)

    result = await tool.execute({"diagram_id": "diag-2"})

    assert result.error is None
    assert result.content == '{"nodes":[],"edges":[]}'
    assert result.metadata["diagram_type"] == "mindmap"


@pytest.mark.anyio
async def test_create_diagram_tool_handles_validation_error(diagram_service):
    diagram_service.create_diagram.side_effect = DiagramValidationError("missing nodes")
    tool = _build_create_diagram_tool(service=diagram_service, notebook_id="nb-1")

    result = await tool.execute(
        {
            "title": "Invalid",
            "diagram_type": "mindmap",
            "content": "{}",
            "document_ids": [],
        }
    )

    assert result.error == "diagram_validation_failed"
    assert "missing nodes" in result.content


@pytest.mark.anyio
async def test_update_and_delete_diagram_tools(diagram_service):
    diagram_service.update_diagram_content.return_value = _make_diagram("diag-3")
    diagram_service.get_diagram.return_value = _make_diagram("diag-3")
    diagram_service.delete_diagram.return_value = True

    update_tool = _build_update_diagram_tool(service=diagram_service)
    delete_tool = _build_delete_diagram_tool(service=diagram_service)

    update_result = await update_tool.execute({"diagram_id": "diag-3", "content": '{"nodes":[],"edges":[]}'})
    delete_result = await delete_tool.execute({"diagram_id": "diag-3"})

    assert update_result.error is None
    assert "Diagram updated" in update_result.content
    assert delete_result.error is None
    assert "Diagram deleted" in delete_result.content


@pytest.mark.anyio
async def test_update_positions_tool_returns_not_found(diagram_service):
    diagram_service.update_node_positions.side_effect = DiagramNotFoundError("missing")
    tool = _build_update_diagram_positions_tool(service=diagram_service)

    result = await tool.execute({"diagram_id": "missing", "positions": {"root": {"x": 1, "y": 2}}})

    assert result.error == "diagram_not_found"


@pytest.mark.anyio
async def test_confirm_diagram_type_tool_returns_metadata():
    tool = _build_confirm_diagram_type_tool()

    result = await tool.execute(
        {
            "diagram_type": "mindmap",
            "title": "Chapter 3",
            "reason": "Prompt asks for a hierarchy map.",
        }
    )

    assert result.error is None
    assert "confirmed" in result.content.lower()
    assert result.metadata["diagram_type"] == "mindmap"
    assert result.metadata["reason"].startswith("Prompt")


def test_diagram_skill_provider_builds_manifest(diagram_service):
    provider = DiagramSkillProvider(diagram_service=diagram_service)

    manifest = provider.build_manifest(
        SkillContext(
            notebook_id="nb-1",
            activated_command="/diagram",
            selected_document_ids=["doc-1"],
            request_message="Generate a diagram from the notebook document",
        )
    )

    assert manifest.name == "diagram"
    assert manifest.slash_command == "/diagram"
    assert manifest.force_first_tool_call is True
    assert manifest.required_tool_call_before_response == "create_diagram"
    assert manifest.confirmation_required == frozenset(
        {"confirm_diagram_type", "update_diagram", "delete_diagram"}
    )
    assert "create_diagram" in manifest.system_prompt_addition
    assert "strict JSON" in manifest.system_prompt_addition
    assert "Do not output raw <tool_call>" in manifest.system_prompt_addition
    assert [tool.name for tool in manifest.tools] == [
        "list_diagrams",
        "read_diagram",
        "confirm_diagram_type",
        "create_diagram",
        "update_diagram",
        "update_diagram_positions",
        "delete_diagram",
    ]
