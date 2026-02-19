# 03 - 流水线模块化：Celery Task 拆分与阶段函数抽取

## 1. 概述

本文档描述将单体 `_process_document_async` 拆分为三个独立的执行入口，并通过 `_execute_pipeline` 高阶函数消除三者之间的重复 boilerplate。

核心拆分：

| 执行入口 | 职责 | 适用场景 |
|----------|------|---------|
| `_convert_document_async` | 仅执行文件转换 | Admin 调试，批量转换 |
| `_index_document_async` | 仅执行索引（split + pgvector + ES） | Admin 调试，CONVERTED 文档补齐索引 |
| `_process_document_async` | 完整流水线（转换+索引），支持智能跳过 | 用户端 Notebook 关联，向后兼容 |

产品约束：用户端仅使用完整流水线入口，分段入口仅用于 Admin/调试。

## 2. 公共执行框架：_execute_pipeline

### 2.1 设计目标

三个执行入口共享大量 boilerplate（DB session 管理、幂等检查、claim_processing、stage 推进、error handling）。根据 DRY 原则，抽取公共框架函数。

选择高阶函数（而非 class）是基于 KISS 原则：不需要继承体系、不需要状态复用、三个入口结构平行。

> 详细设计见 [07-pipeline-executor.md](./07-pipeline-executor.md)

### 2.2 结构概要

```python
async def _execute_pipeline(
    document_id: str,
    mode: str,
    from_statuses: list[DocumentStatus],
    initial_stage: ProcessingStage,
    pipeline_fn: Callable[[PipelineContext], Awaitable[None]],
    skip_if_status: set[DocumentStatus] | None = None,
) -> None:
    """
    统一流水线执行框架。

    负责：
    1. DB session 获取与释放
    2. 幂等检查（已完成/正在处理 -> skip）
    3. claim_processing 原子认领
    4. 调用 pipeline_fn 执行业务逻辑
    5. 异常时 rollback + 标记 FAILED + compensation cleanup
    """
```

`PipelineContext` 提供业务函数所需的全部依赖和工具方法：

```python
@dataclass
class PipelineContext:
    document_id: str
    document: Document
    doc_repo: DocumentRepositoryImpl
    session: AsyncSession
    mode: str
    original_status: DocumentStatus   # claim 之前的原始状态，用于智能跳过判断
    indexed_anything: bool = False    # 是否已写入索引，用于失败时补偿清理

    async def set_stage(self, stage: ProcessingStage, meta: dict | None = None):
        """推进处理阶段。"""

    async def set_terminal_status(self, status: DocumentStatus, **kwargs):
        """设置终态并 commit。"""
```

> 注意：`original_status` 在 `_execute_pipeline` 中于 `claim_processing()` 之前记录，因为 claim 后文档状态已变为 PROCESSING。详见 [07-pipeline-executor.md](./07-pipeline-executor.md)。

## 3. 三个执行入口

### 3.1 _convert_document_async（仅转换）

**输入**：`document_id: str, force: bool = False`

**前置条件**：文档状态为 UPLOADED / PENDING / FAILED（force=True 时也允许 COMPLETED / CONVERTED）

**执行流程**：

1. 如果 force=True 且文档已有索引，先同步执行 `_delete_document_nodes_async` 清理旧索引
2. 通过 `_execute_pipeline` 进入统一框架
3. 解析文件路径（`_resolve_source_path`）
4. 调用 `_PROCESSOR.process_and_save()` 执行 MinerU/MarkItDown 转换
5. 保存 Markdown 和 assets 到磁盘
6. 更新终态为 `CONVERTED`，记录 `content_path` / `content_size` / `page_count`

**终态**：`DocumentStatus.CONVERTED`，`processing_stage = None`

```python
async def _convert_document_async(document_id: str, force: bool = False) -> None:
    async def _do_convert(ctx: PipelineContext) -> None:
        if force:
            try:
                await _delete_document_nodes_async(ctx.document_id)
            except Exception as exc:
                logger.warning("Pre-conversion cleanup failed for %s: %s", document_id, exc)

        source_path = _resolve_source_path(ctx.document)
        await ctx.set_stage(ProcessingStage.CONVERTING)
        result, content_path, content_size = await _PROCESSOR.process_and_save(
            document_id=ctx.document_id, file_path=source_path,
        )
        await ctx.set_stage(ProcessingStage.FINALIZING)
        await ctx.set_terminal_status(
            DocumentStatus.CONVERTED,
            page_count=result.page_count,
            content_path=content_path,
            content_size=content_size,
            content_format="markdown",
        )

    from_statuses = [DocumentStatus.UPLOADED, DocumentStatus.PENDING, DocumentStatus.FAILED]
    if force:
        from_statuses.extend([DocumentStatus.COMPLETED, DocumentStatus.CONVERTED])
    await _execute_pipeline(
        document_id, mode="convert_only",
        from_statuses=from_statuses,
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_convert,
    )
```

