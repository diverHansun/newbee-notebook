# 07 - 流水线执行框架：_execute_pipeline 设计

## 1. 设计目标

本文档描述 `_execute_pipeline` 高阶函数的设计，它是三个流水线执行入口（`_convert_document_async`、`_index_document_async`、`_process_document_async`）的公共框架。

### 1.1 要解决的问题

三个执行入口共享以下 boilerplate，每个约 40-50 行：

1. 获取 DB session 并在 finally 中释放
2. 从数据库加载 Document 实体
3. 幂等检查：COMPLETED/PROCESSING -> skip
4. `claim_processing` 原子认领
5. 构建 `_set_stage` 闭包用于阶段推进
6. try/except 统一异常处理（rollback + compensation + FAILED）
7. finally 中关闭数据库连接

三份重复违反 DRY 原则，且错误处理逻辑的微调需要同步修改三处。

### 1.2 设计选择

| 方案 | 说明 | 采用 |
|------|------|------|
| 高阶函数 + dataclass | `_execute_pipeline(pipeline_fn)` + `PipelineContext` | 采用 |
| 基类 + 模板方法模式 | `PipelineExecutor.run()` with abstract `_execute()` | 不采用 |
| 装饰器 | `@pipeline_task` 装饰 async 函数 | 不采用 |

选择理由：
- 高阶函数最简单（KISS），不引入继承体系
- PipelineContext 是纯数据类 + 工具方法，没有生命周期管理需求
- 三个入口结构平行，不需要多态调度
- 装饰器会隐藏执行流程，降低可读性

## 2. PipelineContext 数据类

### 2.1 定义

```python
# infrastructure/tasks/pipeline_context.py

from dataclasses import dataclass, field
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.document import Document
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.processing_stage import ProcessingStage
from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
    DocumentRepositoryImpl,
)


@dataclass
class PipelineContext:
    """流水线执行上下文。

    传递给 pipeline_fn，提供业务逻辑所需的全部依赖和工具方法。
    PipelineContext 本身不管理 session 生命周期，由 _execute_pipeline 负责。
    """

    document_id: str
    document: Document
    doc_repo: DocumentRepositoryImpl
    session: AsyncSession
    mode: str
    original_status: DocumentStatus  # claim 之前的原始状态，用于智能跳过判断
    indexed_anything: bool = False   # 是否已写入索引，失败时决定是否补偿清理
    _current_stage: Optional[str] = field(default=None, repr=False)

    async def set_stage(
        self, stage: ProcessingStage, meta: dict[str, Any] | None = None
    ) -> None:
        """推进处理阶段。

        更新数据库中的 processing_stage 并 commit，
        使外部监控可以实时观察进度。
        """
        self._current_stage = stage.value
        await self.doc_repo.update_status(
            document_id=self.document_id,
            status=DocumentStatus.PROCESSING,
            processing_stage=stage.value,
            processing_meta=meta,
        )
        await self.session.commit()

    async def set_terminal_status(
        self,
        status: DocumentStatus,
        chunk_count: int | None = None,
        page_count: int | None = None,
        content_path: str | None = None,
        content_size: int | None = None,
        content_format: str | None = None,
    ) -> None:
        """设置终态（CONVERTED / COMPLETED）并 commit。

        终态时 processing_stage 清空为 None（结果状态由 DocumentStatus 表达）。

        注意：此处传 processing_stage=None 意图是"显式写入 NULL"。
        repo 层的 update_status 必须使用 sentinel 值（_UNSET）区分
        "未传参"和"显式传 None"，否则 None 会被 `if xxx is not None`
        短路跳过，导致终态残留旧 stage 值。详见 Phase 1 任务 1.4。
        """
        await self.doc_repo.update_status(
            document_id=self.document_id,
            status=status,
            processing_stage=None,   # 显式清空（依赖 repo 层 sentinel 机制）
            processing_meta=None,    # 显式清空
            chunk_count=chunk_count,
            page_count=page_count,
            content_path=content_path,
            content_size=content_size,
            content_format=content_format,
            error_message=None,      # 显式清空
        )
        await self.session.commit()

    @property
    def current_stage(self) -> str | None:
        """当前阶段值，用于失败时记录 failed_stage。"""
        return self._current_stage
```

### 2.2 职责边界

PipelineContext 只负责：
- 持有依赖引用（doc_repo, session, document）
- 记录 claim 前的原始状态（original_status），供智能跳过逻辑使用
- 提供阶段推进方法（set_stage）
- 提供终态设置方法（set_terminal_status）
- 记录当前阶段用于失败诊断
- 追踪是否已写入索引（indexed_anything），供补偿清理逻辑使用

