# 存储抽象层设计

本文档定义 StorageBackend 接口规范，以及 LocalStorageBackend (Bind Mount) 和 MinIOStorageBackend 两套实现的设计细节。抽象层是实现平滑迁移的核心机制。

---

## 1. 设计目标

1. **统一接口**: 上层服务 (DocumentService, Celery Worker) 不感知具体存储后端。
2. **环境切换**: 通过环境变量 `STORAGE_BACKEND` 选择存储实现，无需改动业务代码。
3. **最小侵入**: 只改造存储 I/O 层，不涉及 RAG 管线、对话引擎、数据库层。
4. **向后兼容**: LocalStorageBackend 完全包装现有逻辑，行为不变。

---

## 2. 接口定义

### 2.1 StorageBackend 抽象基类

```python
# newbee_notebook/infrastructure/storage/base.py

from abc import ABC, abstractmethod
from pathlib import PurePosixPath
from typing import BinaryIO, Optional
from datetime import timedelta


class StorageBackend(ABC):
    """文档文件存储后端的统一接口。

    所有文件操作通过此接口完成，上层服务不直接操作文件系统或对象存储 API。
    对象键 (object_key) 统一使用 POSIX 路径格式: {document_id}/{category}/{filename}
    例如: 393f579b-.../original/paper.pdf
         393f579b-.../markdown/content.md
         393f579b-.../assets/images/a267b5...jpg
    """

    @abstractmethod
    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """保存文件。

        Args:
            object_key: 对象键，格式为 {document_id}/{category}/{filename}
            data: 文件的二进制流
            content_type: MIME 类型

        Returns:
            存储后的对象键 (与输入 object_key 相同)
        """

    @abstractmethod
    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """从本地文件路径保存到存储后端。

        用于 Celery Worker 处理完成后上传 MinerU 生成的文件。

        Args:
            object_key: 对象键
            local_path: 本地文件绝对路径
            content_type: MIME 类型

        Returns:
            存储后的对象键
        """

    @abstractmethod
    async def get_file(self, object_key: str) -> bytes:
        """读取文件内容。

        Args:
            object_key: 对象键

        Returns:
            文件的完整字节内容

        Raises:
            FileNotFoundError: 对象不存在
        """

    @abstractmethod
    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        """读取文本文件内容。

        用于读取 Markdown 内容等文本文件。

        Args:
            object_key: 对象键
            encoding: 文本编码

        Returns:
            文件的文本内容

        Raises:
            FileNotFoundError: 对象不存在
        """

    @abstractmethod
    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        """获取文件的可访问 URL。

        对于 LocalStorageBackend: 返回 API 路由路径 (如 /api/v1/documents/{id}/assets/...)
        对于 MinIOStorageBackend: 返回 Presigned GET URL

        Args:
            object_key: 对象键
            expires: URL 有效期 (仅对 MinIO 生效)

        Returns:
            可由浏览器直接访问的 URL
        """

    @abstractmethod
    async def delete_file(self, object_key: str) -> None:
        """删除单个文件。

        Args:
            object_key: 对象键

        Raises:
            FileNotFoundError: 对象不存在
        """

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int:
        """删除指定前缀下的所有文件。

        用于删除整个文档的所有文件: delete_prefix("{document_id}/")

        Args:
            prefix: 对象键前缀

        Returns:
            删除的文件数量
        """

    @abstractmethod
    async def list_objects(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有对象键。

        Args:
            prefix: 对象键前缀

        Returns:
            对象键列表
        """

    @abstractmethod
    async def exists(self, object_key: str) -> bool:
        """检查对象是否存在。

        Args:
            object_key: 对象键

        Returns:
            True 如果对象存在
        """
```

### 2.2 对象键命名规范

对象键采用与当前文件系统结构一致的命名:

```
{document_id}/original/{filename}          # 原始上传文件
{document_id}/markdown/content.md          # MinerU 转换后的 Markdown
{document_id}/assets/images/{hash}.jpg     # 提取的图片
{document_id}/assets/meta/layout.json      # 处理元数据
```

这样设计确保:
- 与 legacy `data/documents/{document_id}/` 目录结构一一对应，便于迁移和对象键推导
- `delete_prefix("{document_id}/")` 可以清理某个文档的全部文件
- MinIO 桶中的对象路径直观可读

---

## 3. LocalStorageBackend 实现

包装现有的文件系统操作，行为完全兼容当前方案。

