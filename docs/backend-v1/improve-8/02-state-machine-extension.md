# 02 - 状态机扩展：CONVERTED 状态与 ProcessingStage 枚举

## 1. 概述

本文档定义两个核心变更：

1. DocumentStatus 扩展：新增 `CONVERTED` 中间状态
2. ProcessingStage 枚举化：替代硬编码 stage 字符串，仅包含过程阶段

## 2. DocumentStatus 扩展

### 2.1 现有状态

```python
class DocumentStatus(str, Enum):
    UPLOADED   = "uploaded"     # 文件已保存，等待处理
    PENDING    = "pending"      # 排队等待 worker 执行
    PROCESSING = "processing"   # Worker 正在处理
    COMPLETED  = "completed"    # 全流程完成
    FAILED     = "failed"       # 处理失败
```

### 2.2 扩展后状态

```python
class DocumentStatus(str, Enum):
    UPLOADED   = "uploaded"     # 文件已保存，等待处理
    PENDING    = "pending"      # 排队等待 worker 执行
    PROCESSING = "processing"   # Worker 正在处理
    CONVERTED  = "converted"    # 新增: 转换完成，Markdown已生成
    COMPLETED  = "completed"    # 全流程完成（转换+索引）
    FAILED     = "failed"       # 处理失败
```

### 2.3 CONVERTED 状态语义

| 属性 | 说明 |
|------|------|
| 含义 | MinerU/MarkItDown 已将原始文件转换为 Markdown，assets 已保存到磁盘 |
| 磁盘状态 | `data/documents/{id}/markdown/content.md` 已存在，`assets/images/` 已保存 |
| 数据库状态 | `content_path` 已填写，`content_size` 已计算，`page_count` 已记录 |
| 索引状态 | pgvector 和 ES 均未建索引，`chunk_count = 0` |
| 可执行操作 | 可触发 `index_document_task`（仅索引）、可查看转换后内容、可加入 Notebook |
| 终端性 | 非终端状态——是一个稳定的等待点，可以长期停留 |
| 对话能力 | 不可对话——视为 blocking 状态，必须完成索引后才能参与 RAG 检索 |

### 2.4 与现有状态的对比

| 状态 | 磁盘文件 | Markdown | pgvector | ES | 可对话 |
|------|---------|----------|----------|-----|--------|
| UPLOADED | raw/ 存在 | 无 | 无 | 无 | 否 |
| PROCESSING | raw/ 存在 | 生成中 | 无 | 无 | 否 |
| CONVERTED | raw/ 存在 | markdown/ 存在 | 无 | 无 | 否 |
| COMPLETED | raw/ 存在 | markdown/ 存在 | 已索引 | 已索引 | 是 |
| FAILED | raw/ 存在 | 可能部分 | 已清理 | 已清理 | 否 |

## 3. 状态转换规则

### 3.1 完整状态转换图

```
                         +--------------------------------------+
                         |            文件上传到 Library          |
                         +-----------------+--------------------+
                                           |
                                           v
                                    +----------+
                                    | UPLOADED  |
                                    +--+---+----+
                                       |   |
          admin/convert ---------------+   +------- add_to_notebook / admin/reprocess
          (仅转换)                                   (完整流水线)
                  |                                        |
                  v                                        v
           +------------+                          +------------+
           | PROCESSING | (stage=converting)       | PROCESSING | (stage=converting)
           +------+-----+                          +------+-----+
                  |                                       |
          转换完成 |                                       | 转换完成
                  v                                       |
           +-----------+                                  |
           | CONVERTED | <-- 新增稳定中间态                 |
           +--+----+---+                                  |
              |    |                                      |
   admin/index|    |add_to_notebook                       | 继续 splitting->indexing
   (仅索引)    |    |(智能补齐)                              |
              |    |                                      |
              v    v                                      |
        +------------+                                    |
        | PROCESSING | (stage=splitting)                  |
        +------+-----+                                    |
               |                                          |
               | indexing_pg -> indexing_es -> finalizing  |
               |                                          |
               v                                          v
          +-----------+                             +-----------+
          | COMPLETED |                             | COMPLETED |
          +-----------+                             +-----------+

               任意 PROCESSING 阶段异常
                         |
                         v
                    +--------+
                    | FAILED | <-- (记录 failed_stage + error_message)
                    +---+----+
                        |
                        | retry / reprocess
                        v
                  回到相应入口重试
```

