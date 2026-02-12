# 文档处理模块 - 模块架构

## 1. Architecture Overview (总体架构)

### 1.1 架构演进背景

**当前架构 (ai-core-v1)** 存在的问题:

```python
# 当前 document_tasks.py 的处理流程
def _extract_text(path: str):
    extractor = get_extractor(path)  # PyPDF2/docx2txt/pandas
    result = extractor.extract(path)
    return result.text, result.page_count  # 返回纯文本,丢失结构

# 当前 content_extraction/base.py 的提取器
class PdfExtractor:
    def extract(self, path: str) -> ExtractionResult:
        reader = PyPDF2.PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return ExtractionResult(text="\n".join(pages))  # 纯文本
```

**问题**:
1. 纯文本丢失原文档结构(标题、表格、公式)
2. 前端无法渲染纯文本(需要 Markdown 格式)
3. 用户选中的文字与 RAG chunk 无法对应

**新架构目标**: 统一使用 Markdown 作为中间格式

### 1.2 新架构概览

文档处理模块采用分层架构,由三个核心组件构成:

```
                    +------------------+
                    |   调用方(API层)   |
                    +--------+---------+
                             |
                             v
+-----------------------------------------------------------+
|                    文档处理模块                              |
|  +------------------+  +------------------+  +-----------+ |
|  |   处理协调器      |  |   转换引擎适配器   |  |  内容存储  | |
|  |  (Coordinator)   |  |   (Converters)   |  |  (Store)  | |
|  +--------+---------+  +--------+---------+  +-----+-----+ |
|           |                     |                  |       |
+-----------------------------------------------------------+
            |                     |                  |
            v                     v                  v
     +------+------+       +------+------+    +-----+-----+
     | Celery 任务  |       | MinerU API |    | 文件系统   |
     |   队列       |       | MarkItDown |    |           |
     +-------------+       +-------------+    +-----------+
```

### 1.2 组件职责

**处理协调器 (Coordinator)**
- 接收文档处理请求
- 根据文件类型选择转换引擎
- 管理处理状态生命周期
- 协调异步任务调度

**转换引擎适配器 (Converters)**
- 封装外部转换服务的调用
- 提供统一的转换接口
- 处理转换结果的标准化

**内容存储 (Store)**
- 管理 Markdown 内容的持久化
- 提供内容读取接口
- 管理存储路径映射

---

## 2. Design Pattern & Rationale (设计模式与理由)

### 2.1 策略模式 (Strategy Pattern)

**应用位置**: 转换引擎选择

**选择理由**:
- 不同文件格式需要不同的转换策略
- PDF 使用 MinerU(高质量),Office 使用 MarkItDown(轻量)
- 便于后续添加新的转换引擎而不修改现有代码

**实现方式**:
- 定义统一的转换器接口
- 每种转换引擎实现该接口
- 协调器根据文件类型选择具体实现

### 2.2 适配器模式 (Adapter Pattern)

**应用位置**: 外部服务封装

**选择理由**:
- MinerU 通过 HTTP API 调用,MarkItDown 通过 Python 库调用
- 调用方式差异需要统一抽象
- 隔离外部服务变更对内部逻辑的影响

**实现方式**:
- MinerU 适配器封装 HTTP 请求/响应处理
- MarkItDown 适配器封装库函数调用
- 两者对外暴露相同的方法签名

### 2.3 异步任务模式

**应用位置**: 文档处理流程

**选择理由**:
- PDF 转换可能耗时数分钟
- 同步处理会阻塞 API 响应
- 需要支持任务重试和失败恢复

**实现方式**:
- 使用 Celery 任务队列
- 处理请求立即返回,后台异步执行
- 通过状态字段反映处理进度

---

## 3. Module Structure & File Layout (模块结构与文件组织)

### 3.1 目录结构

```
newbee_notebook/
├── infrastructure/
│   └── document_processing/          # 文档处理模块根目录
│       ├── coordinator.py            # 处理协调器
│       ├── converters/               # 转换引擎适配器
│       │   ├── base.py               # 转换器基类/接口
│       │   ├── mineru_converter.py   # MinerU 适配器
│       │   └── markitdown_converter.py # MarkItDown 适配器
│       ├── store.py                  # 内容存储
│       └── tasks.py                  # Celery 异步任务
│
├── api/routers/
│   └── documents.py                  # 文档 API (新增内容查询端点)
│
└── domain/entities/
    └── document.py                   # Document 实体 (扩展字段)
```

### 3.2 职责划分

