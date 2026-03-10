import asyncio
import importlib.util
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration
MINIO_SDK_AVAILABLE = importlib.util.find_spec("minio") is not None


@pytest.mark.skipif(
    not MINIO_SDK_AVAILABLE,
    reason="minio SDK is not installed; run `pip install -r requirements.txt` first",
)
@pytest.mark.skipif(
    not os.getenv("MINIO_TEST_ENDPOINT"),
    reason="MINIO_TEST_ENDPOINT is not set; skip MinIO integration test",
)
def test_minio_storage_backend_roundtrip_and_delete_prefix():
    from newbee_notebook.infrastructure.storage.minio_storage_backend import MinIOStorageBackend

    endpoint = os.getenv("MINIO_TEST_ENDPOINT", "")
    access_key = os.getenv("MINIO_TEST_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_TEST_SECRET_KEY", "minioadmin123")
    bucket = os.getenv("MINIO_TEST_BUCKET", "newbee-notebook-test")
    secure = os.getenv("MINIO_TEST_SECURE", "false").lower() == "true"
    public_endpoint = os.getenv("MINIO_TEST_PUBLIC_ENDPOINT") or endpoint

    backend = MinIOStorageBackend(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket_name=bucket,
        secure=secure,
        public_endpoint=public_endpoint,
    )

    prefix = f"it-{uuid4().hex[:10]}"
    md_key = f"{prefix}/markdown/content.md"
    image_key = f"{prefix}/assets/images/demo.jpg"

    async def _run():
        await backend.save_file(md_key, BytesIO(b"# title"), content_type="text/markdown")
        await backend.save_file(image_key, BytesIO(b"img"), content_type="image/jpeg")

        assert await backend.exists(md_key) is True
        assert await backend.get_text(md_key) == "# title"
        assert await backend.get_file(image_key) == b"img"

        temp_download = Path("tmp-minio-download.md")
        try:
            await backend.download_to_path(md_key, str(temp_download))
            assert temp_download.read_text(encoding="utf-8") == "# title"
        finally:
            temp_download.unlink(missing_ok=True)

        listed = sorted(await backend.list_objects(f"{prefix}/"))
        assert listed == [image_key, md_key]

        url = await backend.get_file_url(image_key)
        assert "X-Amz-" in url
        assert bucket in url

        deleted_count = await backend.delete_prefix(f"{prefix}/")
        assert deleted_count >= 2
        assert await backend.exists(md_key) is False

    asyncio.run(_run())
