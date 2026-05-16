import asyncio

from newbee_notebook.application.services.library_service import LibraryService
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.document_type import DocumentType


class _FakeLibraryRepo:
    pass


class _FakeRefRepo:
    pass


class _FakeDocumentRepo:
    def __init__(self) -> None:
        self.list_kwargs = None
        self.count_kwargs = None

    async def list_by_library(self, **kwargs):
        self.list_kwargs = kwargs
        return ["doc-1"]

    async def count_by_library(self, **kwargs):
        self.count_kwargs = kwargs
        return 1


def test_list_documents_passes_content_type_filters_to_repository():
    document_repo = _FakeDocumentRepo()
    service = LibraryService(
        library_repo=_FakeLibraryRepo(),
        document_repo=document_repo,
        ref_repo=_FakeRefRepo(),
    )

    docs, total = asyncio.run(
        service.list_documents(
            limit=5,
            offset=10,
            status=DocumentStatus.COMPLETED,
            content_types=[DocumentType.PDF, DocumentType.DOCX],
        )
    )

    assert docs == ["doc-1"]
    assert total == 1
    assert document_repo.list_kwargs == {
        "limit": 5,
        "offset": 10,
        "status": DocumentStatus.COMPLETED,
        "content_types": [DocumentType.PDF, DocumentType.DOCX],
    }
    assert document_repo.count_kwargs == {
        "status": DocumentStatus.COMPLETED,
        "content_types": [DocumentType.PDF, DocumentType.DOCX],
    }
