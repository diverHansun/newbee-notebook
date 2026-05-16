import asyncio

from sqlalchemy.dialects import postgresql

from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.document_type import DocumentType
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def scalars(self):
        return _FakeScalars()

    def scalar(self):
        return 0


class _CaptureSession:
    def __init__(self) -> None:
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return _FakeResult()


def _compile_sql(query) -> str:
    return str(
        query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_list_by_library_applies_content_type_filter_with_status():
    session = _CaptureSession()
    repo = DocumentRepositoryImpl(session)

    asyncio.run(
        repo.list_by_library(
            limit=10,
            offset=0,
            status=DocumentStatus.COMPLETED,
            content_types=[DocumentType.PDF, DocumentType.DOCX],
        )
    )

    sql = _compile_sql(session.queries[0])
    assert "documents.status = 'completed'" in sql
    assert "documents.content_type IN ('pdf', 'docx')" in sql


def test_count_by_library_applies_content_type_filter():
    session = _CaptureSession()
    repo = DocumentRepositoryImpl(session)

    asyncio.run(
        repo.count_by_library(
            status=DocumentStatus.COMPLETED,
            content_types=[DocumentType.XLSX, DocumentType.CSV],
        )
    )

    sql = _compile_sql(session.queries[0])
    assert "documents.status = 'completed'" in sql
    assert "documents.content_type IN ('xlsx', 'csv')" in sql


def test_list_by_library_ignores_empty_content_type_filter():
    session = _CaptureSession()
    repo = DocumentRepositoryImpl(session)

    asyncio.run(repo.list_by_library(content_types=[]))

    sql = _compile_sql(session.queries[0])
    assert "documents.content_type IN" not in sql
