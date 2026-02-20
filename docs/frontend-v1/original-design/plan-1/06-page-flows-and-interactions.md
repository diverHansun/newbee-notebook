# 页面流程与交互设计

本文档补充之前缺失的页面级交互设计，覆盖完整的用户操作流程。对应解决以下设计空白：

- 首页/Notebook 列表页的 UI 设计
- Library 页面设计
- 文档上传与 Library 管理流程
- 文档添加到 Notebook 后的处理状态轮询
- 来源引用（Sources）的展示与交互
- chat/ask 模式切换与 session 选择器
- 系统性错误处理策略

---

## 1. 应用核心流程

用户的完整操作路径：

```
首页（Notebook 列表）
  |
  |-- 上传文档到 Library（POST /documents/library/upload）
  |     文件仅存储，不解析
  |
  |-- 创建 Notebook（POST /notebooks）
  |
  |-- 从 Library 选择文档添加到 Notebook（POST /notebooks/{id}/documents）
  |     此时触发后端解析：uploaded -> pending -> processing -> completed
  |
  |-- 进入 Notebook 详情页（三栏布局）
  |     |-- Sources Panel：查看文档列表和处理状态
  |     |-- Main Panel：Chat/Ask 对话 或 Reader View 查看文档
  |     |-- Studio Panel：待定
  |
  |-- 文档处理完成后即可对话
```

关键设计原则：**Library-first 工作流**。文档必须先上传到 Library（仅存储），再关联到 Notebook 时才触发解析。Library 是全局文档存储，一个文档可被多个 Notebook 引用。

---

## 2. 首页 -- Notebook 列表页

路由：`/notebooks`（`/` 重定向到此）

### 2.1 页面布局

```
+------------------------------------------------------------------+
|  Header: NewBee Notebook                          [Theme Toggle]  |
+------------------------------------------------------------------+
|                                                                    |
|                        我的 Notebooks                              |
|                                                                    |
|   +------------------+  +------------------+  +------------------+ |
|   |                  |  |                  |  |                  | |
|   |  Notebook A      |  |  Notebook B      |  |  Notebook C      | |
|   |  3 docs, 2 chats |  |  5 docs, 0 chats |  |  1 doc,  4 chats | |
|   |  更新于 2 小时前  |  |  更新于 昨天     |  |  更新于 3 天前   | |
|   |                  |  |                  |  |                  | |
|   +------------------+  +------------------+  +------------------+ |
|                                                                    |
|                       （空状态时显示引导）                          |
|                                                                    |
+------------------------------------------------------------------+
|  底部操作栏                                                        |
|  [+ 创建 Notebook]    [上传文档到 Library]    [查看 Library]       |
+------------------------------------------------------------------+
```

### 2.2 Notebook 卡片

每张卡片展示：
- Notebook 标题
- 文档数量（`document_count`）
- 会话数量（`session_count`）
- 最近更新时间（`updated_at`，相对时间格式）
- 可选：描述摘要（`description` 截断显示）

交互：
- 点击卡片 -> 进入 `/notebooks/[id]` 详情页
- 卡片右上角 `...` 菜单 -> 编辑标题/描述（PATCH /notebooks/{id}）、删除（DELETE /notebooks/{id}，需确认弹窗）
- 按最近更新时间倒序排列

### 2.3 空状态

当没有任何 Notebook 时，主区域显示引导内容：

```
还没有 Notebook

Notebook 是你的 AI 知识助手工作区。
先上传文档到 Library，再创建 Notebook 开始对话。

[上传文档]  [创建 Notebook]
```

### 2.4 底部操作栏

固定在页面底部，三个按钮：

| 按钮 | 操作 | 后端端点 |
|------|------|----------|
| + 创建 Notebook | 弹出 Dialog，填写标题和描述 | POST /notebooks |
| 上传文档到 Library | 弹出文件选择器，支持多文件 | POST /documents/library/upload |
| 查看 Library | 跳转到 `/library` 页面 | - |

### 2.5 创建 Notebook Dialog