PipelineContext 不负责：
- session 生命周期管理（由 _execute_pipeline 负责）
- 错误处理和 FAILED 状态设置（由 _execute_pipeline 负责）
- 业务逻辑（由 pipeline_fn 负责）

## 3. _execute_pipeline 函数

### 3.1 签名

```python
async def _execute_pipeline(
    document_id: str,
    mode: str,
    from_statuses: list[DocumentStatus],
    initial_stage: ProcessingStage,
    pipeline_fn: Callable[[PipelineContext], Awaitable[None]],
    skip_if_status: set[DocumentStatus] | None = None,
) -> None:
```

参数说明：

| 参数 | 类型 | 说明 |
|------|------|------|
| document_id | str | 目标文档 ID |
| mode | str | 执行模式标识，用于日志（"convert_only" / "index_only" / "full_pipeline"） |
| from_statuses | list | claim_processing 允许的源状态列表 |
| initial_stage | ProcessingStage | claim 成功后设置的初始 stage |
| pipeline_fn | Callable | 核心业务逻辑回调，接收 PipelineContext |
| skip_if_status | set, 可选 | 遇到这些状态直接跳过（幂等保护） |

### 3.2 执行流程

```
    _execute_pipeline(document_id, mode, from_statuses, initial_stage, pipeline_fn)
                |
                v
    +---  get_database()  ---+
    |                        |
    |  async with db.session() as session:
    |       |
    |       v
    |  doc_repo.get(document_id)
    |       |
    |       v
    |  <-- 幂等检查 -->
    |  if doc.status in skip_if_status: return   (已完成跳过)
    |  if doc.status == PROCESSING: return        (防重复执行)
    |       |
    |       v
    |  claim_processing(from_statuses, initial_stage)
    |       |-- 失败: return (另一个 worker 已认领)
    |       |-- 成功: 继续
    |       v
    |  构建 PipelineContext
    |       |
    |       v
    |  +-- try --------------------------------+
    |  |                                       |
    |  |  await pipeline_fn(ctx)               |
    |  |                                       |
    |  +-- except Exception as exc ------------+
    |  |                                       |
    |  |  session.rollback()      // 清除脏数据  |
    |  |                                       |
    |  |  if ctx.indexed_anything:             |
    |  |      _delete_document_nodes_async()   |
    |  |                                       |
    |  |  doc_repo.update_status(              |
    |  |      FAILED,                          |
    |  |      error_message=str(exc),          |
    |  |      processing_stage=保留当前值,       |
    |  |      processing_meta={                |
    |  |          "failed_stage": ...,          |
    |  |          "conversion_preserved": ...,  |
    |  |          "mode": mode,                |
    |  |      }                                |
    |  |  )                                    |
    |  |  session.commit()                     |
    |  |                                       |
    |  +---------------------------------------+
    |                                          |
    +---  finally: close_database()  ----------+
```

### 3.3 实现

```python
async def _execute_pipeline(
    document_id: str,
    mode: str,
    from_statuses: list[DocumentStatus],
    initial_stage: ProcessingStage,
    pipeline_fn: Callable[[PipelineContext], Awaitable[None]],
    skip_if_status: set[DocumentStatus] | None = None,
) -> None:
    """统一流水线执行框架。"""
    db = await get_database()
    try:
        async with db.session() as session:
            doc_repo = DocumentRepositoryImpl(session)

            document = await doc_repo.get(document_id)
            if not document:
                logger.error("[%s] Document %s not found", mode, document_id)
                return

            # 幂等检查
            if skip_if_status and document.status in skip_if_status:
                logger.info("[%s] Document %s status=%s, skip",
                            mode, document_id, document.status.value)
                return
            if document.status == DocumentStatus.PROCESSING:
                logger.info("[%s] Document %s already processing, skip",
                            mode, document_id)
                return

            # 原子认领
            # 注意：在 claim 之前记录原始状态，因为 claim 会将状态改为 PROCESSING。
            # pipeline_fn 需要 original_status 来判断智能跳过（如 CONVERTED->跳过转换）。
            original_status = document.status

            claimed = await doc_repo.claim_processing(
                document_id,
                from_statuses=from_statuses,
                processing_stage=initial_stage.value,
                processing_meta={"mode": mode},
            )
            if not claimed:
                logger.warning("[%s] Failed to claim %s", mode, document_id)
                return

            await session.commit()

            # 重新加载 document 获取最新状态
            document = await doc_repo.get(document_id)

            ctx = PipelineContext(
                document_id=document_id,
                document=document,
                doc_repo=doc_repo,
                session=session,
                mode=mode,
                original_status=original_status,
            )

            try:
                await pipeline_fn(ctx)
            except Exception as exc:
                logger.error("[%s] Pipeline failed for %s at stage=%s: %s",
                             mode, document_id, ctx.current_stage, exc, exc_info=True)

                # 先 rollback 清除 session 中的脏数据，
                # 防止后续 update_status + commit 把 pipeline_fn 中未提交的写操作一并提交。
                await session.rollback()

                # 补偿清理
                if ctx.indexed_anything:
                    try:
                        await _delete_document_nodes_async(document_id)
                    except Exception:
                        logger.warning("Compensation cleanup failed for %s", document_id)

                # 判断转换产物是否完整
                has_conversion = bool(document.content_path) or (
                    ctx.current_stage and ctx.current_stage != ProcessingStage.CONVERTING.value
                )

                await doc_repo.update_status(
                    document_id,
                    DocumentStatus.FAILED,
                    error_message=str(exc)[:500],
                    processing_meta={
                        "failed_stage": ctx.current_stage,
                        "conversion_preserved": has_conversion,
                        "mode": mode,
                    },
                )
                await session.commit()
    finally:
        await close_database()
```