### 3.2 _index_document_async（仅索引）

**输入**：`document_id: str, force: bool = False`

**前置条件**：文档状态为 CONVERTED（force=True 时也允许 COMPLETED / FAILED）

**执行流程**：

1. 如果 force=True 且文档已有索引，先同步清理旧索引
2. 通过 `_execute_pipeline` 进入统一框架
3. 解析 content_path，加载已转换的 Markdown
4. 调用 `_load_markdown_nodes` 执行 SentenceSplitter 分块
5. 调用 `_index_to_stores` 执行 pgvector + ES 索引
6. 更新终态为 `COMPLETED`，记录 `chunk_count`

**终态**：`DocumentStatus.COMPLETED`，`processing_stage = None`

**失败行为**：

索引失败时状态设为 `FAILED`（非 CONVERTED），但：
- 磁盘上的 Markdown 产物不清除
- `processing_meta` 中标记 `conversion_preserved=true`
- 后续重试时可通过 `content_path` 跳过转换阶段

```python
async def _index_document_async(document_id: str, force: bool = False) -> None:
    async def _do_index(ctx: PipelineContext) -> None:
        if force:
            try:
                await _delete_document_nodes_async(ctx.document_id)
            except Exception as exc:
                logger.warning("Pre-index cleanup failed for %s: %s", document_id, exc)

        content_path = ctx.document.content_path
        if not content_path:
            raise RuntimeError(f"Document {document_id} has no content_path, cannot index")

        await ctx.set_stage(ProcessingStage.SPLITTING)
        nodes = await _load_markdown_nodes(ctx.document, content_path)

        # 注意：不在此处设置 INDEXING_PG stage，由 _index_to_stores 内部统一管理
        await _index_to_stores(nodes, ctx)

        await ctx.set_stage(ProcessingStage.FINALIZING)
        await ctx.set_terminal_status(
            DocumentStatus.COMPLETED,
            chunk_count=len(nodes),
        )

    from_statuses = [DocumentStatus.CONVERTED]
    if force:
        from_statuses.extend([DocumentStatus.COMPLETED, DocumentStatus.FAILED])
    await _execute_pipeline(
        document_id, mode="index_only",
        from_statuses=from_statuses,
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_index,
    )
```

### 3.3 _process_document_async（完整流水线，向后兼容）

**输入**：`document_id: str`

**前置条件**：文档状态为 UPLOADED / PENDING / FAILED / CONVERTED

**智能跳过**：

- 通过 `ctx.original_status`（claim 之前记录的原始状态）判断是否跳过转换
- 如果 `original_status == CONVERTED`，跳过转换阶段，从 SPLITTING 开始
- 如果 `original_status` 为 UPLOADED / PENDING / FAILED，执行完整流程

> 注意：不能用 `ctx.document.status` 判断，因为 claim_processing() 之后 document 重新加载时状态已经是 PROCESSING。也不能仅依赖 `content_path` 判断，因为 FAILED 状态（`conversion_preserved=true`）也可能有 `content_path`，但 FAILED 文档应该走完整流水线重新处理。

**执行流程**：

1. 通过 `_execute_pipeline` 进入统一框架
2. 检测 `ctx.original_status` 决定是否跳过转换
3. 如需转换：执行 CONVERTING -> 保存 Markdown -> 中间 commit 记录 content_path
4. 执行 SPLITTING -> INDEXING_PG -> INDEXING_ES -> FINALIZING
5. 更新终态为 `COMPLETED`