```
+---------------------------------------------+
|  创建新 Notebook                         [X] |
|                                               |
|  标题 *                                       |
|  +----------------------------------------+  |
|  | 输入 Notebook 标题...                   |  |
|  +----------------------------------------+  |
|                                               |
|  描述（可选）                                 |
|  +----------------------------------------+  |
|  | 简要描述这个 Notebook 的用途...          |  |
|  +----------------------------------------+  |
|                                               |
|                       [取消]  [创建]          |
+---------------------------------------------+
```

创建成功后：跳转到新 Notebook 的详情页 `/notebooks/[id]`，此时 Sources Panel 为空，引导用户添加文档。

### 2.6 添加文档到 Notebook -- 底部抽屉（Sheet）

在 Notebook 详情页的 Sources Panel 中点击"+ Add sources"或首页触发时，从底部弹出 Sheet：

```
+------------------------------------------------------------------+
|  添加文档到 Notebook                                          [X] |
|  ---------------------------------------------------------------- |
|                                                                    |
|  从 Library 选择文档:                                             |
|                                                                    |
|  [ ] 文档 A.pdf         uploaded    12 MB    2024-01-15          |
|  [ ] 文档 B.docx        completed   3 MB     2024-01-14          |
|  [v] 文档 C.pdf         uploaded    8 MB     2024-01-13          |
|  [v] 文档 D.pdf         completed   5 MB     2024-01-12          |
|                                                                    |
|  已选择 2 个文档                                                  |
|  ---------------------------------------------------------------- |
|  或上传新文档到 Library:                                          |
|  +------------------------------------------------------+        |
|  |  将文件拖放到此处，或点击选择文件                      |        |
|  |  支持 PDF、DOCX、TXT、MD（单文件最大 300MB）            |        |
|  +------------------------------------------------------+        |
|                                                                    |
|                                        [取消]  [添加到 Notebook]  |
+------------------------------------------------------------------+
```

交互细节：
- 上半部分：列出 Library 中的文档（GET /library/documents），支持多选 checkbox
- 已经在当前 Notebook 中的文档灰显不可选
- 文档列表中展示状态 Badge（uploaded/processing/converted/completed/failed），所有状态均可选
- 下半部分：支持直接上传新文件到 Library（POST /documents/library/upload），上传完成后自动出现在上方列表并选中
- 点击"添加到 Notebook"：POST /notebooks/{id}/documents，body: { document_ids: [...] }
- 被添加的文档如果 status 为 uploaded/failed，后端会自动排队处理（前端开始轮询）

**添加结果处理**（后端返回 `NotebookDocumentsAddResponse`，包含 added/skipped/failed）：

- 显示结果摘要 toast：
  - ✅ N 个文档已添加（含每个文档的 action：如"开始完整处理"/"仅需索引"/"已完成"）
  - ⚠️ N 个文档跳过（如"已在此 Notebook 中"）
  - ❌ N 个文档失败（如"文档不存在"）
- 全部成功时关闭 Sheet，刷新 Sources Panel 文档列表
- 有 skipped/failed 时保持 Sheet 打开，让用户查看具体原因

### 2.7 文件上传交互

上传入口有两处：
1. 首页底部"上传文档到 Library"按钮 -> 仅上传到 Library，不关联 Notebook
2. 添加文档 Sheet 中的上传区域 -> 上传到 Library 后自动列入可选列表

上传细节：
- 使用 `POST /documents/library/upload`，multipart/form-data，`files` 字段
- 支持多文件同时上传
- 上传进度：每个文件独立显示进度条
- 上传完成：显示成功/失败状态
- 文件大小限制和类型限制在前端做初步校验（参考后端配置）
- 支持拖拽上传（drag-and-drop）

---

## 3. Library 页面

路由：`/library`

### 3.1 页面布局

```
+------------------------------------------------------------------+
|  Header: NewBee Notebook  /  Library              [Theme Toggle]  |
+------------------------------------------------------------------+
|                                                                    |
|  Library 文档管理                        [上传文档]               |
|                                                                    |
|  过滤: [全部] [已上传] [处理中] [已完成] [失败]     搜索: [____]  |
|                                                                    |
|  +--------------------------------------------------------------+ |
|  | [ ] 文档标题           状态        大小    上传时间    操作   | |
|  |--------------------------------------------------------------| |
|  | [ ] 文档 A.pdf         已完成      12MB    1月15日    [...]   | |
|  | [ ] 文档 B.docx        处理中...   3MB     1月14日    [...]   | |
|  | [ ] 文档 C.pdf         已上传      8MB     1月13日    [...]   | |
|  | [ ] 文档 D.pdf         失败        5MB     1月12日    [...]   | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  已选 2 个    [批量删除]                                          |
|                                                                    |
|  分页: < 1 2 3 ... 10 >                                          |
+------------------------------------------------------------------+
```