### 3.2 有效状态转换表

| 起始状态 | 目标状态 | 触发条件 | 说明 |
|----------|---------|---------|------|
| -- | UPLOADED | `upload_to_library()` | 初始上传 |
| UPLOADED | PROCESSING | `claim_processing()` | 开始转换或完整流水线 |
| UPLOADED | PENDING | `add_documents()` (legacy) | 现有兼容路径 |
| PENDING | PROCESSING | `claim_processing()` | Worker 认领 |
| PROCESSING | CONVERTED | `convert_document_task` complete | 仅转换模式 |
| PROCESSING | COMPLETED | `process_document_task` complete | 完整流水线模式 |
| PROCESSING | FAILED | 任意阶段异常 | 记录失败信息 |
| CONVERTED | PROCESSING | `claim_processing()` via `index_document_task` | 开始索引 |
| CONVERTED | COMPLETED | 不可直接跳转 | 必须经过 PROCESSING |
| FAILED | PROCESSING | `claim_processing()` | 重试（任意模式） |
| FAILED | PENDING | `reprocess-pending` | 批量重试兼容路径 |

### 3.3 claim_processing() 的允许源状态更新

当前允许：`[UPLOADED, PENDING, FAILED]`

扩展后允许：`[UPLOADED, PENDING, FAILED, CONVERTED]`

```python
# 扩展后
claimed = await doc_repo.claim_processing(
    document_id,
    from_statuses=[DocumentStatus.UPLOADED, DocumentStatus.PENDING,
                   DocumentStatus.FAILED, DocumentStatus.CONVERTED],
    ...
)
```

> 注意：CONVERTED -> PROCESSING 仅在 `index_document_task` 中触发，表示从"已转换"进入"正在索引"。

## 4. ProcessingStage 枚举

### 4.1 设计原则

ProcessingStage 枚举仅描述 `PROCESSING` 状态下文档正在执行的子阶段。不包含 `COMPLETED` 或 `CONVERTED` 等结果状态，因为结果状态是 `DocumentStatus` 的职责（SRP 原则）。

### 4.2 定义

```python
# newbee_notebook/domain/value_objects/processing_stage.py

from enum import Enum


class ProcessingStage(str, Enum):
    """文档处理阶段 -- 仅描述 PROCESSING 状态期间的子阶段。

    注意：不包含 EMBEDDING 阶段。向量嵌入由 pgvector insert 内部完成，
    没有独立的可观测步骤，因此不作为单独的 stage 暴露。
    """

    QUEUED       = "queued"        # 已排队，等待 worker 领取
    CONVERTING   = "converting"    # MinerU/MarkItDown 正在转换文件
    SPLITTING    = "splitting"     # MarkdownReader + SentenceSplitter 分块
    INDEXING_PG  = "indexing_pg"   # 写入 pgvector 向量索引（含嵌入计算）
    INDEXING_ES  = "indexing_es"   # 写入 Elasticsearch 全文索引
    FINALIZING   = "finalizing"    # 更新最终元数据和状态

    @property
    def is_conversion_phase(self) -> bool:
        """属于转换阶段。"""
        return self == ProcessingStage.CONVERTING

    @property
    def is_indexing_phase(self) -> bool:
        """属于索引阶段。"""
        return self in (
            ProcessingStage.SPLITTING,
            ProcessingStage.INDEXING_PG,
            ProcessingStage.INDEXING_ES,
            ProcessingStage.FINALIZING,
        )
```

### 4.3 终态时 processing_stage 的处理规则

当文档到达终态时，`processing_stage` 按以下规则设置：

| 终态 | processing_stage 值 | 说明 |
|------|---------------------|------|
| CONVERTED | `None` | DocumentStatus 已表明结果，stage 清空 |
| COMPLETED | `None` | 同上 |
| FAILED | 保留失败时的 stage 值 | 用于诊断失败位置和决定重试策略 |

