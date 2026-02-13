# 03 - 流水线模块化：Celery Task 拆分与阶段函数抽取

## 1. 概述

将 `_process_document_async()` 单体函数拆分为三个独立的 async 核心函数，注册为独立的 Celery Task，实现文档转换、索引、完整流水线三种执行模式。

## 2. 当前结构

```python
# 当前: 一个函数包含所有阶段
async def _process_document_async(document_id: str):
    claim_processing()
    # 阶段 1: converting
    conversion_result = await _PROCESSOR.process_and_save(...)
    # 阶段 2: splitting
    nodes = _load_markdown_nodes(...)
    # 阶段 3: embedding (空操作)
    # 阶段 4: indexing_pg
    await _index_pg_nodes(nodes)
    # 阶段 5: indexing_es
    await _index_es_nodes(nodes)
    # 阶段 6: finalizing
    update_status(COMPLETED)
```

## 3. 拆分后结构

### 3.1 核心 async 函数（3个）

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 函数 1: 仅转换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _convert_document_async(document_id: str) -> None:
    """
    仅执行文件→Markdown 转换，完成后状态设为 CONVERTED。
    
    阶段: converting → CONVERTED
    允许起始状态: UPLOADED, FAILED, PENDING
    终态: CONVERTED (成功) / FAILED (失败)
    """

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 函数 2: 仅索引
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _index_document_async(document_id: str) -> None:
    """
    对已转换文档执行全部索引操作，完成后状态设为 COMPLETED。
    
    前置条件: status == CONVERTED (content_path 存在)
    阶段: splitting → embedding → indexing_pg → indexing_es → finalizing → COMPLETED
    允许起始状态: CONVERTED
    终态: COMPLETED (成功) / FAILED (失败)
    """

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 函数 3: 完整流水线（重构，复用函数 1 和 2）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _process_document_async(document_id: str) -> None:
    """
    完整处理流水线，保持向后兼容。
    
    阶段: converting → splitting → embedding → indexing_pg → indexing_es → finalizing → COMPLETED
    允许起始状态: UPLOADED, PENDING, FAILED
    终态: COMPLETED (成功) / FAILED (失败)
    
    注意: 不经过 CONVERTED 中间态，直接从 converting 走到 COMPLETED。
    """
```

### 3.2 Celery Task 注册（5个 → 从3个扩展到5个）

```python
# ━━━ 现有 Task（保持不变）━━━

@app.task(name="...process_document_task")
def process_document_task(document_id: str):
    """完整流水线 — 向后兼容。"""
    asyncio.run(_process_document_async(document_id))

@app.task(name="...process_pending_documents_task")
def process_pending_documents_task():
    """批量完整流水线 — 向后兼容。"""
    asyncio.run(_process_all_pending_async())

@app.task(name="...delete_document_nodes_task")
def delete_document_nodes_task(document_id: str):
    """删除向量/ES节点 — 保持不变。"""
    asyncio.run(_delete_document_nodes_async(document_id))

# ━━━ 新增 Task ━━━

@app.task(name="...convert_document_task")
def convert_document_task(document_id: str):
    """仅转换 — 新增。"""
    asyncio.run(_convert_document_async(document_id))

@app.task(name="...index_document_task")
def index_document_task(document_id: str):
    """仅索引 — 新增。"""
    asyncio.run(_index_document_async(document_id))
```

## 4. 详细设计

### 4.1 `_convert_document_async()` 实现

```python
async def _convert_document_async(document_id: str) -> None:
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            
            # ── 幂等性检查 ──
            document = await doc_repo.get(document_id)
            if not document:
                logger.error("Document %s not found", document_id)
                return
            
            # 已转换或已完成 → 跳过
            if document.status in (DocumentStatus.CONVERTED, DocumentStatus.COMPLETED):
                logger.info("Document %s already converted/completed, skip", document_id)
                return
            
            # 正在处理 → 跳过（防止重复执行）
            if document.status == DocumentStatus.PROCESSING:
                logger.info("Document %s is already processing, skip", document_id)
                return
            
            # ── 原子认领 ──
            claimed = await doc_repo.claim_processing(
                document_id,
                from_statuses=[DocumentStatus.UPLOADED, DocumentStatus.PENDING, DocumentStatus.FAILED],
                processing_stage=ProcessingStage.CONVERTING.value,
                processing_meta={"mode": "convert_only"},
            )
            if not claimed:
                logger.info("Document %s claimed by another worker, skip", document_id)
                return
            await session.commit()
            
            # ── 转换阶段 ──
            try:
                source_path = _resolve_source_path(document)
                
                conversion_result, rel_content_path, content_size = \
                    await _PROCESSOR.process_and_save(document.document_id, str(source_path))
                
                # ── 设置 CONVERTED 终态 ──
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.CONVERTED,
                    page_count=conversion_result.page_count or 0,
                    content_path=rel_content_path,
                    content_size=content_size,
                    content_format="markdown",
                    error_message=None,
                    processing_stage=ProcessingStage.CONVERTED.value,
                    processing_meta={"mode": "convert_only"},
                )
                await session.commit()
                
                logger.info(
                    "Document %s converted successfully: pages=%d, content=%d bytes",
                    document_id,
                    conversion_result.page_count or 0,
                    content_size,
                )
                
            except Exception as exc:
                logger.exception("Conversion failed for %s", document_id)
                await session.rollback()
                # 转换阶段无需向量清理（indexed_anything 始终为 False）
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                    processing_stage=ProcessingStage.CONVERTING.value,
                    processing_meta={"failed_stage": "converting", "mode": "convert_only"},
                )
                await session.commit()
    finally:
        await close_database()