### 3.2 核心功能

**文档列表**：
- 数据来源：GET /library/documents?limit=20&offset=0&status={filter}
- 表格列：选择框、文档标题、处理状态、文件大小、上传时间、操作菜单
- 状态 Badge 样式：uploaded（灰色）、pending/processing（蓝色+加载动画）、completed（绿色）、failed（红色）

**状态过滤**：
- Tab 式过滤条：全部 / 已上传 / 处理中 / 已完成 / 失败
- 通过 `status` 查询参数传给后端

**单个文档操作**（`...` 菜单）：
- 查看详情 -> Dialog 展示文档元数据
- 删除 -> 确认弹窗，分两级：
  - 软删除（默认）：DELETE /library/documents/{id}，移除索引和数据库记录，保留磁盘文件
  - 硬删除：DELETE /library/documents/{id}?force=true，彻底删除

**批量操作**：
- 全选 / 取消全选
- 批量删除（逐个调用删除 API）

**上传按钮**：
- 右上角"上传文档"按钮，打开文件选择器
- 与首页上传逻辑一致

### 3.3 与 Notebook Sources Panel 的关系

Library 是全局文档存储，Sources Panel 是 Notebook 级别的文档引用视图。两者的关系：

- Library 中的文档可以被多个 Notebook 引用
- 从 Notebook 中移除文档（DELETE /notebooks/{id}/documents/{did}）只是解除引用，不影响 Library
- 从 Library 中删除文档会影响所有引用了它的 Notebook

---

## 4. 文档处理状态轮询

### 4.1 状态流转

```
uploaded --> pending --> processing --> converted --> processing --> completed
                                   \-> failed       (索引阶段)   \-> failed
```

> 注意：后端 improve-8 已引入 `converted` 中间态。通过 Notebook 关联触发的完整流水线中，`converted` 是瞬间过渡状态；
> 但通过 admin/convert 单独触发转换时，文档会稳定停留在 `converted`。

- **uploaded**：文件已上传到 Library，尚未触发处理
- **pending**：已关联到 Notebook，等待处理队列
- **processing**：Worker 正在处理（可通过 `processing_stage` 查看子阶段）
- **converted**：文档已转换为 Markdown，等待索引（可查看内容，但不可对话）
- **completed**：全流程完成（转换 + 索引），可以查看和对话
- **failed**：处理失败，需查看错误信息（`error_message` 和 `processing_stage` 可定位失败位置）

### 4.2 轮询策略

使用 TanStack Query 的 `refetchInterval` 实现自动轮询：

```typescript
useQuery({
  queryKey: ['document', documentId],
  queryFn: () => fetchDocument(documentId),
  refetchInterval: (query) => {
    const status = query.state.data?.status;
    // 终态时停止轮询
    if (status === 'completed' || status === 'failed') return false;
    // converted 在 Notebook 上下文中也需轮询（完整流水线最终目标是 completed）
    // uploaded/pending/processing/converted 均继续轮询
    return 3000;
  },
});
```

### 4.3 Sources Panel 中的状态展示

在 Notebook 详情页的 Sources Panel 中，SourceCard 根据文档状态展示不同 UI：

| 状态 | 展示 | 交互 |
|------|------|------|
| uploaded / pending | 灰色 Badge "等待处理" | View 按钮禁用 |
| processing | 蓝色 Badge + 子阶段文本 + 加载动画 | View 按钮禁用 |
| converted | 黄色 Badge "已转换，等待索引" | View 按钮**可用**（可查看已转换的 Markdown） |
| completed | 绿色 Badge "已完成"（可隐藏） | View 按钮可用 |
| failed | 红色 Badge "处理失败" + 错误摘要 | 显示"重新处理"按钮 |

**processing 子阶段展示**（基于 `processing_stage` 字段）：

