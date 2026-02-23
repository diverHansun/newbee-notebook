# P5: 可选 Sources 功能

## 问题描述

当前 notebook 中所有已完成（COMPLETED）的文档都自动参与 RAG 向量检索和 Elasticsearch 全文检索。用户无法指定搜索范围，导致：

1. 不相关文档的内容可能干扰检索结果的精度
2. 用户无法针对特定文档进行提问
3. Chat 和 Ask 模式都存在此问题

## 当前数据流

```
前端发送 ChatRequest(message, mode, session_id, context)
    |
    v
chat_service._get_notebook_scope(notebook_id)
    -> 获取 notebook 下所有 COMPLETED 状态的 document_id
    -> 返回 allowed_doc_ids（全量）
    |
    v
SessionManager.chat() / chat_stream()
    -> ModeSelector.run() / run_stream()
        -> mode.set_allowed_documents(allowed_doc_ids)
            |
            v
        Ask: HybridRetriever(pg_filters, es_filters, allowed_doc_ids)
        Chat: _collect_sources(message) 用 allowed_doc_ids 过滤
        Explain/Conclude: ChatEngine retriever 用 allowed_doc_ids 过滤
```

关键接入点：`allowed_doc_ids` 贯穿整个检索链路，只需在入口处做交集过滤即可。

## 设计方案

### 1. API 层变更

#### ChatRequest 扩展

文件：`newbee_notebook/api/routers/chat.py`（`ChatRequest` 实际定义在此文件第 31 行，而非 `api/models/requests.py`，后者只包含 `ChatContext` 等辅助模型）

```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: Literal["chat", "ask", "explain", "conclude"] = Field("chat")
    session_id: Optional[str] = Field(None)
    context: Optional[ChatContext] = Field(None)
    include_ec_context: Optional[bool] = Field(None)
    # 新增
    source_document_ids: Optional[List[str]] = Field(
        None,
        description="指定参与检索的文档 ID 列表。None 表示使用全部文档。"
    )
```

语义约定：
- `None`（默认）：使用 notebook 下所有 COMPLETED 文档，兼容现有行为
- `[id1, id2, ...]`：仅使用指定文档参与检索
- `[]`（空列表）：不使用任何文档（纯 LLM 对话）

#### 路由层透传

文件：`newbee_notebook/api/routers/chat.py`

在 `chat()` 和 `chat_stream()` 端点中，将 `request.source_document_ids` 传递给 `chat_service`。

### 2. 后端过滤逻辑

#### chat_service.py 变更

新增交集过滤方法：

```python
def _apply_source_filter(
    self,
    all_doc_ids: List[str],
    source_document_ids: Optional[List[str]],
) -> List[str]:
    """
    将用户选择的文档 ID 与 notebook 实际拥有的文档 ID 取交集。

    - source_document_ids = None: 返回全部（兼容旧行为）
    - source_document_ids = []: 返回空列表
    - source_document_ids = [...]: 返回交集
    """
    if source_document_ids is None:
        return all_doc_ids
    valid_set = set(all_doc_ids)
    return [doc_id for doc_id in source_document_ids if doc_id in valid_set]
```

在 `chat()` 和 `chat_stream()` 中调用：

```python
allowed_doc_ids, docs_by_status, blocking_doc_ids, completed_doc_titles = (
    await self._get_notebook_scope(session.notebook_id)
)
# 新增：应用用户选择过滤
allowed_doc_ids = self._apply_source_filter(allowed_doc_ids, source_document_ids)
```

后续流程不变——`allowed_doc_ids` 传入 `SessionManager`，再传入各 Mode，各 Mode 已有的过滤逻辑自动生效。

#### 模式兼容性

| 模式 | 使用 allowed_doc_ids 的方式 | 是否需要改动 |
|------|---------------------------|-------------|
| Chat | `_collect_sources()` 中 `build_document_filters(self.allowed_doc_ids)` | 无需改动 |
| Ask | `_refresh_retriever()` 中 `build_document_filters(self.allowed_doc_ids)` | 无需改动 |
| Explain | `_build_retriever()` 中 `build_document_filters(self.allowed_doc_ids)` | 无需改动 |
| Conclude | 同 Explain | 无需改动 |

ES search tool（`es_search_tool.py`）也通过 `allowed_doc_ids` 过滤，无需改动。

### 3. 前端 API 层

#### chat.ts 变更

`chatStream()` 和 `chatOnce()` 的请求体新增 `source_document_ids` 字段：

```typescript
export async function chatStream(
  notebookId: string,
  body: {
    message: string;
    mode: string;
    session_id?: string;
    context?: ChatContext;
    include_ec_context?: boolean;
    source_document_ids?: string[] | null;  // 新增
  },
  callbacks: StreamCallbacks,
): Promise<void> { ... }
```

### 4. 前端 SourceSelector 组件

#### 交互流程

```
1. 输入区左下角，SegmentedControl 旁边显示一个文档图标按钮
2. 点击按钮 -> 从下往上弹出 Source Selector 面板
3. 面板显示文档列表（checkbox）
4. 用户勾选/取消文档
5. 点击"完成"按钮 -> 面板收起
6. 面板收起后，选中的文档以 chips 形式显示在输入区上方（仅当非全选时显示）
```

#### 面板视觉规格