```python
async def _process_document_async(document_id: str) -> None:
    async def _do_full_pipeline(ctx: PipelineContext) -> None:
        # 使用 original_status 判断（claim 之前的状态），而非 ctx.document.status
        skip_conversion = ctx.original_status == DocumentStatus.CONVERTED

        if not skip_conversion:
            source_path = _resolve_source_path(ctx.document)
            await ctx.set_stage(ProcessingStage.CONVERTING)
            result, content_path, content_size = await _PROCESSOR.process_and_save(
                document_id=ctx.document_id, file_path=source_path,
            )
            # 完整流水线中转换完成后不进入 CONVERTED 终态，保持 PROCESSING 状态。
            # 此处直接调用 doc_repo.update_status 而非 ctx.set_terminal_status，
            # 因为这是中间步骤：记录 content_path 以便后续索引阶段使用，
            # 同时确保失败时 conversion_preserved 可被正确判定。
            await ctx.doc_repo.update_status(
                ctx.document_id, DocumentStatus.PROCESSING,
                content_path=content_path, content_size=content_size,
                page_count=result.page_count, content_format="markdown",
            )
            await ctx.session.commit()
        else:
            content_path = ctx.document.content_path
            logger.info("Document %s already converted, skipping conversion", document_id)

        await ctx.set_stage(ProcessingStage.SPLITTING)
        nodes = await _load_markdown_nodes(ctx.document, content_path)

        # 注意：不在此处设置 INDEXING_PG stage，由 _index_to_stores 内部统一管理
        await _index_to_stores(nodes, ctx)

        await ctx.set_stage(ProcessingStage.FINALIZING)
        await ctx.set_terminal_status(
            DocumentStatus.COMPLETED,
            chunk_count=len(nodes),
        )

    await _execute_pipeline(
        document_id, mode="full_pipeline",
        from_statuses=[
            DocumentStatus.UPLOADED, DocumentStatus.PENDING,
            DocumentStatus.FAILED, DocumentStatus.CONVERTED,
        ],
        initial_stage=ProcessingStage.QUEUED,
        pipeline_fn=_do_full_pipeline,
        skip_if_status={DocumentStatus.COMPLETED},
    )
```

## 4. Celery Task 注册

### 4.1 新增 Task

```python
@celery_app.task(name="convert_document")
def convert_document_task(document_id: str, force: bool = False) -> None:
    """仅转换单个文档。Admin/调试用。"""
    asyncio.run(_convert_document_async(document_id, force=force))

@celery_app.task(name="index_document")
def index_document_task(document_id: str, force: bool = False) -> None:
    """仅索引单个文档。Admin/调试用、智能关联补齐用。"""
    asyncio.run(_index_document_async(document_id, force=force))
```

### 4.2 现有 Task 保持

```python
@celery_app.task(name="process_document")
def process_document_task(document_id: str) -> None:
    """完整流水线。用户端 Notebook 关联的默认入口。"""
    asyncio.run(_process_document_async(document_id))
```

### 4.3 批量 Task

```python
@celery_app.task(name="convert_pending")
def convert_pending_task(document_ids: list[str] | None = None) -> dict:
    """批量转换：为每个待转换文档分派独立的 convert_document_task。"""
    return asyncio.run(_convert_pending_async(document_ids))

@celery_app.task(name="index_pending")
def index_pending_task(document_ids: list[str] | None = None) -> dict:
    """批量索引：为每个 CONVERTED 文档分派独立的 index_document_task。"""
    return asyncio.run(_index_pending_async(document_ids))
```

批量操作的执行策略：在外层查找待处理文档列表，然后为每个文档分派独立的 Celery Task（而非在循环中直接 await）。这避免了 session 嵌套风险，每个文档独立重试、独立超时。

```python
async def _convert_pending_async(document_ids: list[str] | None = None) -> dict:
    """批量转换分发。"""
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            docs = await _find_documents_by_status(
                doc_repo, [DocumentStatus.UPLOADED, DocumentStatus.FAILED], document_ids
            )

        dispatched, skipped = [], []
        for doc in docs:
            convert_document_task.delay(doc.document_id)
            dispatched.append(doc.document_id)

        return {"queued": dispatched, "skipped": skipped}
    finally:
        await close_database()
```

`_index_pending_async` 结构对称，查找 `CONVERTED` 状态文档。

## 5. 辅助函数

### 5.1 _resolve_source_path

解析文档原始文件路径，支持绝对/相对路径。无变更，现有实现复用。

### 5.2 _resolve_content_path

解析转换后 Markdown 的磁盘路径。复用已有的路径拼接逻辑，不新增函数：

```python
def _resolve_content_path(content_path: str) -> Path:
    """将数据库中存储的相对 content_path 解析为绝对路径。

    content_path 格式示例: "documents/{id}/markdown/content.md"
    拼接规则: Path(get_documents_directory()) / content_path
    """
    return Path(get_documents_directory()) / content_path
```

> 与 `_resolve_source_path` 的区别：`_resolve_source_path` 解析原始上传文件路径（raw/），`_resolve_content_path` 解析转换后的 Markdown 路径（markdown/）。两者共享同一个 `get_documents_directory()` 基础目录。

### 5.3 _load_markdown_nodes

加载已转换的 Markdown，执行 SentenceSplitter 分块。

```python
async def _load_markdown_nodes(document: Document, content_path: str) -> list[TextNode]:
    """加载 Markdown 并分块为 TextNode 列表。"""
    full_path = _resolve_content_path(content_path)
    docs = MarkdownReader().load_data(full_path)
    nodes = split_documents(docs, chunk_size=512, chunk_overlap=50)
    # 注入元数据
    for node in nodes:
        node.metadata["document_id"] = document.document_id
        node.metadata["library_id"] = document.library_id or ""
    return nodes
```