> **实施注意**：现有 `document_repo_impl.py` 中 `update_status` 使用 `if processing_stage is not None` 做条件赋值，传 `None` 等同于"不更新"而非"清空为 NULL"。终态清空逻辑要求 `update_status` 能区分"未传参"和"显式传 None"。实施时需引入 sentinel 值（如 `_UNSET = object()`）。详见 Phase 1 任务 1.4。

### 4.4 替代现有硬编码

```python
# 修改前（硬编码字符串）
await _set_stage("converting")
await _set_stage("splitting")

# 修改后（类型安全枚举）
await _set_stage(ProcessingStage.CONVERTING)
await _set_stage(ProcessingStage.SPLITTING)
```

### 4.5 数据库兼容性

`processing_stage` 列是 `VARCHAR`/`TEXT` 类型，枚举继承 `str`，存储值不变。无需数据库迁移。

## 5. Document Entity 扩展

### 5.1 新增属性方法

```python
# domain/entities/document.py

@property
def is_converted(self) -> bool:
    """文档是否已完成转换（不含索引）。"""
    return self.status == DocumentStatus.CONVERTED

@property
def needs_conversion(self) -> bool:
    """文档是否需要转换。"""
    return self.status in (DocumentStatus.UPLOADED, DocumentStatus.FAILED)

@property
def needs_indexing(self) -> bool:
    """文档是否需要索引（已转换但未索引）。"""
    return self.status == DocumentStatus.CONVERTED

@property
def is_ready_for_chat(self) -> bool:
    """文档是否可以进入对话。"""
    return self.status == DocumentStatus.COMPLETED

def mark_converted(self, page_count, content_path, content_size) -> None:
    """标记文档转换完成。"""
    self.status = DocumentStatus.CONVERTED
    self.page_count = page_count
    self.content_path = content_path
    self.content_size = content_size
    self.content_format = "markdown"
    self.processing_stage = None  # 终态清空 stage
    self.error_message = None
```

### 5.2 DocumentStatus 的属性扩展

```python
class DocumentStatus(str, Enum):
    # ... 现有值 ...
    CONVERTED = "converted"

    @property
    def is_terminal(self) -> bool:
        """终端状态（不再自动推进）。"""
        return self in (DocumentStatus.COMPLETED, DocumentStatus.FAILED)

    @property
    def is_stable(self) -> bool:
        """稳定状态（可以长期停留）。"""
        return self in (
            DocumentStatus.UPLOADED,
            DocumentStatus.CONVERTED,
            DocumentStatus.COMPLETED,
            DocumentStatus.FAILED,
        )

    @property
    def is_blocking(self) -> bool:
        """阻塞状态（未完成索引，不可参与对话）。"""
        return self in (
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.CONVERTED,
        )

    @property
    def can_start_conversion(self) -> bool:
        """是否可以开始转换。"""
        return self in (DocumentStatus.UPLOADED, DocumentStatus.FAILED)

    @property
    def can_start_indexing(self) -> bool:
        """是否可以开始索引。"""
        return self == DocumentStatus.CONVERTED
```

## 6. 数据库影响评估

### 6.1 Schema 变更

无需 DDL 变更。`status` 和 `processing_stage` 均为 VARCHAR 类型，`CONVERTED` 和 `converted` 作为新值可直接写入。

### 6.2 查询影响

需要更新以下查询逻辑：

| 查询 | 影响 | 处理方式 |
|------|------|---------
| `list_by_library(status=...)` | CONVERTED 需要作为合法过滤值 | 枚举自动支持 |
| `claim_processing(from_statuses=...)` | 需要在仅索引场景中包含 CONVERTED | 调用方传参控制 |
| `_get_notebook_scope()` | CONVERTED 需加入 blocking_statuses | 新增 CONVERTED 到集合 |
| 前端状态展示 | 需要识别 `converted` 状态 | 前端增加 CONVERTED 状态映射 |

### 6.3 向后兼容

- API 响应中 `status` 字段新增 `"converted"` 值，前端如果使用 switch/case 需要增加该分支
- 现有 `completed` / `failed` / `uploaded` / `processing` 的行为完全不变
- Postman Collection 中的 status 过滤查询需要更新文档