```

### 4.2 `_index_document_async()` 实现

```python
async def _index_document_async(document_id: str) -> None:
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            
            # ── 幂等性检查 ──
            document = await doc_repo.get(document_id)
            if not document:
                logger.error("Document %s not found", document_id)
                return
            
            if document.status == DocumentStatus.COMPLETED:
                logger.info("Document %s already completed, skip indexing", document_id)
                return
            
            if document.status == DocumentStatus.PROCESSING:
                logger.info("Document %s is already processing, skip", document_id)
                return
            
            # ── 前置条件验证 ──
            if document.status != DocumentStatus.CONVERTED:
                logger.error(
                    "Document %s status is %s, expected CONVERTED for indexing",
                    document_id, document.status.value,
                )
                return
            
            # 验证转换产物存在
            if not document.content_path:
                logger.error("Document %s has no content_path, cannot index", document_id)
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message="content_path is empty, conversion may have failed",
                    processing_stage=ProcessingStage.SPLITTING.value,
                )
                await session.commit()
                return
            
            content_abs_path = Path(get_documents_directory()) / document.content_path
            if not content_abs_path.exists():
                logger.error("Content file not found: %s", content_abs_path)
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message=f"Content file not found: {content_abs_path}",
                    processing_stage=ProcessingStage.SPLITTING.value,
                )
                await session.commit()
                return
            
            # ── 原子认领（从 CONVERTED 认领）──
            claimed = await doc_repo.claim_processing(
                document_id,
                from_statuses=[DocumentStatus.CONVERTED],
                processing_stage=ProcessingStage.SPLITTING.value,
                processing_meta={"mode": "index_only"},
            )
            if not claimed:
                logger.info("Document %s claimed by another worker, skip", document_id)
                return
            await session.commit()
            
            current_stage = ProcessingStage.SPLITTING.value
            indexed_anything = False
            
            async def _set_stage(stage: ProcessingStage, meta: dict | None = None) -> None:
                nonlocal current_stage
                current_stage = stage.value
                await doc_repo.update_status(
                    document_id=document_id,
                    status=DocumentStatus.PROCESSING,
                    processing_stage=stage.value,
                    processing_meta=meta,
                )
                await session.commit()
            
            # ── 索引阶段 ──
            try:
                nodes = _load_markdown_nodes(content_abs_path, document)
                chunk_count = len(nodes)
                
                await _set_stage(ProcessingStage.EMBEDDING, {"chunk_count": chunk_count})
                await _set_stage(ProcessingStage.INDEXING_PG, {"chunk_count": chunk_count})
                await _index_pg_nodes(nodes)
                indexed_anything = True
                
                await _set_stage(ProcessingStage.INDEXING_ES, {"chunk_count": chunk_count})
                await _index_es_nodes(nodes)
                
                await _set_stage(ProcessingStage.FINALIZING, {"chunk_count": chunk_count})
                
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.COMPLETED,
                    chunk_count=chunk_count,
                    error_message=None,
                    processing_stage=ProcessingStage.COMPLETED.value,
                    processing_meta={"chunk_count": chunk_count, "mode": "index_only"},
                )
                await session.commit()
                
                logger.info(
                    "Document %s indexed successfully: chunks=%d",
                    document_id, chunk_count,
                )
                
            except Exception as exc:
                logger.exception("Indexing failed for %s", document_id)
                await session.rollback()
                
                if indexed_anything:
                    try:
                        await _delete_document_nodes_async(document_id)
                    except Exception as cleanup_exc:
                        logger.warning(
                            "Compensation cleanup failed for %s: %s",
                            document_id, cleanup_exc,
                        )
                
                # 索引失败后回退到 CONVERTED（而非 FAILED），保留转换成果
                # 这样重试时可以直接从索引阶段开始，不需要重新转换
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                    processing_stage=current_stage,
                    processing_meta={
                        "failed_stage": current_stage,
                        "mode": "index_only",
                        "conversion_preserved": True,
                    },
                )
                await session.commit()
    finally:
        await close_database()
