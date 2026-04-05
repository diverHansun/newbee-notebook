import asyncio
from unittest.mock import AsyncMock

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.scripts.detect_orphans import detect_orphan_documents


def _doc(doc_id: str) -> Document:
    return Document(
        document_id=doc_id,
        title="doc",
        library_id="lib-1",
        status=DocumentStatus.UPLOADED,
    )


def test_detect_orphans_local_storage_mode(tmp_path):
    doc_1 = "11111111-1111-1111-1111-111111111111"
    doc_2 = "22222222-2222-2222-2222-222222222222"
    (tmp_path / doc_1).mkdir()
    (tmp_path / doc_2).mkdir()
    (tmp_path / "not-a-doc").mkdir()
    (tmp_path / doc_1 / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / doc_2 / "b.txt").write_text("b", encoding="utf-8")

    repo = AsyncMock()
    repo.get_batch = AsyncMock(return_value=[_doc(doc_1)])

    orphan_ids = asyncio.run(detect_orphan_documents(str(tmp_path), repo))
    assert orphan_ids == [doc_2]


def test_detect_orphans_remote_storage_mode(tmp_path):
    doc_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    doc_2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    class _FakeStorage:
        async def list_objects(self, prefix: str):  # noqa: ARG002
            return [
                f"{doc_1}/markdown/content.md",
                f"{doc_2}/assets/images/demo.jpg",
                "invalid-prefix/file.txt",
            ]

    repo = AsyncMock()
    repo.get_batch = AsyncMock(return_value=[_doc(doc_1)])

    orphan_ids = asyncio.run(
        detect_orphan_documents(
            str(tmp_path),
            repo,
            storage_backend=_FakeStorage(),
        )
    )
    assert orphan_ids == [doc_2]
