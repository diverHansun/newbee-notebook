# MediMind Agent 模式优化方案

## 文档信息

- 日期: 2026-01-28
- 版本: v2.0 (更新)
- 状态: 方案确认

---

## 一、问题背景

### 1.1 当前架构状态

MediMind Agent 支持四种交互模式:

| 模式 | 引擎类型 | 检索方式 | 对话记忆 | 使用场景 |
|------|---------|---------|---------|----------|
| Chat | FunctionAgent | ES作为工具调用 | 有 | 自由对话 |
| Ask | ReActAgent + HybridRetriever | pgvector + ES混合 | 有 | 深度问答 |
| Explain | RetrieverQueryEngine | 仅pgvector | 无 | 概念解释 |
| Conclude | RetrieverQueryEngine | 仅pgvector | 无 | 内容总结 |

### 1.2 已完成的功能

1. Celery异步文档处理流程
   - 文档上传后自动触发处理任务
   - 文本提取(PDF/DOCX/Excel/CSV/TXT/MD)
   - 分chunk(512 tokens, 50 overlap)
   - 自动索引到pgvector和Elasticsearch

2. 四种模式的基本实现
   - Chat/Ask模式支持对话记忆
   - Explain/Conclude模式无状态独立查询
   - SSE流式响应

3. Library和Notebook文档管理
   - Library全局文档库
   - Notebook引用Library文档
   - 文档范围过滤(MetadataFilter)

### 1.3 存在的问题

1. context.selected_text未被使用: Explain/Conclude模式接收前端传递的选中文本,但未融入查询
2. 缺少文档内容API: 前端无法获取文档的可读内容用于阅读器展示
3. 无Markdown转换: 文档提取为纯文本,不利于前端渲染
4. Explain模式缺少ES: 设计上应使用ES精确匹配选中文本

---

## 二、解决方案

### 2.1 后端改进

#### 2.1.1 selected_text增强查询

修改Explain和Conclude模式的_process方法,将selected_text融入查询:

```python
# explain_mode.py / conclude_mode.py
async def _process(self, message: str) -> str:
    query = message
    if self._context and self._context.get("selected_text"):
        selected = self._context["selected_text"]
        query = f"""请基于以下选中的文本内容进行分析:

---
{selected}
---

用户问题: {message}"""

    response = await self._query_engine.aquery(query)
    return str(response)
```

#### 2.1.2 文档内容API

新增获取文档内容的接口:

```
GET /api/v1/documents/{document_id}/content

Response:
{
  "document_id": "uuid",
  "content_type": "pdf",
  "content_markdown": "# 文档标题\n\n文档内容...",
  "original_file_available": true,
  "download_url": "/api/v1/documents/{id}/download"
}
```

#### 2.1.3 PDF转Markdown

使用PyMuPDF提取PDF结构化内容,转换为Markdown格式:

- 保留标题层级
- 保留段落结构
- 表格转换为Markdown表格
- 图片提取为Base64或链接

存储位置: Document表新增content_markdown字段

#### 2.1.4 原始文件下载

Excel/CSV等文件保留原始文件,提供下载接口:

```
GET /api/v1/documents/{document_id}/download
Response: 文件流
```

### 2.2 前端实现

#### 2.2.1 技术栈

| 组件 | 方案 |
|------|------|
| 框架 | Next.js 15 (App Router) |
| UI | shadcn/ui + Tailwind CSS |
| 状态 | Zustand + TanStack Query |
| Markdown | react-markdown + remark-gfm |
| 流式响应 | fetch + ReadableStream |

#### 2.2.2 三列布局

```
+------------------+--------------------+------------------+
|     Sources      |        Chat        |      Studio      |
|   (文档列表/     |    (对话区域)       |   (Notes等)      |
|    文档阅读器)   |                    |                  |
+------------------+--------------------+------------------+
      可伸缩              主区域              可伸缩
```

- 左侧: 文档列表或文档阅读器(切换显示)
- 中间: Chat/Ask对话区域
- 右侧: Notes和附加功能(暂不实现)

#### 2.2.3 文档阅读器交互

1. 用户点击View按钮,左侧切换为文档阅读器
2. 使用react-markdown渲染Markdown内容
3. 用户选中文字后,弹出操作菜单
4. 点击Explain或Conclude,发送请求到后端

#### 2.2.4 文本选中流程

```
用户选中文字
    |
    v
弹出菜单: [Explain] [Conclude]
    |
    v
点击按钮
    |
    v
发送请求:
POST /chat/notebooks/{id}/chat/stream
{
  mode: "explain" | "conclude",
  message: "请解释/总结这段内容",
  context: {
    document_id: "xxx",
    selected_text: "用户选中的文字"
  }
}
    |
    v
接收SSE流式响应
    |
    v
在聊天区域显示结果
```

---

## 三、实施计划

### 阶段1: 后端改进

| 任务 | 优先级 | 文件 |
|------|--------|------|
| selected_text增强 | 高 | explain_mode.py, conclude_mode.py |
| 文档内容API | 高 | documents.py, document_service.py |
| PDF转Markdown | 高 | content_extraction/base.py |
| 原始文件下载API | 中 | documents.py |

### 阶段2: 前端开发

| 任务 | 优先级 |
|------|--------|
| 项目初始化和技术栈配置 | 高 |
| 三列布局框架 | 高 |
| 文档列表组件 | 高 |
| 文档阅读器组件 | 高 |
| 文本选中和菜单 | 高 |
| 聊天组件和SSE处理 | 高 |

### 阶段3: 集成测试

| 任务 |
|------|
| 端到端测试: 上传 -> 处理 -> 阅读 -> 选中 -> AI响应 |
| 流式响应测试 |
| 多文档notebook测试 |

---

## 四、详细文档

- 后端文档: docs/backend-v1/
- 前端文档: docs/frontend-v1/

---

## 五、确认事项

### 已确认

1. 不需要"是否参与RAG"勾选框,文档加入notebook即参与检索
2. 先实现PDF转Markdown,Excel/CSV保留原始文件
3. 三列布局: Sources | Chat | Studio
4. 左侧面板切换: 文档列表 <-> 文档阅读器
5. Chat/Ask在中间交互区域,Explain/Conclude用于文档选中
6. 选中后直接执行,不需要额外输入框
7. 选中文字使用高亮显示
8. AI回复在消息下方显示来源卡片
9. Studio功能暂不实现

### Explain vs Conclude区别

| 模式 | 目的 | 检索方式 | 适用场景 |
|------|------|---------|---------|
| Explain | 解释概念 | RAG+ES(精确匹配) | 选中术语/概念 |
| Conclude | 总结内容 | pgvector(语义) | 选中段落/章节 |

后续需实现: 章节/大段内容的选中方式