```

### 4.3 `_process_document_async()` 重构（复用模式）

```python
async def _process_document_async(document_id: str) -> None:
    """
    完整流水线 — 保持向后兼容。
    
    重构策略: 不直接复用 _convert + _index（因为它们各自独立管理 session），
    而是保持原有的单一 session 结构，但使用抽取出的阶段函数。
    """
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            
            document = await doc_repo.get(document_id)
            if not document:
                logger.error("Document %s not found", document_id)
                return
            
            if document.status == DocumentStatus.COMPLETED:
                logger.info("Document %s already completed, skip", document_id)
                return
            if document.status == DocumentStatus.PROCESSING:
                logger.info("Document %s already processing, skip", document_id)
                return
            
            # ── 智能入口：根据当前状态决定起始阶段 ──
            if document.status == DocumentStatus.CONVERTED:
                # 已转换 → 直接从索引阶段开始
                start_from_index = True
            elif document.status in (DocumentStatus.UPLOADED, DocumentStatus.PENDING, DocumentStatus.FAILED):
                start_from_index = False
            else:
                logger.warning("Unexpected status %s for %s", document.status, document_id)
                return
            
            # ── 原子认领 ──
            from_statuses = (
                [DocumentStatus.CONVERTED]
                if start_from_index
                else [DocumentStatus.UPLOADED, DocumentStatus.PENDING, DocumentStatus.FAILED]
            )
            initial_stage = (
                ProcessingStage.SPLITTING.value
                if start_from_index
                else ProcessingStage.CONVERTING.value
            )
            
            claimed = await doc_repo.claim_processing(
                document_id,
                from_statuses=from_statuses,
                processing_stage=initial_stage,
                processing_meta={"mode": "full_pipeline"},
            )
            if not claimed:
                return
            await session.commit()
            
            current_stage = initial_stage
            indexed_anything = False
            
            async def _set_stage(stage: ProcessingStage, meta: dict | None = None):
                nonlocal current_stage
                current_stage = stage.value
                await doc_repo.update_status(
                    document_id=document_id,
                    status=DocumentStatus.PROCESSING,
                    processing_stage=stage.value,
                    processing_meta=meta,
                )
                await session.commit()
            
            try:
                # ── 转换阶段（可选跳过）──
                if not start_from_index:
                    source_path = _resolve_source_path(document)
                    conversion_result, rel_content_path, content_size = \
                        await _PROCESSOR.process_and_save(
                            document.document_id, str(source_path)
                        )
                    # 更新转换结果到 document 对象（不设为 CONVERTED，继续往下走）
                    await doc_repo.update_status(
                        document_id,
                        status=DocumentStatus.PROCESSING,
                        page_count=conversion_result.page_count or 0,
                        content_path=rel_content_path,
                        content_size=content_size,
                        content_format="markdown",
                        processing_stage=ProcessingStage.SPLITTING.value,
                    )
                    await session.commit()
                    content_abs_path = Path(get_documents_directory()) / rel_content_path
                else:
                    content_abs_path = Path(get_documents_directory()) / document.content_path
                
                # ── 索引阶段（始终执行）──
                await _set_stage(ProcessingStage.SPLITTING)
                nodes = _load_markdown_nodes(content_abs_path, document)
                chunk_count = len(nodes)
                
                await _set_stage(ProcessingStage.EMBEDDING, {"chunk_count": chunk_count})
                await _set_stage(ProcessingStage.INDEXING_PG, {"chunk_count": chunk_count})
                await _index_pg_nodes(nodes)
                indexed_anything = True
                
                await _set_stage(ProcessingStage.INDEXING_ES, {"chunk_count": chunk_count})
                await _index_es_nodes(nodes)
                
                await _set_stage(ProcessingStage.FINALIZING, {"chunk_count": chunk_count})
                
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.COMPLETED,
                    chunk_count=chunk_count,
                    page_count=document.page_count if start_from_index else (conversion_result.page_count or 0),
                    error_message=None,
                    processing_stage=ProcessingStage.COMPLETED.value,
                    processing_meta={"chunk_count": chunk_count, "mode": "full_pipeline"},
                )
                await session.commit()
                
            except Exception as exc:
                logger.exception("Processing failed for %s", document_id)
                await session.rollback()
                if indexed_anything:
                    try:
                        await _delete_document_nodes_async(document_id)
                    except Exception as cleanup_exc:
                        logger.warning("Cleanup failed for %s: %s", document_id, cleanup_exc)
                await doc_repo.update_status(
                    document_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                    processing_stage=current_stage,
                    processing_meta={"failed_stage": current_stage, "mode": "full_pipeline"},
                )
                await session.commit()
    finally:
        await close_database()