| processing_stage | Badge 文本 |
|-----------------|------------|
| converting | "转换文档中..." |
| splitting | "文本分块中..." |
| indexing_pg | "构建向量索引..." |
| indexing_es | "构建全文索引..." |
| finalizing | "完成处理中..." |

### 4.4 失败处理

文档处理失败时：
- SourceCard 显示红色"处理失败"Badge 和错误信息摘要（来自 GET /documents/{id} 的 `error_message`）
- 提供"重新处理"按钮，调用 POST /admin/documents/{id}/reindex?force=true
- 重新处理后 status 回到 pending，继续轮询

### 4.5 批量轮询优化

当 Notebook 中有多个文档正在处理时，不对每个文档单独轮询，而是轮询文档列表接口：

```typescript
useQuery({
  queryKey: ['notebook-documents', notebookId],
  queryFn: () => fetchNotebookDocuments(notebookId),
  refetchInterval: (query) => {
    const docs = query.state.data?.data || [];
    const NON_TERMINAL = ['uploaded', 'pending', 'processing', 'converted'];
    const hasProcessing = docs.some(d => NON_TERMINAL.includes(d.status));
    return hasProcessing ? 3000 : false;
  },
});
```

---

## 5. Notebook 详情页补充设计

路由：`/notebooks/[id]`

### 5.1 Session 选择器

在 ChatPanel 头部区域，mode 切换 Tabs 的上方或右侧，添加 session 选择器：

```
+----------------------------------------------------------+
|  Session: [当前会话标题          v]    [+ 新建会话]       |
|  -------------------------------------------------------- |
|  [Chat]  [Ask]                                            |
|  -------------------------------------------------------- |
|  消息列表 ...                                             |
```

Session 选择器是一个 Select/Combobox 下拉组件：
- 数据来源：GET /notebooks/{id}/sessions
- 默认选中最近会话：GET /notebooks/{id}/sessions/latest
- 首次进入时若无会话，第一条消息发送时自动创建（POST /notebooks/{id}/sessions）
- 切换 session 时重新加载消息列表（GET /sessions/{id}/messages）
- 下拉列表显示每个 session 的标题和消息数
- 支持删除 session（DELETE /sessions/{id}，需确认）

### 5.2 chat/ask 模式切换

模式切换器放在 ChatInput 输入框的左侧，而非头部 Tabs：

```
+----------------------------------------------------------+
|  Session: [当前会话标题          v]    [+ 新建会话]       |
|  -------------------------------------------------------- |
|  消息列表 ...                                             |
|                                                            |
|  -------------------------------------------------------- |
|  [Chat v]  +------------------------------------------+   |
|            | 输入消息...                               |   |
|            +------------------------------------------+   |
|                                                  [发送]   |
+----------------------------------------------------------+
```

- 左侧是模式选择下拉：Chat / Ask
- 模式差异：
  - **Chat**：通用对话模式，LLM 直接回复
  - **Ask**：文档问答模式，使用 RAG 检索 Notebook 中的文档后回答（需文档处理完成）
- 消息列表中混合展示两种模式的消息（通过 Badge 区分 mode）
- 切换模式不影响消息历史，只改变下一条消息的发送 mode
- Ask 模式发送时，若 Notebook 中没有 completed 状态的文档，给出提示

### 5.3 explain/conclude 浮动卡片

ExplainCard 是独立的浮动窗口，可在 Notebook 页面内任意拖动：

```
+-- ExplainCard ----------------+
|  [解释] "选中的文本..."   [_] [X] |
|  ----------------------------- |
|  AI 回复内容 ...               |
|  （流式加载中...）             |
|  ----------------------------- |
|  来源: [文档 A] [文档 B]      |
+--------------------------------+
```

特性：
- 可拖动（标题栏作为拖拽手柄）
- 可缩放（右下角拖拽调整大小）
- 可最小化（收缩为标题栏，点击恢复）
- 可关闭
- 默认尺寸：宽 400px，最大高度 500px
- 默认位置：Notebook 页面右下角
- 同一时间只有一个 ExplainCard（新的 explain/conclude 操作替换旧内容）

### 5.4 chat 409 冲突处理

当 Notebook 中存在任何 blocking 状态（uploaded/pending/processing/converted）的文档时，ask/explain/conclude 模式返回 409（error_code: E4001）。

