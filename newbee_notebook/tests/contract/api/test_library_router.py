from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_library_service
from newbee_notebook.api.routers import library
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.document_type import DocumentType


def _build_client(service: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(library.router, prefix="/api/v1")
    app.dependency_overrides[get_library_service] = lambda: service
    return TestClient(app)


def _service() -> SimpleNamespace:
    return SimpleNamespace(list_documents=AsyncMock(return_value=([], 0)))


def test_list_library_documents_omits_content_type_filter_by_default():
    service = _service()
    client = _build_client(service)

    response = client.get("/api/v1/library/documents")

    assert response.status_code == 200
    assert service.list_documents.await_args.kwargs["content_types"] is None


def test_list_library_documents_accepts_single_content_type_filter():
    service = _service()
    client = _build_client(service)

    response = client.get("/api/v1/library/documents?content_type=pdf")

    assert response.status_code == 200
    assert service.list_documents.await_args.kwargs["content_types"] == [DocumentType.PDF]


def test_list_library_documents_accepts_multiple_content_type_filters_with_status():
    service = _service()
    client = _build_client(service)

    response = client.get(
        "/api/v1/library/documents?status=completed&content_type=pdf&content_type=docx"
    )

    assert response.status_code == 200
    kwargs = service.list_documents.await_args.kwargs
    assert kwargs["status"] == DocumentStatus.COMPLETED
    assert kwargs["content_types"] == [DocumentType.PDF, DocumentType.DOCX]


def test_list_library_documents_rejects_invalid_content_type_filter():
    service = _service()
    client = _build_client(service)

    response = client.get("/api/v1/library/documents?content_type=unknown")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid content_type filter"
    service.list_documents.assert_not_awaited()


def test_list_library_documents_rejects_too_many_content_type_values():
    service = _service()
    client = _build_client(service)
    query = "&".join(["content_type=pdf"] * 33)

    response = client.get(f"/api/v1/library/documents?{query}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Too many content_type values"
    service.list_documents.assert_not_awaited()
