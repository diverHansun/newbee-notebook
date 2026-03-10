import asyncio
from pathlib import Path
from types import SimpleNamespace

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.infrastructure.tasks import document_tasks


class _FakeRuntimeStorageBackend:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects
        self.download_calls: list[tuple[str, str]] = []

    async def exists(self, object_key: str) -> bool:
        return object_key in self._objects

    async def download_to_path(self, object_key: str, local_path: str) -> None:
        self.download_calls.append((object_key, local_path))
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._objects[object_key])


def test_materialize_document_source_downloads_remote_object_and_cleans_up(monkeypatch):
    document = Document(
        document_id="doc-src-1",
        title="demo.pdf",
        status=DocumentStatus.UPLOADED,
        file_path="documents/doc-src-1/original/demo.pdf",
    )
    storage = _FakeRuntimeStorageBackend(
        {
            "doc-src-1/original/demo.pdf": b"%PDF-1.7",
        }
    )
    monkeypatch.setattr(document_tasks, "get_runtime_storage_backend", lambda: storage)

    state: dict[str, object] = {}

    async def _run():
        async with document_tasks._materialize_document_source(document) as local_path:
            state["path"] = local_path
            assert local_path.exists()
            assert local_path.suffix == ".pdf"
            assert local_path.read_bytes() == b"%PDF-1.7"

    asyncio.run(_run())

    assert storage.download_calls[0][0] == "doc-src-1/original/demo.pdf"
    assert state["path"] is not None
    assert not Path(state["path"]).exists()


def test_load_markdown_nodes_downloads_remote_content_before_reading(monkeypatch):
    document = Document(
        document_id="doc-md-1",
        library_id="lib-1",
        notebook_id="nb-1",
        title="converted.md",
        status=DocumentStatus.CONVERTED,
        content_path="documents/doc-md-1/markdown/content.md",
    )
    storage = _FakeRuntimeStorageBackend(
        {
            "doc-md-1/markdown/content.md": b"# Remote Title\n\nhello",
        }
    )
    monkeypatch.setattr(document_tasks, "get_runtime_storage_backend", lambda: storage)

    observed: dict[str, str] = {}

    class _FakeMarkdownReader:
        def __init__(self, **kwargs):  # noqa: ARG002
            pass

        def load_data(self, *, file: str, extra_info: dict):
            path = Path(file)
            observed["reader_path"] = file
            observed["reader_text"] = path.read_text(encoding="utf-8")
            observed["extra_title"] = extra_info["title"]
            return ["doc"]

    def _fake_split_documents(docs, chunk_size: int, chunk_overlap: int):  # noqa: ARG001
        return [
            SimpleNamespace(metadata={}, node_id="node-1"),
            SimpleNamespace(metadata={}, node_id="node-2"),
        ]

    monkeypatch.setattr(document_tasks, "MarkdownReader", _FakeMarkdownReader)
    monkeypatch.setattr(document_tasks, "split_documents", _fake_split_documents)

    nodes = asyncio.run(document_tasks._load_markdown_nodes(document, document.content_path or ""))

    assert observed["reader_text"] == "# Remote Title\n\nhello"
    assert observed["extra_title"] == "converted.md"
    assert storage.download_calls[0][0] == "doc-md-1/markdown/content.md"
    assert not Path(observed["reader_path"]).exists()
    assert [node.metadata["chunk_index"] for node in nodes] == [0, 1]
    assert all(node.metadata["document_id"] == "doc-md-1" for node in nodes)
