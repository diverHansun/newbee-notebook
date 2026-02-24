# 迁移计划: 分阶段实施路径

本文档定义从 Bind Mount 到 MinIO 的分阶段迁移路径，包括任务拆分、依赖关系、验收标准和回滚策略。

---

## 1. 迁移前提条件

在开始实际迁移之前，以下条件必须满足:

| 条件 | 说明 | 当前状态 |
|------|------|----------|
| frontend-v1 第一版基本可用 | 三列布局、Markdown 渲染、图片加载正常工作 | 待开发 |
| 前后端联调完成基础流程 | 文档上传 → 处理 → 查看 → 对话 全链路通过 | 待验证 |
| 当前 Bind Mount 方案稳定 | 无遗留 bug，清理工具正常使用 | 已完成 (improve-6) |
| Docker 环境正常 | PostgreSQL, Redis, Elasticsearch, Celery 运行稳定 | 已验证 |

---

## 2. 分阶段实施路径

### 全局视图

```
Phase 0: 存储抽象层 (可提前实施，不影响现有功能)
    |
    v
Phase 1: MinIO 服务集成 (Docker Compose + 基础验证)
    |
    v
Phase 2: Celery Worker 改造 (文件上传走 StorageBackend)
    |
    v
Phase 3: 内容服务层改造 (Markdown 路径替换 + Presigned URL)
    |
    v
Phase 4: 数据迁移 + 全面切换
```

---

## 3. Phase 0: 存储抽象层

**目标**: 引入 StorageBackend 接口和 LocalStorageBackend，不改变任何运行时行为。

**时机**: 可在前端开发期间提前完成，不阻塞其他工作。

### 3.1 任务清单

| 编号 | 任务 | 预估时长 |
|------|------|----------|
| P0-1 | 创建 `infrastructure/storage/base.py`，定义 StorageBackend ABC | 0.5h |
| P0-2 | 创建 `infrastructure/storage/local_storage_backend.py`，包装现有文件操作 | 1h |
| P0-3 | 创建 `infrastructure/storage/__init__.py`，实现工厂函数 | 0.5h |
| P0-4 | 在 `api/dependencies.py` 中注册 `get_storage` 依赖 | 0.5h |
| P0-5 | 单元测试: LocalStorageBackend 的 CRUD 操作 | 1h |

**Phase 0 总计: ~3.5h**

### 3.2 验收标准

- 所有现有测试通过 (行为不变)
- `STORAGE_BACKEND=local` 时功能与改造前完全一致
- LocalStorageBackend 单元测试覆盖所有接口方法

### 3.3 文件变更清单

```
新增:
  newbee_notebook/infrastructure/storage/base.py
  newbee_notebook/infrastructure/storage/local_storage_backend.py
  newbee_notebook/infrastructure/storage/__init__.py
  tests/unit/infrastructure/storage/test_local_storage_backend.py

修改:
  newbee_notebook/api/dependencies.py     (新增 get_storage)
  .env.example                            (新增 STORAGE_BACKEND 说明)
```

---

## 4. Phase 1: MinIO 服务集成

**目标**: 在 Docker Compose 中添加 MinIO 服务，实现 MinIOStorageBackend 并通过基础验证。

**前置依赖**: Phase 0 完成。

### 4.1 任务清单

| 编号 | 任务 | 预估时长 |
|------|------|----------|
| P1-1 | docker-compose.yml 新增 MinIO 服务 (profiles: minio) | 0.5h |
| P1-2 | 创建 `infrastructure/storage/minio_storage_backend.py` | 1.5h |
| P1-3 | 工厂函数支持 `STORAGE_BACKEND=minio` 分支 | 0.5h |
| P1-4 | requirements.txt 新增 minio 依赖 | 0.5h |
| P1-5 | .env.example 追加 MinIO 配置项 | 0.5h |
| P1-6 | 集成测试: MinIOStorageBackend CRUD 操作 | 1h |
| P1-7 | 验证 Presigned URL 浏览器可达性 | 0.5h |

**Phase 1 总计: ~5h**

### 4.2 验收标准

- `docker compose --profile minio up -d` 启动成功
- MinIO Web Console (`localhost:9001`) 可访问
- MinIOStorageBackend 集成测试全部通过
- Presigned URL 在浏览器中可直接访问文件

### 4.3 文件变更清单

```
新增:
  newbee_notebook/infrastructure/storage/minio_storage_backend.py
  tests/integration/storage/test_minio_storage_backend.py

修改:
  docker-compose.yml                      (新增 minio service)
  newbee_notebook/infrastructure/storage/__init__.py  (工厂函数扩展)
  requirements.txt                        (新增 minio>=7.2.0)
  .env.example                            (新增 MinIO 配置项)
```

---

## 5. Phase 2: Celery Worker 改造

**目标**: Celery Worker 的文档处理流程使用 StorageBackend 上传文件，而非直接写入文件系统。

