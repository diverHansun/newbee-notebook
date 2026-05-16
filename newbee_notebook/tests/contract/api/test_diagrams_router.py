from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from newbee_notebook.api.dependencies import get_diagram_service
from newbee_notebook.api.routers import diagrams as diagrams_router
from newbee_notebook.application.services.diagram_service import (
    DiagramNotFoundError,
    DiagramTypeNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.domain.entities.diagram import Diagram


def _build_client(service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(diagrams_router.router, prefix="/api/v1")

    async def _override():
        return service

    app.dependency_overrides[get_diagram_service] = _override
    return TestClient(app)


def _make_diagram(diagram_id: str = "diag-1") -> Diagram:
    return Diagram(
        diagram_id=diagram_id,
        notebook_id="nb-1",
        title="Chapter map",
        diagram_type="mindmap",
        format="reactflow_json",
        content_path=f"diagrams/nb-1/{diagram_id}.json",
        document_ids=["doc-1"],
        node_positions={"root": {"x": 120.0, "y": 48.0}},
        created_at=datetime(2026, 3, 19, 12, 0, 0),
        updated_at=datetime(2026, 3, 19, 12, 0, 0),
    )


def _make_echarts_diagram(diagram_id: str = "echart-1") -> Diagram:
    return Diagram(
        diagram_id=diagram_id,
        notebook_id="nb-1",
        title="Sales chart",
        diagram_type="echarts",
        format="echarts_option",
        content_path=f"diagrams/nb-1/{diagram_id}.json",
        document_ids=[],
        node_positions=None,
        created_at=datetime(2026, 3, 19, 12, 0, 0),
        updated_at=datetime(2026, 3, 19, 12, 0, 0),
    )


def test_list_diagrams_returns_response():
    service = AsyncMock()
    service.list_diagrams = AsyncMock(return_value=[_make_diagram()])

    client = _build_client(service)
    response = client.get("/api/v1/diagrams", params={"notebook_id": "nb-1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["diagrams"][0]["diagram_id"] == "diag-1"


def test_get_diagram_returns_404_when_missing():
    service = AsyncMock()
    service.get_diagram = AsyncMock(side_effect=DiagramNotFoundError("missing"))

    client = _build_client(service)
    response = client.get("/api/v1/diagrams/missing", params={"notebook_id": "nb-1"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Diagram not found"
    service.get_diagram.assert_awaited_once_with("missing", notebook_id="nb-1")


def test_create_diagram_returns_201_and_derives_format():
    service = AsyncMock()
    service.create_diagram = AsyncMock(return_value=_make_echarts_diagram())

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Sales chart",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1,2,3]}]}',
            "document_ids": [],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["diagram_id"] == "echart-1"
    assert payload["format"] == "echarts_option"
    service.create_diagram.assert_awaited_once_with(
        notebook_id="nb-1",
        title="Sales chart",
        diagram_type="echarts",
        content='{"series":[{"type":"bar","data":[1,2,3]}]}',
        document_ids=[],
    )


def test_create_diagram_rejects_format_in_request_body():
    service = AsyncMock()

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Sales chart",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1,2,3]}]}',
            "document_ids": [],
            "format": "mermaid",
        },
    )

    assert response.status_code == 422
    service.create_diagram.assert_not_awaited()


def test_create_diagram_omitted_document_ids_defaults_to_empty_binding():
    service = AsyncMock()
    service.create_diagram = AsyncMock(return_value=_make_echarts_diagram())

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Sales chart",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1,2,3]}]}',
        },
    )

    assert response.status_code == 201
    service.create_diagram.assert_awaited_once_with(
        notebook_id="nb-1",
        title="Sales chart",
        diagram_type="echarts",
        content='{"series":[{"type":"bar","data":[1,2,3]}]}',
        document_ids=[],
    )


def test_create_diagram_requires_title():
    service = AsyncMock()

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1,2,3]}]}',
        },
    )

    assert response.status_code == 422
    service.create_diagram.assert_not_awaited()


def test_create_diagram_maps_validation_error_to_400():
    service = AsyncMock()
    service.create_diagram = AsyncMock(
        side_effect=DiagramValidationError("schema: bad | 违规位置: content.series | 建议: fix")
    )

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Bad chart",
            "diagram_type": "echarts",
            "content": "{}",
            "document_ids": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "diagram_validation_failed"


def test_create_diagram_maps_unknown_type_to_400():
    service = AsyncMock()
    service.create_diagram = AsyncMock(side_effect=DiagramTypeNotFoundError("not registered"))

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Bad chart",
            "diagram_type": "unknown",
            "content": "{}",
            "document_ids": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_diagram_type"


def test_create_diagram_maps_document_scope_error_to_400():
    service = AsyncMock()
    service.create_diagram = AsyncMock(side_effect=ValueError("Document doc-1 is not associated"))

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "nb-1",
            "title": "Scoped chart",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1]}]}',
            "document_ids": ["doc-1"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_reference"


def test_create_diagram_maps_integrity_error_to_400():
    service = AsyncMock()
    service.create_diagram = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("foreign key"))
    )

    client = _build_client(service)
    response = client.post(
        "/api/v1/diagrams",
        json={
            "notebook_id": "missing-notebook",
            "title": "Chart",
            "diagram_type": "echarts",
            "content": '{"series":[{"type":"bar","data":[1]}]}',
            "document_ids": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_reference"


def test_get_diagram_content_returns_plain_text():
    service = AsyncMock()
    service.get_diagram_content = AsyncMock(return_value='{"nodes":[],"edges":[]}')

    client = _build_client(service)
    response = client.get("/api/v1/diagrams/diag-1/content", params={"notebook_id": "nb-1"})

    assert response.status_code == 200
    assert response.text == '{"nodes":[],"edges":[]}'
    service.get_diagram_content.assert_awaited_once_with("diag-1", notebook_id="nb-1")


def test_patch_positions_returns_updated_diagram():
    service = AsyncMock()
    service.update_node_positions = AsyncMock(return_value=_make_diagram("diag-2"))

    client = _build_client(service)
    response = client.patch(
        "/api/v1/diagrams/diag-2/positions",
        params={"notebook_id": "nb-1"},
        json={"positions": {"root": {"x": 100, "y": 50}}},
    )

    assert response.status_code == 200
    assert response.json()["diagram_id"] == "diag-2"
    service.update_node_positions.assert_awaited_once_with(
        "diag-2",
        {"root": {"x": 100.0, "y": 50.0}},
        notebook_id="nb-1",
    )


def test_delete_diagram_returns_204():
    service = AsyncMock()
    service.delete_diagram = AsyncMock(return_value=True)

    client = _build_client(service)
    response = client.delete("/api/v1/diagrams/diag-1", params={"notebook_id": "nb-1"})

    assert response.status_code == 204
    service.delete_diagram.assert_awaited_once_with("diag-1", notebook_id="nb-1")
