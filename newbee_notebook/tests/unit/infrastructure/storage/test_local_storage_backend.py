import asyncio
from io import BytesIO
from pathlib import Path

import pytest

from newbee_notebook.infrastructure.storage.local_storage_backend import LocalStorageBackend


@pytest.mark.unit
def test_local_storage_backend_roundtrip_and_prefix_delete(tmp_path):
    backend = LocalStorageBackend(base_dir=str(tmp_path))

    async def _run():
        md_key = "doc-1/markdown/content.md"
        image_key = "doc-1/assets/images/demo.jpg"

        await backend.save_file(md_key, BytesIO(b"# title\n\nhello"), content_type="text/markdown")
        await backend.save_file(image_key, BytesIO(b"img"), content_type="image/jpeg")

        assert await backend.exists(md_key) is True
        assert await backend.exists(image_key) is True
        assert await backend.get_text(md_key) == "# title\n\nhello"
        assert await backend.get_file(image_key) == b"img"

        download_path = tmp_path / "downloads" / "content.md"
        await backend.download_to_path(md_key, str(download_path))
        assert download_path.read_text(encoding="utf-8") == "# title\n\nhello"

        listed = sorted(await backend.list_objects("doc-1/"))
        assert listed == [image_key, md_key]

        deleted_count = await backend.delete_prefix("doc-1/")
        assert deleted_count == 2
        assert await backend.exists(md_key) is False
        assert await backend.exists(image_key) is False

    asyncio.run(_run())


@pytest.mark.unit
def test_local_storage_backend_get_file_url_for_assets_and_download(tmp_path):
    backend = LocalStorageBackend(base_dir=str(tmp_path))

    async def _run():
        asset_url = await backend.get_file_url("doc-2/assets/images/a.png")
        assert asset_url == "/api/v1/documents/doc-2/assets/images/a.png"

        download_url = await backend.get_file_url("doc-2/original/a.pdf")
        assert download_url == "/api/v1/documents/doc-2/download"

    asyncio.run(_run())


@pytest.mark.unit
def test_local_storage_backend_rejects_path_traversal(tmp_path):
    backend = LocalStorageBackend(base_dir=str(tmp_path))

    async def _run():
        with pytest.raises(ValueError):
            await backend.save_file("../evil.txt", BytesIO(b"bad"))

    asyncio.run(_run())
