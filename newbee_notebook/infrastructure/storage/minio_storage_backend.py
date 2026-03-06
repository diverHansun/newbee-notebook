"""MinIO object storage backend."""

import asyncio
import mimetypes
from datetime import timedelta
from io import BytesIO
from pathlib import PurePosixPath
from typing import BinaryIO
from urllib.parse import urlsplit

from minio import Minio
from minio.error import S3Error

from .base import StorageBackend


def _normalize_endpoint(endpoint: str, secure: bool) -> tuple[str, bool]:
    """Normalize endpoint to MinIO SDK format (host:port, secure flag)."""
    endpoint = endpoint.strip()
    if not endpoint:
        raise ValueError("MinIO endpoint cannot be empty")

    if "://" not in endpoint:
        return endpoint, secure

    parsed = urlsplit(endpoint)
    if not parsed.netloc:
        raise ValueError(f"Invalid MinIO endpoint: {endpoint}")
    parsed_secure = parsed.scheme.lower() == "https"
    return parsed.netloc, parsed_secure


def _normalize_object_key(object_key: str) -> str:
    """Validate object key to avoid path traversal-like keys."""
    key = object_key.strip().replace("\\", "/")
    if not key:
        raise ValueError("Object key cannot be empty")

    normalized = PurePosixPath(key)
    parts = normalized.parts
    if normalized.is_absolute() or any(part in ("..", "") for part in parts):
        raise ValueError(f"Invalid object key: {object_key}")
    return str(normalized)


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip().replace("\\", "/")
    if not prefix:
        return ""
    return _normalize_object_key(prefix.rstrip("/")) + "/"


class MinIOStorageBackend(StorageBackend):
    """Storage backend using MinIO/S3-compatible object storage."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str = "documents",
        secure: bool = False,
        public_endpoint: str | None = None,
    ) -> None:
        endpoint_host, endpoint_secure = _normalize_endpoint(endpoint, secure)
        self._client = Minio(
            endpoint=endpoint_host,
            access_key=access_key,
            secret_key=secret_key,
            secure=endpoint_secure,
        )
        self._bucket = bucket_name

        if public_endpoint:
            public_host, public_secure = _normalize_endpoint(public_endpoint, endpoint_secure)
            self._public_client = Minio(
                endpoint=public_host,
                access_key=access_key,
                secret_key=secret_key,
                secure=public_secure,
            )
        else:
            self._public_client = self._client

        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    @staticmethod
    def _read_stream_with_length(data: BinaryIO) -> tuple[BinaryIO, int]:
        seekable = getattr(data, "seekable", None)
        if callable(seekable) and data.seekable():
            current = data.tell()
            data.seek(0, 2)
            length = data.tell()
            data.seek(current)
            return data, max(0, length - current)

        blob = data.read()
        stream = BytesIO(blob)
        return stream, len(blob)

    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        key = _normalize_object_key(object_key)
        await asyncio.to_thread(self._save_file_sync, key, data, content_type)
        return key

    def _save_file_sync(self, object_key: str, data: BinaryIO, content_type: str) -> None:
        stream, length = self._read_stream_with_length(data)
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=stream,
            length=length,
            content_type=content_type,
        )

    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        key = _normalize_object_key(object_key)
        guessed_type, _ = mimetypes.guess_type(local_path)
        final_content_type = guessed_type or content_type
        await asyncio.to_thread(self._save_from_path_sync, key, local_path, final_content_type)
        return key

    def _save_from_path_sync(self, object_key: str, local_path: str, content_type: str) -> None:
        self._client.fput_object(
            bucket_name=self._bucket,
            object_name=object_key,
            file_path=local_path,
            content_type=content_type,
        )

    async def get_file(self, object_key: str) -> bytes:
        key = _normalize_object_key(object_key)
        return await asyncio.to_thread(self._get_file_sync, key)

    def _get_file_sync(self, object_key: str) -> bytes:
        response = None
        try:
            response = self._client.get_object(self._bucket, object_key)
            return response.read()
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise FileNotFoundError(f"Object not found: {object_key}") from exc
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        data = await self.get_file(object_key)
        return data.decode(encoding)

    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        key = _normalize_object_key(object_key)
        return await asyncio.to_thread(
            self._public_client.presigned_get_object,
            self._bucket,
            key,
            expires,
        )

    async def delete_file(self, object_key: str) -> None:
        key = _normalize_object_key(object_key)
        await asyncio.to_thread(self._delete_file_sync, key)

    def _delete_file_sync(self, object_key: str) -> None:
        try:
            self._client.stat_object(self._bucket, object_key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise FileNotFoundError(f"Object not found: {object_key}") from exc
            raise
        self._client.remove_object(self._bucket, object_key)

    async def delete_prefix(self, prefix: str) -> int:
        normalized_prefix = _normalize_prefix(prefix)
        return await asyncio.to_thread(self._delete_prefix_sync, normalized_prefix)

    def _delete_prefix_sync(self, prefix: str) -> int:
        objects = self._client.list_objects(
            bucket_name=self._bucket,
            prefix=prefix,
            recursive=True,
        )
        deleted = 0
        for obj in objects:
            self._client.remove_object(self._bucket, obj.object_name)
            deleted += 1
        return deleted

    async def list_objects(self, prefix: str) -> list[str]:
        normalized_prefix = _normalize_prefix(prefix)
        return await asyncio.to_thread(self._list_objects_sync, normalized_prefix)

    def _list_objects_sync(self, prefix: str) -> list[str]:
        objects = self._client.list_objects(
            bucket_name=self._bucket,
            prefix=prefix,
            recursive=True,
        )
        return [obj.object_name for obj in objects]

    async def exists(self, object_key: str) -> bool:
        key = _normalize_object_key(object_key)
        return await asyncio.to_thread(self._exists_sync, key)

    def _exists_sync(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise
