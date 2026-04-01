import asyncio

from newbee_notebook.infrastructure.storage import minio_storage_backend as minio_module


class _FakeMinio:
    instances = []

    def __init__(
        self,
        endpoint,
        access_key=None,
        secret_key=None,
        session_token=None,
        secure=True,
        region=None,
        http_client=None,
        credentials=None,
        cert_check=True,
    ):
        self.endpoint = endpoint
        self.region = region
        self.region_queries = []
        self.presign_calls = []
        _FakeMinio.instances.append(self)

    def bucket_exists(self, bucket_name):
        return True

    def make_bucket(self, bucket_name):
        raise AssertionError(f"bucket should already exist: {bucket_name}")

    def _get_region(self, bucket_name):
        self.region_queries.append(bucket_name)
        return "us-east-1"

    def presigned_get_object(self, bucket_name, object_name, expires):
        self.presign_calls.append((bucket_name, object_name, expires))
        return f"http://{self.endpoint}/{bucket_name}/{object_name}?X-Amz-Signature=test"


def test_get_file_url_uses_internal_region_for_public_endpoint(monkeypatch):
    _FakeMinio.instances = []
    monkeypatch.setattr(minio_module, "Minio", _FakeMinio)

    backend = minio_module.MinIOStorageBackend(
        endpoint="minio:9000",
        access_key="minioadmin",
        secret_key="minioadmin123",
        bucket_name="documents",
        secure=False,
        public_endpoint="http://localhost:9000",
    )

    internal_client, public_client = _FakeMinio.instances
    assert internal_client.endpoint == "minio:9000"
    assert internal_client.region_queries == ["documents"]
    assert public_client.endpoint == "localhost:9000"
    assert public_client.region == "us-east-1"
    assert public_client.region_queries == []

    url = asyncio.run(backend.get_file_url("doc-1/assets/images/a.png"))

    assert url.startswith("http://localhost:9000/documents/doc-1/assets/images/a.png?")
    assert public_client.presign_calls[0][0] == "documents"
    assert public_client.presign_calls[0][1] == "doc-1/assets/images/a.png"