> 重要：只要有**一个**文档未完成索引，**所有** RAG 模式都会被阻塞。

前端处理：

- 捕获 409 响应，解析 `error_code` 和 `details` 字段
- `details` 包含 `blocking_document_ids`（阻塞文档列表）和 `documents_by_status`（各状态计数）
- 在 ChatPanel 中显示系统提示消息，包含状态统计：

```
文档处理中，RAG 功能暂不可用
• 等待处理: {uploaded + pending} 个文档
• 处理中: {processing} 个文档
• 已转换待索引: {converted} 个文档
提示: 您可以先使用 Chat 模式进行通用对话
```

- chat 模式不受影响（不依赖文档索引）
- 前端可在加载 Notebook 文档列表时预判 blocking 状态，proactively 在 Ask 模式下显示提示或禁用发送

### 5.5 消息 mode 标记展示

消息列表混合展示所有模式的消息。每条 MessageItem 根据 `mode` 字段展示不同视觉标识：

| mode | Badge 样式 | 附加内容 |
|------|-----------|----------|
| chat | 蓝色 Badge "Chat" | 无 |
| ask | 绿色 Badge "Ask" | 回复附带 SourcesCard |
| explain | 紫色 Badge "Explain" | 显示选中文本引用 |
| conclude | 橙色 Badge "Conclude" | 显示选中文本引用 |

后端支持按 mode 过滤消息（`GET /sessions/{id}/messages?mode=chat,ask`），可在 ChatPanel 顶部添加过滤选项（非 MVP）。

### 5.6 Session 数量上限

每个 Notebook 最多 20 个 Session（后端硬限制）。前端处理：

- Session 选择器下拉列表底部显示计数："N / 20 个会话"
- 达到上限时，"+ 新建会话"按钮禁用，tooltip 提示"已达到上限（20 个），请删除不需要的会话"
- 首次发消息自动创建 Session 时也可能触发 400 错误（`SessionLimitExceededError`），需要在 ChatPanel 中友好提示

---

## 6. 来源引用（Sources）交互设计

### 6.1 Source 数据结构

后端返回的 sources 数组中每个元素的字段（基于 chat 端点响应）：

```typescript
// 注意：字段名必须与后端 ChatSource dataclass 和 SSE sources 事件精确匹配
interface Source {
  document_id: string;     // 引用的文档 ID
  chunk_id: string;        // chunk 标识（LlamaIndex node_id 或 "user_selection"）
  title: string;           // 文档标题（注意：不是 document_title）
  text: string;            // chunk 文本片段（注意：不是 content）
  score: number;           // 相关度评分（0.0 - 1.0）
}
```

### 6.2 SourcesCard 展示

```
+-- 引用来源 ---------------------+
|  [1] 文档 A.pdf                  |
|  "...相关文本片段预览..."         |
|  -------------------------------- |
|  [2] 文档 B.pdf                  |
|  "...相关文本片段预览..."         |
|  -------------------------------- |
|  [3] 文档 C.pdf                  |
|  "...相关文本片段预览..."         |
+----------------------------------+
|  展开更多（共 5 条）              |
+----------------------------------+
```

- 默认显示前 3 条引用，超过时显示"展开更多"
- 每条引用显示：序号、文档标题、文本片段预览（2行截断）
- 点击某条引用的行为：
  1. 打开对应文档的 Reader View（切换到 Reader View，加载该文档内容）
  2. MVP 阶段只定位到文档级别，不做段落级定位
  3. 后续迭代可通过文本搜索高亮定位到具体 chunk 位置

### 6.3 后续迭代方向（非 MVP）

- 段落级定位：在 Reader View 中搜索 chunk 文本并高亮
- 引用面板：独立的引用汇总面板，集中展示所有对话中的引用
- 引用关系图：可视化文档-问题-引用之间的关系

---

## 7. 错误处理策略

### 7.1 全局错误处理

| 错误场景 | 检测方式 | 处理策略 |
|----------|----------|----------|
| 网络断开 | fetch 抛 TypeError | 全局 toast 提示"网络连接断开"，TanStack Query 自动重试 |
| 后端不可用 | GET /health/ready 失败 | 全局降级 Banner："服务暂时不可用，请稍后重试" |
| API 4xx | ApiError status 4xx | 根据 error_code 分类处理（见下方） |
| API 5xx | ApiError status 5xx | toast 提示"服务器错误，请稍后重试" |

