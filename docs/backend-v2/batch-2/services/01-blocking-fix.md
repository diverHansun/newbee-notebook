# 文档处理阻塞逻辑修复设计

## 1. 问题描述

### 1.1 当前阻塞逻辑

`ChatService._validate_mode_guard()` 在检测到 notebook 中存在任何处于非 COMPLETED 状态的文档时，直接阻塞所有 RAG 依赖模式（ASK/EXPLAIN/CONCLUDE），返回 HTTP 409。

```python
# chat_service.py:527-538 -- 当前代码
if mode_enum in rag_modes and (blocking_document_ids or []):
    raise DocumentProcessingError("文档正在处理中，请稍后重试")
```

阻塞判定发生在两处，调用同一个 `_validate_mode_guard()`:
- `prevalidate_mode_requirements()`: 流式接口建立 SSE 连接前，返回 HTTP 409
- `chat_stream()` 内部: SSE 连接已建立后，转为 SSE error 事件

### 1.2 两类阻塞问题

#### 问题 A: Agent/Ask 模式 -- notebook 级别过度阻塞

前端 "选择检索范围" 下拉框展示 notebook 中的文档列表，用户可选择检索哪些文档。

```
notebook 中有 7 个文档:
  5 个 COMPLETED (已完成，索引已构建)
  1 个 PROCESSING (MinerU 正在转换)
  1 个 FAILED (处理失败)

当前行为: 用户点击 Ask -> 409，整个 notebook 的 RAG 功能不可用
期望行为: Ask 正常工作，检索范围 = 5 个已完成文档
          "选择检索范围" 下拉框仅展示/可选 COMPLETED 文档
```

典型场景:
1. 用户向 notebook 添加新文档，处理期间无法对已有文档提问
2. 某个文档处理失败（FAILED），导致整个 notebook 的 RAG 功能不可用
3. 批量上传文档时，必须等待所有文档处理完成才能开始交互

#### 问题 B: Explain/Conclude 模式 -- 文档级别状态不匹配

文档处理分为两阶段: MinerU 转换（PDF -> Markdown）和索引构建（pgvector + ES）。当 MinerU 转换完成但索引未构建时（CONVERTED 状态），文档的 markdown 内容已可查看（View 按钮可用），但 RAG 检索不可用。

```
文档状态: CONVERTED (markdown 可查看，但 pgvector + ES 索引未建)

当前行为: 用户查看文档 -> 选中文本 -> 点击 "解释/总结" -> 409 或失败
期望行为: 明确告知 "该文档索引尚未构建完成，暂时无法进行解释/总结"
```

此问题是文档级别的: 用户操作的 `context.document_id` 对应的文档本身未完成索引，与 notebook 中其他文档的状态无关。

### 1.3 文档状态与功能可用性

| DocumentStatus | 含义 | 进入 completed_doc_ids | 进入 blocking_ids | Agent/Ask 可检索 | Explain/Conclude 可操作 | View 可查看 |
|---|---|---|---|---|---|---|
| COMPLETED | 处理完成 | 是 | 否 | 是 | 是 | 是 |
| UPLOADED | 已上传未处理 | 否 | 是 | 否 | 否 | 否 |
| PENDING | 队列等待中 | 否 | 是 | 否 | 否 | 否 |
| PROCESSING | 正在处理 | 否 | 是 | 否 | 否 | 否 |
| CONVERTED | 转换完成索引未建 | 否 | 是 | 否 | 否 | 是 |
| FAILED | 处理失败 | 否 | 否 | 否 | 否 | 视情况 |

FAILED 状态: 既不可检索也不阻塞其他文档。用户可重新处理或删除。

## 2. 设计目标

1. Agent/Ask 模式: 有 COMPLETED 文档即可使用，检索范围为所有 COMPLETED 文档
2. Explain/Conclude 模式: 按目标文档状态判断，仅当 `context.document_id` 对应文档为 COMPLETED 时可操作
3. 部分文档处理中时，以 warning 事件通知前端（信息性，不阻塞功能）
4. 底层检索管道不需要修改（已正确实现 document_id 过滤）

## 3. 修改方案

### 3.1 修改 _validate_mode_guard() -- 核心变更

将阻塞粒度从 "notebook 级别一刀切" 改为 "按模式分层判断":

