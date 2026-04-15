import asyncio

from newbee_notebook.scripts.migrate_to_minio import (
    migrate_documents_to_minio,
    verify_migration,
)


class _FakeBackend:
    def __init__(self) -> None:
        self.uploaded: dict[str, str] = {}

    async def save_from_path(self, object_key: str, local_path: str, content_type: str = "application/octet-stream") -> str:
        self.uploaded[object_key] = content_type
        return local_path

    async def list_objects(self, prefix: str) -> list[str]:
        if prefix:
            return [k for k in self.uploaded if k.startswith(prefix)]
        return sorted(self.uploaded.keys())


def test_migrate_documents_to_minio_dry_run(tmp_path):
    doc_id = "393f579b-2318-42eb-8a0a-9b5232900108"
    (tmp_path / doc_id).mkdir()
    (tmp_path / doc_id / "a.md").write_text("# a", encoding="utf-8")
    (tmp_path / doc_id / "b.jpg").write_bytes(b"jpg")

    backend = _FakeBackend()
    stats = asyncio.run(
        migrate_documents_to_minio(
            documents_dir=tmp_path,
            backend=backend,  # type: ignore[arg-type]
            dry_run=True,
        )
    )

    assert stats.total_files == 2
    assert stats.migrated_files == 2
    assert stats.failed_files == 0
    assert backend.uploaded == {}


def test_verify_migration_reports_missing_files(tmp_path):
    doc_id = "393f579b-2318-42eb-8a0a-9b5232900108"
    (tmp_path / doc_id).mkdir()
    (tmp_path / doc_id / "a.md").write_text("# a", encoding="utf-8")
    (tmp_path / doc_id / "b.jpg").write_bytes(b"jpg")

    backend = _FakeBackend()
    backend.uploaded[f"{doc_id}/a.md"] = "text/markdown"

    total, missing = asyncio.run(
        verify_migration(
            documents_dir=tmp_path,
            backend=backend,  # type: ignore[arg-type]
        )
    )

    assert total == 2
    assert missing == [f"{doc_id}/b.jpg"]


def test_migrate_documents_to_minio_skips_root_files_and_non_uuid_dirs(tmp_path):
    uuid_dir = tmp_path / "393f579b-2318-42eb-8a0a-9b5232900108"
    uuid_dir.mkdir()
    (uuid_dir / "markdown").mkdir()
    (uuid_dir / "markdown" / "content.md").write_text("# ok", encoding="utf-8")

    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "not-a-document").mkdir()
    (tmp_path / "not-a-document" / "junk.txt").write_text("x", encoding="utf-8")

    backend = _FakeBackend()
    stats = asyncio.run(
        migrate_documents_to_minio(
            documents_dir=tmp_path,
            backend=backend,  # type: ignore[arg-type]
            dry_run=False,
        )
    )

    assert stats.total_files == 1
    assert stats.migrated_files == 1
    assert stats.failed_files == 0
    assert sorted(backend.uploaded.keys()) == [
        "393f579b-2318-42eb-8a0a-9b5232900108/markdown/content.md"
    ]