**前置依赖**: Phase 1 完成。

### 5.1 任务清单

| 编号 | 任务 | 预估时长 |
|------|------|----------|
| P2-1 | `local_storage.save_upload_file()` 改为调用 StorageBackend | 1h |
| P2-2 | `document_tasks.py` 中 MinerU 处理结果上传改造 | 2h |
| P2-3 | `document_processing/store.py` Markdown 保存改造 | 1h |
| P2-4 | Celery Worker Docker 环境变量配置 (MINIO_ENDPOINT 等) | 0.5h |
| P2-5 | 端到端测试: 上传 PDF → 处理 → 文件存入 MinIO | 1h |

**Phase 2 总计: ~5.5h**

### 5.2 关键改造点

**Celery Worker 中的文件写入路径**:

当前 MinerU 转换后，文件直接写入 `data/documents/{id}/` 目录。改造后:

```python
# 改造前 (document_tasks.py)
content_path = Path(documents_dir) / document_id / "markdown" / "content.md"
content_path.parent.mkdir(parents=True, exist_ok=True)
content_path.write_text(markdown_content, encoding="utf-8")

# 改造后
storage = get_storage_backend()
await storage.save_file(
    object_key=f"{document_id}/markdown/content.md",
    data=BytesIO(markdown_content.encode("utf-8")),
    content_type="text/markdown",
)
```

**MinerU 图片处理**:

MinerU 先将图片提取到本地临时目录，然后需要上传到存储后端:

```python
# 改造后: 遍历 MinerU 输出的图片目录，逐一上传
for image_file in mineru_output_dir.glob("images/*"):
    await storage.save_from_path(
        object_key=f"{document_id}/assets/images/{image_file.name}",
        local_path=str(image_file),
    )
```

### 5.3 Markdown 图片路径重写时机

MinerU 原始输出中的图片引用是相对路径 (如 `images/xxx.jpg`)。当前处理流程已在保存 Markdown 时将其重写为 API 路径。

改造后，这一重写逻辑保持不变。Markdown 中仍然嵌入 `/api/v1/documents/{id}/assets/images/...` 路径。实际的 URL 替换发生在 Phase 3 的 ContentService 中，在读取时动态转换。

这样设计确保:
- 存储的 Markdown 内容与存储后端无关 (不包含 MinIO URL)
- 切换存储后端不需要修改已存储的 Markdown 文件
- 本地模式下 API 路径直接可用，MinIO 模式下动态替换

### 5.4 验收标准

- 上传文件 → Celery 处理 → 文件出现在 MinIO 桶中
- MinIO Web Console 可查看处理后的 Markdown、图片、元数据
- `STORAGE_BACKEND=local` 时行为与改造前一致

---

## 6. Phase 3: 内容服务层改造

**目标**: DocumentService 通过 ContentService 返回经路径替换的 Markdown 内容，实现图片直连 MinIO。

**前置依赖**: Phase 2 完成。

### 6.1 任务清单

| 编号 | 任务 | 预估时长 |
|------|------|----------|
| P3-1 | 创建 `application/services/content_service.py` | 1h |
| P3-2 | `document_service.get_document_content()` 接入 ContentService | 1h |
| P3-3 | `document_service.get_asset_path()` 支持 MinIO 重定向 | 0.5h |
| P3-4 | 端到端测试: 前端打开文档 → 图片从 MinIO 加载 | 1h |
| P3-5 | 性能验证: 对比图片加载时间 | 0.5h |

**Phase 3 总计: ~4h**

### 6.2 验收标准

- 前端打开文档阅读器，Markdown 正常渲染
- 浏览器开发者工具中确认图片请求指向 MinIO (非 FastAPI)
- 100 张图片的文档加载时间显著改善
- `STORAGE_BACKEND=local` 时行为不变

---

## 7. Phase 4: 数据迁移与全面切换

**目标**: 将现有 `data/documents/` 中的文件迁移到 MinIO，验证全链路后正式切换。

**前置依赖**: Phase 3 完成且验证通过。

### 7.1 任务清单

| 编号 | 任务 | 预估时长 |
|------|------|----------|
| P4-1 | 编写数据迁移脚本 `scripts/migrate_to_minio.py` | 1.5h |
| P4-2 | 执行数据迁移 (本地文件 → MinIO) | 0.5h |
| P4-3 | 迁移验证: 对比文件数量和大小 | 0.5h |
| P4-4 | 清理工具适配 (make clean-doc 支持 MinIO) | 1h |
| P4-5 | 孤儿检测适配 (detect_orphans 支持 MinIO) | 0.5h |
| P4-6 | 更新 .env 切换到 `STORAGE_BACKEND=minio` | 0.5h |
| P4-7 | 全链路回归测试 | 1h |

**Phase 4 总计: ~5.5h**

### 7.2 数据迁移脚本