```
                    ┌──────────────────────────────────┐
                    │  选择检索范围              [完成] │  标题栏
                    ├──────────────────────────────────┤
                    │  [x] 全部文档                    │  全选/取消全选
                    ├──────────────────────────────────┤
                    │  [x] paper-title-1.pdf           │
                    │  [x] research-notes.md           │  文档列表
                    │  [ ] meeting-summary.docx        │  （滚动区域）
                    │  [x] data-analysis.pdf           │
                    └──────────────────────────────────┘
输入区 ──────────────────────────────────────────────────
```

- 面板从输入区底部向上展开，`position: absolute`，`bottom: 100%`
- 最大高度：240px，超出滚动
- 背景：`hsl(var(--card))`
- 边框：`1px solid hsl(var(--border))`
- 圆角：顶部 `border-radius: 8px 8px 0 0`
- 展开/收起动画：`transform: translateY` + `opacity` 过渡（200ms）

#### 文档列表数据获取

复用已有的 `listDocumentsInNotebook()` API：

```typescript
import { listDocumentsInNotebook } from "@/lib/api/documents";

// 获取 COMPLETED 状态的文档
const { items } = await listDocumentsInNotebook(notebookId, {
  status: "completed",
  limit: 100,
});
```

返回的 `NotebookDocumentItem` 包含 `document_id`、`title`、`content_type`、`file_size` 等字段，足够渲染列表。

边界场景处理：
- **无可用文档**：若 `items` 为空，文档图标按鈕显示为禁用态，面板内显示“暂无可用文档”提示。
- **文档数超过 100 个**：`limit: 100` 为当前软性上限，面板底部显示“共 N 个文档，仅显示前 100 个”提示，后续可提升 limit 或分页。
- **API 失败**：请求失败时，按鈕保持可点击，面板内显示错误提示并提供重试入口。

#### 组件接口

```typescript
type SourceSelectorProps = {
  notebookId: string;
  selectedIds: string[] | null;          // null = 全部
  onChange: (ids: string[] | null) => void;
};
```

文件位置：`frontend/src/components/chat/source-selector.tsx`

#### 状态管理

在 `chat-store.ts` 或 `chat-panel.tsx` 的本地 state 中维护：

```typescript
// null = 全部文档（默认），string[] = 指定文档
const [sourceDocIds, setSourceDocIds] = useState<string[] | null>(null);
```

此状态在 session 切换时重置为 `null`。

发送消息时，将 `sourceDocIds` 传入 `chatStream()` / `chatOnce()`。

#### 选中提示（Chips）

当用户选择了部分文档（非全选）时，在输入区上方显示已选文档的 chips：

```
  [paper-1.pdf x] [notes.md x] [+2 更多]
  ┌─ 输入区 ──────────────────────────┐
  │ ...                                │
  └────────────────────────────────────┘
```

- 每个 chip 显示文档标题（截断到 16 字符）+ 关闭按钮
- 超过 3 个时显示 "+N 更多"
- 全选时不显示 chips（默认行为，无需提示）

### 5. 输入区布局整合

结合 P3 的输入区重设计，完整的输入区结构为：

```
┌─ chat-input-container ─────────────────────────────────┐
│                                                        │
│  [paper-1.pdf x] [notes.md x]     ← source chips      │
│                                    （仅非全选时显示）     │
│                                                        │
│  ┌─ textarea ────────────────────────────────────┐     │
│  │ 输入消息...                                    │     │
│  └───────────────────────────────────────────────┘     │
│                                                        │
│  [Chat|Ask]  [文档图标]                          (●)   │
│                                                        │
└────────────────────────────────────────────────────────┘

         ^
         |  点击文档图标时弹出 Source Selector 面板
```

文档图标按钮位于 SegmentedControl 右侧，使用与发送按钮相同的圆形图标风格（但尺寸略小，28x28px）。

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/api/routers/chat.py` | ChatRequest 新增 source_document_ids；端点透传 |
| `newbee_notebook/application/services/chat_service.py` | _apply_source_filter 方法 |
| `frontend/src/lib/api/chat.ts` | 请求体新增字段 |
| `frontend/src/components/chat/source-selector.tsx` | 新增组件 |
| `frontend/src/components/chat/chat-input.tsx` | 集成 SourceSelector 和 chips |
| `frontend/src/components/chat/chat-panel.tsx` | sourceDocIds 状态管理 |
| `frontend/src/app/globals.css` | SourceSelector 样式 |
| `frontend/src/lib/i18n/strings.ts` | 新增文本常量 |

## 验证标准

- 默认行为（不选择）与当前完全一致，全部文档参与检索
- 点击文档图标，Source Selector 从下方平滑弹出
- 文档列表正确显示 notebook 中所有 COMPLETED 文档
- 勾选/取消操作正常，全选按钮逻辑正确
- 点击"完成"后面板收起，选中结果以 chips 显示
- 发送消息时 source_document_ids 正确传入后端
- 后端仅对指定文档执行 RAG 和 ES 检索
- Chat 和 Ask 模式都能正确使用指定 sources
- Explain/Conclude 模式不受影响（它们使用 context.document_id 指定单文档）
- session 切换时 source 选择重置为全部
- **边界场景**：notebook 下无 COMPLETED 文档时，文档图标按钮不可用，面板显示"暂无可用文档"提示
- **边界场景**：COMPLETED 文档数超过 100 时，面板底部显示"共 N 个文档，仅显示前 100 个"提示