```python
# newbee_notebook/infrastructure/storage/local_storage_backend.py

import mimetypes
from pathlib import Path
from typing import BinaryIO
from datetime import timedelta

from .base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """基于本地文件系统的存储后端 (Bind Mount)。

    文件存储在 {base_dir}/{object_key} 路径下，
    其中 base_dir 默认为 data/documents。
    """

    def __init__(self, base_dir: str):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        """将对象键解析为本地文件路径，并校验安全性。"""
        path = self._base_dir / object_key
        # 防止路径遍历
        resolved = path.resolve()
        if not str(resolved).startswith(str(self._base_dir.resolve())):
            raise ValueError(f"Invalid object key: {object_key}")
        return path

    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            while chunk := data.read(8192):
                f.write(chunk)
        return object_key

    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        import shutil
        target = self._resolve_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target)
        return object_key

    async def get_file(self, object_key: str) -> bytes:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        return path.read_bytes()

    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        return path.read_text(encoding=encoding)

    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        # 本地模式: 返回 API 路由路径，由 FastAPI asset 路由处理
        # object_key 格式: {document_id}/assets/images/{hash}.jpg
        parts = object_key.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid object key format: {object_key}")
        document_id = parts[0]
        asset_path = parts[1]
        # 如果是 assets 下的文件，返回 asset API 路径
        if asset_path.startswith("assets/"):
            relative = asset_path[len("assets/"):]
            return f"/api/v1/documents/{document_id}/assets/{relative}"
        # 其他文件返回通用下载路径
        return f"/api/v1/documents/{document_id}/download"

    async def delete_file(self, object_key: str) -> None:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {object_key}")
        path.unlink()

    async def delete_prefix(self, prefix: str) -> int:
        import shutil
        path = self._resolve_path(prefix.rstrip("/"))
        if not path.exists():
            return 0
        # 统计文件数
        count = sum(1 for _ in path.rglob("*") if _.is_file())
        shutil.rmtree(path)
        return count

    async def list_objects(self, prefix: str) -> list[str]:
        path = self._resolve_path(prefix.rstrip("/"))
        if not path.exists():
            return []
        base = self._base_dir
        return [
            str(f.relative_to(base)).replace("\\", "/")
            for f in path.rglob("*")
            if f.is_file()
        ]

    async def exists(self, object_key: str) -> bool:
        path = self._resolve_path(object_key)
        return path.exists() and path.is_file()
```

---

## 4. MinIOStorageBackend 实现

基于 MinIO Python SDK (`minio-py`) 实现，利用 Presigned URL 机制为前端提供直接访问能力。

```python
# newbee_notebook/infrastructure/storage/minio_storage_backend.py

import mimetypes
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from .base import StorageBackend


class MinIOStorageBackend(StorageBackend):
    """基于 MinIO 对象存储的存储后端。

    所有文件存储在单个桶 (bucket) 中，以 document_id 为前缀组织。
    前端通过 Presigned URL 直接从 MinIO 获取文件，绕过 FastAPI 后端。
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str = "documents",
        secure: bool = False,
        public_endpoint: str | None = None,
    ):
        """初始化 MinIO 存储后端。

        Args:
            endpoint: MinIO 服务地址 (如 localhost:9000)
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket_name: 桶名称
            secure: 是否使用 HTTPS
            public_endpoint: 外部可访问的 MinIO 地址。
                Docker 内部使用 minio:9000，但浏览器需要 localhost:9000。
                如果不设置，默认使用 endpoint。
        """
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket_name
        self._public_endpoint = public_endpoint or endpoint
        self._secure = secure

        # 用于生成 Presigned URL 的客户端 (使用外部可达地址)
        if public_endpoint and public_endpoint != endpoint:
            self._public_client = Minio(
                endpoint=public_endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
        else:
            self._public_client = self._client

        self._ensure_bucket()

    def _ensure_bucket(self):
        """确保桶存在，不存在则创建。"""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    async def save_file(
        self,
        object_key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        # 获取数据长度
        data.seek(0, 2)
        length = data.tell()
        data.seek(0)

        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=data,
            length=length,
            content_type=content_type,
        )
        return object_key

    async def save_from_path(
        self,
        object_key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        # 自动检测 MIME 类型
        if content_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(local_path)
            if guessed:
                content_type = guessed

        self._client.fput_object(
            bucket_name=self._bucket,
            object_name=object_key,
            file_path=local_path,
            content_type=content_type,
        )
        return object_key

    async def get_file(self, object_key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, object_key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {object_key}")
            raise

    async def get_text(self, object_key: str, encoding: str = "utf-8") -> str:
        data = await self.get_file(object_key)
        return data.decode(encoding)

    async def get_file_url(
        self,
        object_key: str,
        expires: timedelta = timedelta(hours=2),
    ) -> str:
        """生成 Presigned GET URL。

        使用 public_client (外部可达地址) 生成 URL，确保浏览器可以直接访问。
        """
        return self._public_client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=object_key,
            expires=expires,
        )

    async def delete_file(self, object_key: str) -> None:
        try:
            self._client.stat_object(self._bucket, object_key)
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {object_key}")
            raise
        self._client.remove_object(self._bucket, object_key)

    async def delete_prefix(self, prefix: str) -> int:
        objects = self._client.list_objects(
            self._bucket, prefix=prefix, recursive=True
        )
        count = 0
        for obj in objects:
            self._client.remove_object(self._bucket, obj.object_name)
            count += 1
        return count

    async def list_objects(self, prefix: str) -> list[str]:
        objects = self._client.list_objects(
            self._bucket, prefix=prefix, recursive=True
        )
        return [obj.object_name for obj in objects]

    async def exists(self, object_key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_key)
            return True
        except S3Error:
            return False
```