```python
async def _validate_mode_guard(self, mode_enum, allowed_doc_ids, context,
                                notebook_id, documents_by_status,
                                blocking_document_ids) -> None:

    # --- Agent/Ask: notebook 级别，有可用文档即放行 ---
    rag_modes = (ModeType.ASK, ModeType.CONCLUDE, ModeType.EXPLAIN)
    if mode_enum in rag_modes:
        if not allowed_doc_ids and (blocking_document_ids or []):
            raise DocumentProcessingError(
                message="所有文档正在处理中，暂无可用的检索数据",
                details={
                    "mode": mode_enum.value,
                    "notebook_id": notebook_id,
                    "blocking_document_ids": blocking_document_ids or [],
                    "documents_by_status": documents_by_status or {},
                    "retryable": True,
                },
            )

    # --- Explain/Conclude: 文档级别，检查目标文档状态 ---
    if mode_enum in (ModeType.CONCLUDE, ModeType.EXPLAIN):
        if not allowed_doc_ids and not (context and context.get("selected_text")):
            raise ValueError(
                "Conclude/Explain mode requires at least one processed document "
                "or a selected_text context."
            )
        if context and context.get("selected_text") and not context.get("document_id"):
            raise ValueError(
                "selected_text requires a document_id to ensure traceable sources"
            )
        # 目标文档未完成索引时阻塞
        if context and context.get("document_id"):
            target_doc_id = context["document_id"]
            if target_doc_id in (blocking_document_ids or []):
                raise DocumentProcessingError(
                    message="该文档索引尚未构建完成，暂时无法进行解释/总结",
                    details={
                        "mode": mode_enum.value,
                        "document_id": target_doc_id,
                        "retryable": True,
                    },
                )
        if self._session_manager.vector_index is None:
            raise RuntimeError("Vector index is not available")
```

决策依据:
- 底层检索管道（ES filter、pgvector scope、tool_registry）已正确实现按 document_id 过滤
- `_get_notebook_scope()` 已区分 completed_doc_ids 和 blocking_ids
- 只需放开 guard 层的过度限制，无需修改底层检索逻辑
- Explain/Conclude 的 `context.document_id` 明确标识了用户操作的目标文档，可做精确判断

### 3.2 增加 warning 机制

当 Agent/Ask 模式放行但存在 blocking 文档时，以 warning 事件通知前端。

流式响应（chat_stream）: 在 start 事件后、thinking 事件前插入:

```python
# 构建 warning
blocking_warning = self._build_blocking_warning(blocking_doc_ids, allowed_doc_ids, docs_by_status)

yield {"type": "start", "message_id": message_id}
if blocking_warning:
    yield blocking_warning
if mode_enum != ModeType.CHAT:
    yield {"type": "thinking", "stage": "retrieving"}
```

`_build_blocking_warning()` 私有方法:

```python
@staticmethod
def _build_blocking_warning(
    blocking_doc_ids: List[str],
    allowed_doc_ids: List[str],
    docs_by_status: Dict[str, int],
) -> Optional[Dict[str, Any]]:
    if not blocking_doc_ids or not allowed_doc_ids:
        return None
    return {
        "type": "warning",
        "code": "partial_documents",
        "message": f"{len(blocking_doc_ids)} 个文档正在处理中，当前检索范围不包含这些文档",
        "details": {
            "blocking_document_ids": blocking_doc_ids,
            "available_document_count": len(allowed_doc_ids),
            "documents_by_status": docs_by_status,
        },
    }
```

非流式响应（chat）: 在 ChatResult 中增加 `warnings: List[dict]` 字段:

```python
@dataclass
class ChatResult:
    session_id: str
    message_id: int
    content: str
    mode: ModeType
    sources: List[ChatSource]
    warnings: List[dict] = field(default_factory=list)
```

### 3.3 _apply_source_filter() 增加排除日志

当用户通过 `source_document_ids` 指定了未就绪的文档时，记录日志便于排查:

```python
@staticmethod
def _apply_source_filter(
    all_doc_ids: List[str],
    source_document_ids: Optional[List[str]],
) -> List[str]:
    if source_document_ids is None:
        return all_doc_ids
    valid_set = set(all_doc_ids)
    filtered = [doc_id for doc_id in source_document_ids if doc_id in valid_set]
    excluded = [doc_id for doc_id in source_document_ids if doc_id not in valid_set]
    if excluded:
        logger.info(
            "source_document_ids filter excluded %d non-completed doc(s): %s",
            len(excluded), excluded,
        )
    return filtered
```

保持返回值为 `List[str]` 不变，避免影响调用方签名。

### 3.4 SSE 层适配

`SSEEvent` 增加 warning 格式方法:

```python
@staticmethod
def warning(code: str, message: str, details: Optional[dict] = None) -> str:
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return SSEEvent.format("warning", payload)
```

`sse_adapter` 已是通用的事件字典转 SSE 字符串逻辑，无需额外修改。

## 4. 场景矩阵

### Agent/Ask 模式

| 场景 | blocking_docs | completed_docs | source_filter | 行为 |
|------|-------------|---------------|--------------|------|
| 全部完成 | 0 | N | - | 正常，检索全部 N 个文档 |
| 部分处理中 | M | N (N>0) | - | 正常 + warning，检索 N 个已完成文档 |
| 全部处理中 | M | 0 | - | 阻塞 409 "所有文档正在处理中" |
| 全部失败 | 0 | 0 | - | 无可检索文档（FAILED 不阻塞也不可检索） |
| 用户指定已完成文档 | M | N | [doc_A] | 正常 + warning，仅检索 doc_A |
| 用户指定处理中文档 | M | N | [doc_C] | source_filter 过滤后为空，回退到全部 completed 检索 |