### 7.2 业务错误处理

| error_code | 含义 | 前端处理 |
|------------|------|----------|
| E4001 | 文档处理中，无法使用 RAG | ChatPanel 显示系统提示，建议使用 Chat 模式 |
| 404 | 资源不存在 | Notebook/Document 不存在时跳转到列表页 |
| 409 | 冲突（如重复添加文档） | toast 提示具体原因 |

### 7.3 SSE 连接错误

| 场景 | 处理 |
|------|------|
| SSE 连接意外断开 | 保留已接收的部分内容，标记消息为"回复中断"，显示"重新生成"按钮 |
| 心跳超时（>30秒无事件） | 客户端主动关闭连接，显示"连接超时"，提供重试按钮 |
| 流式取消 | 保留已接收内容，标记消息为已取消状态 |

### 7.4 文档内容加载失败

在 MarkdownViewer 组件中：
- 内容加载失败时显示错误占位："文档内容加载失败" + 重试按钮
- 图片加载失败时显示占位图（img onError 回调替换为占位元素）

### 7.5 TanStack Query 全局配置

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,                    // 失败重试 2 次
      staleTime: 30 * 1000,       // 30 秒内视为新鲜
      refetchOnWindowFocus: false, // 不在窗口聚焦时重新请求
    },
    mutations: {
      retry: 0,                    // mutation 不自动重试
    },
  },
});
```

---

## 8. 路由更新汇总

```
/                        # 重定向到 /notebooks
/notebooks               # Notebook 列表页（首页）
/notebooks/[id]          # Notebook 详情页（三栏布局）
/library                 # Library 文档管理页
```

各页面的布局类型：
- `/notebooks`：单栏，卡片网格 + 底部操作栏
- `/notebooks/[id]`：三栏可调布局（Sources | Main | Studio）
- `/library`：单栏，表格 + 过滤/搜索

---

## 9. 后端 API 端点映射（补充）

本文档涉及的后端端点汇总，补充之前文档未详细描述的端点用途：

### 首页与 Notebook 管理
- `POST /notebooks` — 创建 Notebook（body: title, description）
- `GET /notebooks` — Notebook 列表（分页）
- `GET /notebooks/{id}` — Notebook 详情
- `PATCH /notebooks/{id}` — 更新标题/描述
- `DELETE /notebooks/{id}` — 删除 Notebook（级联删除 sessions 和引用关系）

### 文档上传与 Library
- `POST /documents/library/upload` — 上传文件到 Library（multipart/form-data，支持多文件）
- `GET /library` — Library 信息（document_count）
- `GET /library/documents` — Library 文档列表（分页，支持 status 过滤）
- `DELETE /library/documents/{id}` — 软删除（保留磁盘文件）
- `DELETE /library/documents/{id}?force=true` — 硬删除（彻底删除）

### 文档关联与处理
- `POST /notebooks/{id}/documents` — 将 Library 文档关联到 Notebook（body: document_ids[]，触发处理）
- `GET /notebooks/{id}/documents` — Notebook 内文档列表（分页）
- `DELETE /notebooks/{id}/documents/{did}` — 解除关联（仅删除引用关系）
- `GET /documents/{id}` — 文档元数据与处理状态（用于轮询）

### Session 管理
- `POST /notebooks/{id}/sessions` — 创建 Session（body: title）
- `GET /notebooks/{id}/sessions` — Session 列表
- `GET /notebooks/{id}/sessions/latest` — 最新 Session
- `GET /sessions/{id}/messages` — 消息历史（支持 mode 过滤、分页）
- `DELETE /sessions/{id}` — 删除 Session

### 三级删除语义

| 操作 | 端点 | 影响范围 |
|------|------|----------|
| 从 Notebook 移除 | DELETE /notebooks/{nid}/documents/{did} | 仅解除引用关系 |
| Library 软删除 | DELETE /library/documents/{did} | 删除索引 + 数据库记录，保留磁盘文件 |
| Library 硬删除 | DELETE /library/documents/{did}?force=true | 彻底删除（索引 + 数据库 + 磁盘文件） |