---

## 5. 工厂函数与依赖注入

### 5.1 存储后端工厂

> 说明: 当前实现已区分 `get_storage_backend()`（离线/测试允许 local）与 `get_runtime_storage_backend()`（运行时强制 MinIO）。下面示例以当前代码为准。

```python
# newbee_notebook/infrastructure/storage/__init__.py

import os
from functools import lru_cache

from .base import StorageBackend
from .local_storage_backend import LocalStorageBackend
from .minio_storage_backend import MinIOStorageBackend


def _build_storage_backend(*, allow_local: bool) -> StorageBackend:
    backend_type = os.getenv("STORAGE_BACKEND", "local").lower()

    if backend_type == "minio":
        return MinIOStorageBackend(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
            bucket_name=os.getenv("MINIO_BUCKET", "documents"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT"),
        )
    if backend_type == "local":
        if not allow_local:
            raise RuntimeError("Runtime storage backend requires MinIO (STORAGE_BACKEND=minio)")
        documents_dir = os.getenv("DOCUMENTS_DIR", "data/documents")
        return LocalStorageBackend(base_dir=documents_dir)

    raise ValueError(f"Unsupported STORAGE_BACKEND={backend_type!r}")


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    return _build_storage_backend(allow_local=True)


@lru_cache(maxsize=1)
def get_runtime_storage_backend() -> StorageBackend:
    return _build_storage_backend(allow_local=False)
```

### 5.2 FastAPI 依赖注入

```python
# newbee_notebook/api/dependencies.py (新增)

from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend


def get_storage() -> StorageBackend:
    return get_runtime_storage_backend()
```

### 5.3 环境变量配置示例

```bash
# .env / .env.production - 运行时统一使用 MinIO
STORAGE_BACKEND=minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your-secure-password
MINIO_BUCKET=documents
MINIO_SECURE=false
MINIO_PUBLIC_ENDPOINT=localhost:9000

# DOCUMENTS_DIR 仅供离线脚本 / LocalStorageBackend / legacy 迁移使用
DOCUMENTS_DIR=data/documents
```

---

## 6. 改造影响范围

引入存储抽象层后，以下模块需要调整:

| 模块 | 当前方式 | 改造后 |
|------|----------|--------|
| `local_storage.save_upload_file()` | 直接 `Path.write_bytes()` | 调用 `storage.save_file()` |
| `document_service.get_document_content()` | `Path.read_text()` | 调用 `storage.get_text()` |
| `document_service.get_asset_path()` | 返回 `Path` 供 `FileResponse` | 返回 URL (本地模式仍可返回路径) |
| `document_tasks.py` (Celery) | 历史上直接写入 `data/documents/` | 调用 `storage.save_from_path()` |
| `document_service.delete_document()` | `shutil.rmtree()` | 调用 `storage.delete_prefix()` |
| `detect_orphans.py` | 扫描文件系统目录 | 调用 `storage.list_objects()` |

**不需要改动的模块**:
- RAG 管线 (索引、检索、分块)
- 对话引擎 (SessionManager, ChatEngine)
- 数据库层 (Repository, Entity)
- API 路由定义 (路由路径不变)

---

## 7. 设计要点

### 7.1 同步 vs 异步

MinIO Python SDK (`minio-py`) 是同步库。在 async FastAPI 中使用时，应通过 `asyncio.to_thread()` 或在 `run_in_executor` 中执行 I/O 操作，避免阻塞事件循环。

上述实现中标记为 `async def` 是接口层面的设计，实际 MinIO 调用可能需要包装:

```python
import asyncio

async def get_file(self, object_key: str) -> bytes:
    return await asyncio.to_thread(self._sync_get_file, object_key)

def _sync_get_file(self, object_key: str) -> bytes:
    response = self._client.get_object(self._bucket, object_key)
    data = response.read()
    response.close()
    response.release_conn()
    return data
```

### 7.2 Presigned URL 的 Docker 网络问题

Docker 内部的 MinIO 服务使用容器名 `minio` 作为主机名，但浏览器无法访问 `http://minio:9000/...`。因此需要 `public_endpoint` 参数:

```
Docker 内部通信: minio:9000         (Celery Worker → MinIO)
浏览器访问:      localhost:9000      (Browser → MinIO，通过端口映射)
Presigned URL:   使用 public_client  (生成 localhost:9000 开头的 URL)
```

### 7.3 Content-Type 的重要性

上传到 MinIO 时必须设置正确的 `content_type`:
- 图片: `image/jpeg`, `image/png`
- Markdown: `text/markdown`
- PDF: `application/pdf`
- JSON: `application/json`

如果 content_type 为默认的 `application/octet-stream`，浏览器通过 Presigned URL 访问时会触发下载而非内联显示。

MinIO 架构集成的详细配置见 [03-minio-architecture.md](./03-minio-architecture.md)。