```

## 5. 辅助函数抽取

### 5.1 路径解析（提取为公共函数）

```python
def _resolve_source_path(document: Document) -> Path:
    """解析文档源文件的绝对路径。"""
    source_path = Path(document.file_path)
    if not source_path.is_absolute():
        source_path = Path(get_documents_directory()) / source_path
    if not source_path.exists():
        raise FileNotFoundError(f"Original file not found: {source_path}")
    return source_path
```

### 5.2 批量转换辅助

```python
async def _convert_pending_async(document_ids: list[str] | None = None) -> dict:
    """
    批量转换 uploaded/failed 文档。
    
    Args:
        document_ids: 指定文档ID列表。None 表示处理所有待转换文档。
    
    Returns:
        {"converted": [...], "failed": [...], "skipped": [...]}
    """
    db = await get_database()
    results = {"converted": [], "failed": [], "skipped": []}
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)
            
            if document_ids:
                # 使用指定的文档ID列表
                docs = []
                for doc_id in document_ids:
                    doc = await doc_repo.get(doc_id)
                    if doc:
                        docs.append(doc)
            else:
                # 查找所有待转换文档
                docs = []
                for status in (DocumentStatus.UPLOADED, DocumentStatus.FAILED):
                    docs.extend(
                        await doc_repo.list_by_library(limit=1000, offset=0, status=status)
                    )
        
        # 去重
        seen = set()
        unique_docs = []
        for doc in docs:
            if doc.document_id not in seen:
                seen.add(doc.document_id)
                unique_docs.append(doc)
        
        for doc in unique_docs:
            if doc.status not in (DocumentStatus.UPLOADED, DocumentStatus.FAILED):
                results["skipped"].append({
                    "document_id": doc.document_id,
                    "reason": f"status is {doc.status.value}",
                })
                continue
            try:
                await _convert_document_async(doc.document_id)
                results["converted"].append(doc.document_id)
            except Exception as exc:
                results["failed"].append({
                    "document_id": doc.document_id,
                    "error": str(exc),
                })
        
        return results
    finally:
        await close_database()
```

## 6. 错误处理策略

### 6.1 转换失败

| 场景 | 行为 |
|------|------|
| MinerU 网络错误 | 熔断器计数 +1，fallback 到 MarkItDown |
| MinerU 超时 | 熔断器计数 +1，fallback 到 MarkItDown |
| 所有转换器失败 | status → FAILED, processing_stage = "converting" |
| 文件不存在 | status → FAILED, processing_stage = "converting" |

**转换失败不需要向量清理**（`indexed_anything = False`）。

### 6.2 索引失败

| 场景 | 行为 |
|------|------|
| pgvector 连接失败 | status → FAILED, processing_stage = "indexing_pg" |
| ES 连接失败 | status → FAILED, 补偿清理 pgvector 节点 |
| Markdown 文件损坏 | status → FAILED, processing_stage = "splitting" |

**索引失败保留转换产物**：磁盘上的 `markdown/content.md` 和 `assets/` 不受影响，`processing_meta.conversion_preserved = true`。

### 6.3 重试策略

| 失败阶段 | 重试操作 | 说明 |
|----------|---------|------|
| converting | `convert_document_task` 或 `process_document_task` | 重新调用 MinerU |
| splitting/indexing | `index_document_task` | 如果 content_path 存在，可直接索引 |
| 任意 | `process_document_task` | 智能检测：如果已有 content_path，跳过转换 |

## 7. 幂等性保证

| Task | 幂等行为 |
|------|---------|
| `convert_document_task` | CONVERTED/COMPLETED → skip, PROCESSING → skip |
| `index_document_task` | COMPLETED → skip, PROCESSING → skip, 非CONVERTED → reject |
| `process_document_task` | COMPLETED → skip, PROCESSING → skip, CONVERTED → 从索引开始 |

所有 Task 通过 `claim_processing()` 原子 CAS 操作保证并发安全。

## 8. 文件结构变更

```
newbee_notebook/
├── domain/
│   └── value_objects/
│       ├── document_status.py        # 新增 CONVERTED
│       └── processing_stage.py       # 新增 ProcessingStage 枚举
├── infrastructure/
│   └── tasks/
│       └── document_tasks.py         # 拆分为 3 个核心函数 + 5 个 Celery Task
└── api/
    └── routers/
        └── admin.py                  # 新增端点（见 04-api-endpoints.md）
```