### Explain/Conclude 模式

| 场景 | 目标文档状态 | 其他文档 | 行为 |
|------|-----------|---------|------|
| 目标文档 COMPLETED | COMPLETED | 有 blocking | 正常 + warning |
| 目标文档 COMPLETED | COMPLETED | 全部 COMPLETED | 正常 |
| 目标文档 CONVERTED | CONVERTED | 有 COMPLETED | 阻塞 409 "该文档索引尚未构建完成" |
| 目标文档 PROCESSING | PROCESSING | 有 COMPLETED | 阻塞 409 "该文档索引尚未构建完成" |
| 无 document_id（纯选区） | - | 有 COMPLETED | 正常，使用选区文本直接交互 |

### Chat 模式

| 场景 | 行为 |
|------|------|
| 任何状态组合 | 正常（Chat 不依赖 RAG） |

## 5. SSE 事件协议

### 新增 warning 事件

```json
{
  "type": "warning",
  "code": "partial_documents",
  "message": "2 个文档正在处理中，当前检索范围不包含这些文档",
  "details": {
    "blocking_document_ids": ["doc_c_id", "doc_d_id"],
    "available_document_count": 5,
    "documents_by_status": {
      "completed": 5,
      "processing": 1,
      "pending": 1
    }
  }
}
```

### 事件时序

```
start -> warning(如有) -> thinking -> content... -> sources -> done
```

### 前端处理建议

- 收到 warning 事件后，在 UI 中显示非阻断性提示（toast 或 banner）
- 提示内容告知用户哪些文档尚未就绪，不影响正常的内容流渲染
- 未处理 warning 事件时不会出错（SSE 事件可忽略，向后兼容）

### 前端文档列表适配

"选择检索范围" 下拉框应根据文档状态调整显示:
- COMPLETED: 正常显示，可勾选
- PROCESSING/PENDING/UPLOADED/CONVERTED: 显示为不可选或隐藏，附带状态标签
- FAILED: 显示为不可选，附带失败标签

此为前端变更，后端已通过 notebook-document 列表接口返回文档状态字段。

## 6. 影响分析

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `application/services/chat_service.py` | `_validate_mode_guard()` 逻辑、`_build_blocking_warning()` 新增、`_apply_source_filter()` 日志、`ChatResult.warnings` 字段 |
| `api/routers/chat.py` | `SSEEvent.warning()` 方法、`ChatResponse.warnings` 字段 |

### 不需要修改的模块

| 模块 | 原因 |
|------|------|
| `core/tools/es_search_tool.py` | 已支持 allowed_doc_ids 过滤 |
| `core/tools/tool_registry.py` | 已按 allowed_doc_ids 构建工具 |
| `core/engine/session.py` | 不感知文档状态 |
| `domain/entities/document.py` | 状态模型无需变更 |
| `infrastructure/tasks/` | 处理管道无需变更 |
| `core/rag/` | 检索层无需变更 |

### 独立性

此修复不依赖 core 模块重构（context/engine/session/tools 四模块拆分），可在当前代码上独立实施。

### 向后兼容性

- 新增 warning SSE 事件类型，不影响现有 start/content/sources/done 事件
- 前端未处理 warning 事件时静默忽略，不会出错
- ChatResult.warnings 为可选字段，默认空列表
- 409 错误仍保留（仅在 "无任何可用文档" 或 "目标文档未就绪" 时触发），前端现有 409 处理逻辑兼容

## 7. 测试场景

### Agent/Ask 模式

1. notebook 有 blocking doc 和 completed doc 时，Ask 正常返回并附带 warning 事件
2. notebook 所有文档都在处理中时，Ask 返回 409 "所有文档正在处理中"
3. notebook 无任何文档时，Ask 正常返回（无检索数据，由 LLM 自行回答）
4. notebook 所有文档 FAILED 时，Ask 正常返回（FAILED 不阻塞）
5. source_document_ids 指定处理中文档时被过滤，日志记录

### Explain/Conclude 模式

6. 选中 COMPLETED 文档的文本，其他文档有 blocking，正常返回 + warning
7. 选中 CONVERTED 文档的文本（markdown 可查看但索引未建），返回 409 "该文档索引尚未构建完成"
8. 选中 PROCESSING 文档的文本，返回 409
9. 无 document_id 的纯选区文本，有 COMPLETED 文档时正常返回

### Chat 模式

10. 任何文档状态组合下 Chat 模式正常工作

### SSE 协议

11. warning 事件在 SSE 流中正确位于 start 和 thinking 之间
12. 前端未处理 warning 事件时流正常完成