## 4. 设计原则对照

### 4.1 DRY

修改前：三个函数各含 ~50 行 boilerplate，总计 ~150 行重复代码。
修改后：`_execute_pipeline` ~60 行 + `PipelineContext` ~50 行，三个业务函数各 ~20 行。
净效果：消除 ~90 行重复，且 error handling 逻辑集中维护。

### 4.2 SRP

| 组件 | 单一职责 |
|------|---------|
| `_execute_pipeline` | 流水线执行的基础设施（session / claim / error） |
| `PipelineContext` | 执行上下文的数据持有和工具方法 |
| `_do_convert` | 转换的业务逻辑 |
| `_do_index` | 索引的业务逻辑 |
| `_do_full_pipeline` | 完整流水线的业务逻辑（含智能跳过） |

### 4.3 OCP

新增流水线模式只需编写新的 `pipeline_fn`，不修改 `_execute_pipeline`。例如未来新增"仅 ES 索引"模式：

```python
async def _es_only_document_async(document_id: str) -> None:
    async def _do_es_only(ctx: PipelineContext) -> None:
        nodes = await _load_markdown_nodes(ctx.document, ctx.document.content_path)
        await ctx.set_stage(ProcessingStage.INDEXING_ES)
        es_index = await load_es_index(build_embedding())
        es_index.insert_nodes(nodes)
        await ctx.set_terminal_status(DocumentStatus.COMPLETED, chunk_count=len(nodes))

    await _execute_pipeline(document_id, mode="es_only", ...)
```

### 4.4 KISS

- 使用普通函数和 dataclass，无 class 继承
- PipelineContext 只有两个核心方法（set_stage, set_terminal_status），接口极简
- pipeline_fn 是普通 async 函数，不需要实现抽象接口

### 4.5 YAGNI

未引入的功能：
- 无 Pipeline 编排 / DAG 引擎
- 无 Celery chain / chord 集成
- 无 stage 持久化恢复（从断点继续）——当前重试是从头执行

这些可在未来有明确需求时再引入。

## 5. 错误处理细节

### 5.1 conversion_preserved 的判定逻辑

失败时需要判断转换产物是否完整，以便后续决定重试策略：

```python
# 场景 1: 转换阶段失败 -> conversion_preserved = False
# 场景 2: 分块/索引阶段失败 -> conversion_preserved = True
# 场景 3: 文档原本就有 content_path -> conversion_preserved = True

has_conversion = bool(document.content_path) or (
    ctx.current_stage and ctx.current_stage != ProcessingStage.CONVERTING.value
)
```

### 5.2 失败后的重试路径

| processing_meta.failed_stage | conversion_preserved | 推荐重试方式 |
|------------------------------|---------------------|-------------|
| converting | false | `convert_document_task` 或 `process_document_task` |
| splitting / indexing_* | true | `index_document_task`（跳过转换） |

Admin 可以通过查看 `processing_meta` 来决定使用哪个 task 重试。

## 6. 与现有代码的关系

### 6.1 文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `infrastructure/tasks/pipeline_context.py` | 新建 | PipelineContext 类 |
| `infrastructure/tasks/document_tasks.py` | 重构 | 抽取 _execute_pipeline，重写三个 async 函数 |
| `domain/value_objects/processing_stage.py` | 新建 | ProcessingStage 枚举 |

### 6.2 向后兼容

`_process_document_async` 重构后通过 `_execute_pipeline` 调用，但外部行为不变：

- `process_document_task.delay(document_id)` 的调用方式不变
- UPLOADED 文档的处理流程不变
- FAILED 文档的重试行为不变
- 唯一行为变化：CONVERTED 文档进入完整流水线时自动跳过转换阶段