```python
# scripts/migrate_to_minio.py

"""将本地文件系统中的文档文件迁移到 MinIO。

用法: python -m scripts.migrate_to_minio --documents-dir data/documents

迁移逻辑:
1. 扫描 data/documents/ 下所有 UUID 目录
2. 遍历每个目录下的所有文件
3. 上传到 MinIO 桶中，保持相同的对象键结构
4. 验证上传文件数量和大小
"""

import asyncio
import mimetypes
from pathlib import Path

from newbee_notebook.infrastructure.storage import get_storage_backend


async def migrate(documents_dir: str):
    storage = get_storage_backend()
    doc_path = Path(documents_dir)

    total_files = 0
    total_size = 0
    errors = []

    for doc_dir in sorted(doc_path.iterdir()):
        if not doc_dir.is_dir():
            continue

        document_id = doc_dir.name
        files = list(doc_dir.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())

        print(f"  [{document_id}] {file_count} files...")

        for file_path in files:
            if not file_path.is_file():
                continue

            relative = file_path.relative_to(doc_path)
            object_key = str(relative).replace("\\", "/")

            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"

            try:
                await storage.save_from_path(
                    object_key=object_key,
                    local_path=str(file_path),
                    content_type=content_type,
                )
                total_files += 1
                total_size += file_path.stat().st_size
            except Exception as e:
                errors.append((object_key, str(e)))
                print(f"    ERROR: {object_key} - {e}")

    print(f"\nMigration complete:")
    print(f"  Files: {total_files}")
    print(f"  Size: {total_size / (1024*1024):.1f} MB")
    if errors:
        print(f"  Errors: {len(errors)}")
        for key, err in errors:
            print(f"    - {key}: {err}")
```

### 7.3 验收标准

- MinIO 中的文件数量和大小与本地文件系统一致
- 全链路回归: 上传、处理、查看、对话均正常
- 清理工具在 MinIO 模式下正常工作
- 切回 `STORAGE_BACKEND=local` 时现有功能不受影响

---

## 8. 回滚策略

### 8.1 任意 Phase 回滚

由于存储抽象层和环境变量控制机制的存在，任何阶段都可以通过修改 `.env` 回退:

```bash
# 回滚到 Bind Mount 模式
STORAGE_BACKEND=local
```

此操作立即生效，无需代码变更。

### 8.2 各阶段回滚条件

| Phase | 回滚触发条件 | 回滚操作 |
|-------|-------------|----------|
| Phase 0 | 抽象层引入 bug | 回退 git commit，移除抽象层代码 |
| Phase 1 | MinIO 服务不稳定 | `docker compose --profile minio down`，切回 local |
| Phase 2 | Celery 处理失败 | 切回 `STORAGE_BACKEND=local`，重新处理失败文档 |
| Phase 3 | 前端图片加载异常 | 切回 local，图片恢复 API 路径访问 |
| Phase 4 | 迁移后数据不一致 | 切回 local，本地文件仍保留未删除 |

### 8.3 数据安全

数据迁移 (Phase 4) 采用**复制而非移动**策略:
- 本地 `data/documents/` 目录在迁移完成后不自动删除
- 需要人工确认 MinIO 数据完整后，再手动清理本地文件
- 这确保在任何阶段都可以安全回退到 Bind Mount 模式

---

## 9. 总时间线

| Phase | 内容 | 预估时长 | 前置依赖 |
|-------|------|----------|----------|
| Phase 0 | 存储抽象层 | ~3.5h | 无 (可提前) |
| Phase 1 | MinIO 服务集成 | ~5h | Phase 0 |
| Phase 2 | Celery Worker 改造 | ~5.5h | Phase 1 |
| Phase 3 | 内容服务层改造 | ~4h | Phase 2 |
| Phase 4 | 数据迁移 + 切换 | ~5.5h | Phase 3 |
| **总计** | | **~23.5h** | |

### 9.1 推荐实施节奏

```
前端开发期间:
  - 完成 Phase 0 (存储抽象层，无运行时影响)

前端第一版联调后:
  - Phase 1 → Phase 2 → Phase 3 (连续实施，每个 Phase 完成后验证)

功能稳定后:
  - Phase 4 (数据迁移，正式切换)
```

---

## 10. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| MinIO 服务不稳定 | 低 | 高 | Docker 健康检查 + 回滚到 local |
| Presigned URL 过期导致图片失效 | 中 | 中 | 前端定时刷新内容 (见 04 文档) |
| Docker 网络问题导致 URL 不可达 | 中 | 高 | `MINIO_SERVER_URL` 和 `public_endpoint` 配置 |
| Celery Worker MinIO 连接失败 | 低 | 高 | 重试机制 + fallback 到本地文件系统 |
| CORS 问题阻止图片加载 | 低 | 中 | MinIO 桶 CORS 配置 (见 04 文档) |
| 数据迁移过程中文件损坏 | 极低 | 高 | 迁移后校验 checksum + 保留本地副本 |