### 5.4 _index_to_stores

执行 pgvector + ES 双索引写入。stage 推进统一在此函数内部管理，调用方不应重复设置 INDEXING_PG/INDEXING_ES stage。

```python
async def _index_to_stores(nodes: list[TextNode], ctx: PipelineContext) -> None:
    """将节点写入 pgvector 和 ES。

    内部统一管理 INDEXING_PG / INDEXING_ES stage 推进和 indexed_anything 标记。
    调用方（_do_index / _do_full_pipeline）不应重复设置这些 stage。
    """
    embed_model = build_embedding()

    await ctx.set_stage(ProcessingStage.INDEXING_PG)
    pg_index = await load_pgvector_index(embed_model)
    pg_index.insert_nodes(nodes)
    ctx.indexed_anything = True  # pgvector 已写入，失败时需要补偿清理

    await ctx.set_stage(ProcessingStage.INDEXING_ES)
    es_index = await load_es_index(embed_model)
    es_index.insert_nodes(nodes)
```

### 5.5 _find_documents_by_status

按状态查找文档列表，支持可选的 document_ids 过滤。用于批量操作。

```python
async def _find_documents_by_status(
    doc_repo: DocumentRepositoryImpl,
    statuses: list[DocumentStatus],
    document_ids: list[str] | None = None,
) -> list[Document]:
    """查找指定状态的文档，可选按 document_ids 过滤。

    本质是对 doc_repo.list_by_library() 的封装，增加 document_ids 过滤能力。
    """
    all_docs = []
    for status in statuses:
        docs = await doc_repo.list_by_library(limit=200, status=status)
        all_docs.extend(docs)

    if document_ids is not None:
        id_set = set(document_ids)
        all_docs = [d for d in all_docs if d.document_id in id_set]

    return all_docs
```

## 6. 错误处理策略

### 6.1 统一框架中的错误处理

`_execute_pipeline` 统一处理所有异常，业务函数只需要抛出异常即可：

**关键过程**：异常发生时先执行 `session.rollback()` 清除脏数据，然后执行补偿清理和状态更新（详见 [07-pipeline-executor.md](./07-pipeline-executor.md)）。

| 失败阶段 | 状态设为 | processing_stage | processing_meta |
|----------|---------|------------------|-----------------|
| CONVERTING | FAILED | 保留 "converting" | `{"failed_stage": "converting"}` |
| SPLITTING | FAILED | 保留 "splitting" | `{"failed_stage": "splitting", "conversion_preserved": true}` |
| INDEXING_PG | FAILED | 保留 "indexing_pg" | `{"failed_stage": "indexing_pg", "conversion_preserved": true}` |
| INDEXING_ES | FAILED | 保留 "indexing_es" | `{"failed_stage": "indexing_es", "conversion_preserved": true}` |
| FINALIZING | FAILED | 保留 "finalizing" | `{"failed_stage": "finalizing", "conversion_preserved": true}` |

关键原则：
- 失败时保留 processing_stage 的最后值，用于诊断和重试策略
- 索引阶段失败不清除磁盘转换产物（content_path 保留）
- `conversion_preserved=true` 标记转换产物是否完整，Admin 可据此决定仅重试索引

### 6.2 补偿清理

如果在 INDEXING_PG/INDEXING_ES 阶段失败，已写入的部分节点通过 `_delete_document_nodes_async` 尽力清理：

```python
# _execute_pipeline 中的 except 分支
except Exception as exc:
    if ctx.indexed_anything:
        try:
            await _delete_document_nodes_async(document_id)
        except Exception:
            logger.warning("Compensation cleanup failed for %s", document_id)
    await ctx.doc_repo.update_status(
        document_id, DocumentStatus.FAILED,
        error_message=str(exc)[:500],
        processing_meta={"failed_stage": current_stage, ...},
    )
```

## 7. 幂等性保证

| 机制 | 说明 |
|------|------|
| `skip_if_status` | 已 COMPLETED 文档直接跳过，不重复处理 |
| `claim_processing` | 基于 `UPDATE ... WHERE status IN (...)` 的原子操作，竞争 worker 只有一个能成功 |
| 同状态跳过 | `status == PROCESSING` 时跳过，防止重复执行 |
| force 参数 | 需要显式传入 force=True 才能跳过幂等检查 |

## 8. 文件结构变更

```
newbee_notebook/infrastructure/tasks/
    document_tasks.py       # 现有文件，重构

newbee_notebook/domain/value_objects/
    processing_stage.py     # 新增：ProcessingStage 枚举

newbee_notebook/infrastructure/tasks/
    pipeline_context.py     # 新增：PipelineContext 数据类
```