| 目录/文件 | 职责 | 稳定性 |
|-----------|------|--------|
| coordinator.py | 流程编排,引擎选择 | 稳定接口 |
| converters/base.py | 转换器抽象接口 | 稳定接口 |
| converters/*_converter.py | 具体转换实现 | 内部实现,可替换 |
| store.py | 内容存储读写 | 稳定接口 |
| tasks.py | 异步任务定义 | 内部实现 |

### 3.3 依赖方向

```
API 层
   ↓ 依赖
协调器 (Coordinator)
   ↓ 依赖
转换器接口 (Converter Interface)
   ↓ 实现
具体转换器 (MinerU/MarkItDown)
```

依赖始终指向抽象,不指向具体实现。

---

## 4. Architectural Constraints & Trade-offs (约束与权衡)

### 4.1 MinerU 作为独立服务

**决策**: MinerU 运行在 Docker 容器中,通过 HTTP API 调用

**权衡**:
- 优点: 隔离 GPU 依赖,不影响主服务部署
- 优点: 可独立扩展和升级
- 缺点: 增加网络调用开销
- 缺点: 需要维护额外的服务

**放弃的方案**: 将 MinerU 作为 Python 库直接集成
- 放弃原因: GPU 依赖会使主服务部署复杂化

### 4.2 Markdown 存储在文件系统

**决策**: 转换后的 Markdown 存储在文件系统,数据库仅存储路径

**权衡**:
- 优点: 避免大文本影响数据库性能
- 优点: 便于直接查看和调试
- 缺点: 需要管理文件系统和数据库的一致性
- 缺点: 备份恢复需要同时处理两处

**放弃的方案**: 存储在数据库 TEXT 字段
- 放弃原因: 文档内容可能达到几十 MB,影响查询性能

### 4.3 单一 Markdown 格式输出

**决策**: 所有文档格式统一转换为 Markdown

**权衡**:
- 优点: 前端渲染逻辑统一
- 优点: 简化 API 设计
- 缺点: Excel 表格转换后会丢失公式和样式
- 缺点: 复杂排版的 PDF 可能转换效果不佳

**放弃的方案**: 保留多种格式,前端按类型渲染
- 放弃原因: 增加前端复杂度,不符合 MVP 阶段目标

### 4.4 同步内容查询

**决策**: 内容查询 API 同步读取文件返回

**权衡**:
- 优点: 实现简单
- 优点: 对于已完成的文档,响应快速
- 缺点: 超大文件可能导致响应较慢

**未来演进**: 如遇性能问题,可考虑分页读取或流式传输

---

## 5. 与现有模块的关系

### 5.1 与 DocumentService 的关系

DocumentService 负责:
- 文件上传和保存
- Document 实体的 CRUD
- 触发文档处理任务

本模块负责:
- 接收处理任务
- 执行格式转换
- 更新处理状态和内容路径

### 5.2 与 RAG 模块的关系 (重要变更)

**当前实现** (`document_tasks.py`):
```python
# 直接从原文件提取纯文本,创建 LlamaDocument
text, page_count = _extract_text(document.file_path)
llama_doc = LlamaDocument(text=text, metadata={...})
nodes = split_documents([llama_doc])
await _index_nodes(nodes)  # 直接索引到 PgVector 和 ES
```

**新实现**:
```python
# 1. 先转换为 Markdown 并保存
markdown_content = await _convert_to_markdown(document.file_path)
content_path = await _save_markdown(document_id, markdown_content)

# 2. 更新 Document 状态
await doc_repo.update_content_path(document_id, content_path)

# 3. RAG/ES 索引单独触发(从 Markdown 文件加载)
await _index_from_markdown(content_path, document_id)
```

**RAG 加载方式变更**:

| 当前 | 新方案 |
|------|--------|
| `SimpleDirectoryReader` + 多格式 Reader | `MarkdownReader` 统一加载 |
| 从原始文件提取 | 从 Markdown 文件加载 |
| 各格式独立处理 | 统一 Markdown 处理 |

**LlamaIndex MarkdownReader 特性** (参考 `llama_index/readers/file/markdown/base.py`):
- 按标题层级解析 Markdown
- 返回 `(header, text)` 元组列表
- 支持智能分块(按标题边界)

### 5.3 与 ES 索引的关系

**当前 ES 索引** (`es_search_tool.py`):
- 搜索字段: `content`, `text`, `title`
- 索引内容: 纯文本 chunk

**新 ES 索引**:
- 索引内容: Markdown chunk (保留格式标记)
- 搜索时仍使用 BM25,格式标记不影响检索
- 返回的 chunk 与前端展示一致

### 5.4 与前端的关系 (核心价值)

前端阅读器 (参考 `frontend-v1/03-components.md`):
- 调用内容查询 API 获取 Markdown
- 使用 react-markdown 渲染
- 支持用户选中文本进行 AI 交互

**数据一致性保证**:
```
前端展示: GET /documents/{id}/content → content.md → react-markdown 渲染
RAG 索引: content.md → MarkdownReader → split → PgVector
ES 索引:  content.md → MarkdownReader → split → Elasticsearch

用户选中 "xxx" → 发送 explain 请求 → RAG 检索 → 返回包含 "xxx" 的 chunk
```

前端 SelectionMenu 组件 (`frontend-v1/03-components.md:360-425`):
- 用户选中文字后显示 Explain/Conclude 按钮
- 发送请求时携带 `selected_text` 和 `document_id`
- 后端 RAG 可精确定位到对应 chunk

本模块通过 API 层与前端交互,不直接依赖前端实现。

### 5.5 Celery 任务流程变更

**当前任务流程** (`document_tasks.py:48-118`):
```
process_document_task(document_id)
    → _process_document_async(document_id)
        → _extract_text(file_path)           # 纯文本提取
        → LlamaDocument(text=text)           # 创建文档
        → split_documents([llama_doc])       # 分块
        → _index_nodes(nodes)                # 索引到 PgVector + ES
        → update_status(COMPLETED)
```

**新任务流程**:
```
process_document_task(document_id)
    → _process_document_async(document_id)
        → _convert_to_markdown(file_path)    # MinerU/MarkItDown 转换
        → _save_markdown(document_id, md)    # 保存 Markdown 文件
        → update_content_path(content_path)  # 更新数据库
        → _index_from_markdown(content_path) # 从 Markdown 索引
        → update_status(COMPLETED)
```

**新增函数**:
- `_convert_to_markdown(file_path)`: 根据文件类型选择 MinerU 或 MarkItDown
- `_save_markdown(document_id, content)`: 保存到文件系统
- `_index_from_markdown(content_path, document_id)`: 从 Markdown 文件创建索引
