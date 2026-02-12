# 文档处理模块 - 数据流与接口

## 1. Context & Scope (上下文与范围)

### 1.1 模块交互关系

```
+----------------+     +-------------------+     +-------------+
| DocumentService| --> | 文档处理模块       | --> | 文件系统     |
+----------------+     +-------------------+     +-------------+
                              |
                              v
                       +-------------+
                       | MinerU API  |
                       | (Docker)    |
                       +-------------+
                              ^
                              |
+----------------+     +------+------+
| API 路由层     | <-- | 文档处理模块 |
| (documents.py) |     | (内容查询)   |
+----------------+     +-------------+
```

### 1.2 本文档讨论范围

- 文档处理任务的触发与执行流程
- 与 MinerU API 服务的交互
- 内容存储的读写流程
- 对外暴露的内容查询接口

### 1.3 本模块与 RAG/ES 索引的关系 (重要变更)

**当前架构**: RAG/ES 索引独立于文档处理模块
**新架构**: 文档处理模块负责转换 + 触发 RAG/ES 索引

```
新模块交互关系:

+----------------+     +-------------------+     +------------------+
| DocumentService| --> | 文档处理模块       | --> | Markdown 文件     |
+----------------+     +-------------------+     +--------+---------+
                              |                          |
                              v                          v
                       +-------------+            +------+-------+
                       | MinerU API  |            | RAG/ES 索引   |
                       | MarkItDown  |            | (从MD加载)    |
                       +-------------+            +--------------+
```

### 1.4 不在本文档范围

- 文件上传流程(由 DocumentService 负责)
- 前端渲染逻辑

---

## 2. Data Flow Description (数据流描述)

### 2.1 当前实现 vs 新实现对比

**当前实现** (参考 `document_tasks.py:48-118`):

```python
async def _process_document_async(document_id: str):
    # 1. 提取纯文本
    text, page_count = _extract_text(document.file_path)

    # 2. 创建 LlamaDocument
    llama_doc = LlamaDocument(text=text, metadata={...})

    # 3. 分块
    nodes = split_documents([llama_doc], chunk_size=512, chunk_overlap=50)

    # 4. 直接索引到 PgVector 和 ES
    await _index_nodes(nodes)

    # 5. 更新状态
    await doc_repo.update_status(document_id, DocumentStatus.COMPLETED)
```

**问题**: 纯文本丢失结构,前端无法渲染,选中文字无法与 chunk 对应

**新实现**:

```python
async def _process_document_async(document_id: str):
    # 1. 转换为 Markdown (MinerU/MarkItDown)
    markdown_content, page_count = await _convert_to_markdown(document.file_path)

    # 2. 保存 Markdown 文件
    content_path = await _save_markdown(document_id, markdown_content)

    # 3. 更新 Document 的 content_path
    await doc_repo.update_content_path(document_id, content_path)

    # 4. 从 Markdown 文件创建索引 (使用 MarkdownReader)
    await _index_from_markdown(content_path, document_id)

    # 5. 更新状态
    await doc_repo.update_status(document_id, DocumentStatus.COMPLETED)
```

### 2.2 文档转换流程 (新)

```
[触发] DocumentService 调用处理协调器
    |
    | 输入: document_id, file_path, content_type
    v
[协调器] 创建异步任务
    |
    | 更新 Document.status = PROCESSING
    v
[任务队列] Celery Worker 获取任务
    |
    v
[协调器] 根据 content_type 选择转换器
    |
    +-- PDF --> MinerU 转换器
    |              |
    |              | HTTP POST /file_parse
    |              v
    |           [MinerU API Docker]
    |              |
    |              | 返回 Markdown + 图片
    |              v
    +-- 其他 --> MarkItDown 转换器
                   |
                   | 本地库调用 (uv add markitdown)
                   |
                   | 支持: DOCX, XLSX, PPTX, CSV 等
                   v
               Markdown 内容
    |
    v
[内容存储] 写入 Markdown 文件
    |
    | 路径: data/documents/{document_id}/content.md
    | 图片: data/documents/{document_id}/images/
    v
[协调器] 更新 Document.content_path
    |
    v
[RAG/ES 索引] 从 Markdown 文件创建索引
    |
    | 使用 LlamaIndex MarkdownReader 加载
    | MarkdownReader 特性:
    |   - 按标题层级解析
    |   - 返回 (header, text) 结构
    |   - 智能分块边界
    |
    | 分块后插入:
    |   - PgVector (向量索引)
    |   - Elasticsearch (全文索引)
    v
[协调器] 更新 Document
    |
    | Document.chunk_count = len(nodes)
    | Document.status = COMPLETED
    v
[完成]
```

### 2.2 内容查询流程

```
[触发] 前端请求 GET /documents/{id}/content
    |
    v
[API 路由] 验证 document_id
    |
    v
[DocumentService] 获取 Document 实体
    |
    | 检查 status == COMPLETED
    | 获取 content_path
    v
[内容存储] 读取 Markdown 文件
    |
    | 输入: content_path
    | 输出: markdown_content
    v
[API 路由] 构建响应
    |
    | 返回: document_id, title, content, page_count, ...
    v
[响应] 返回给前端
```

### 2.3 错误处理流程

```
[转换过程发生错误]
    |
    v
[协调器] 捕获异常
    |
    | 更新 Document.status = FAILED
    | 更新 Document.error_message = 错误描述
    v
[完成] 任务结束,不重试
```

---

## 3. Interface Definition (接口定义)

### 3.1 内部接口

#### 3.1.1 处理协调器接口

**触发文档处理**

| 属性 | 说明 |
|------|------|
| 调用方 | DocumentService |
| 输入 | document_id |
| 输出 | 无(异步执行) |
| 行为 | 创建 Celery 任务,立即返回 |

**查询处理状态**

| 属性 | 说明 |
|------|------|
| 调用方 | 任意 |
| 输入 | document_id |
| 输出 | ProcessingStatus |
| 行为 | 读取 Document.status 返回 |

#### 3.1.2 转换器接口

**执行转换**

| 属性 | 说明 |
|------|------|
| 调用方 | 处理协调器 |
| 输入 | file_path, output_dir |
| 输出 | ConversionResult |
| 行为 | 调用外部服务或库,返回转换结果 |
| 异步 | 是(MinerU 为 HTTP 调用) |

#### 3.1.3 内容存储接口

**保存内容**

| 属性 | 说明 |
|------|------|
| 调用方 | 处理协调器 |
| 输入 | document_id, markdown_content, images |
| 输出 | content_path |
| 行为 | 创建目录,写入文件,返回相对路径 |

**读取内容**

| 属性 | 说明 |
|------|------|
| 调用方 | API 路由层 |
| 输入 | content_path |
| 输出 | markdown_content |
| 行为 | 读取文件内容返回 |

### 3.2 外部接口

#### 3.2.1 MinerU API 接口

**PDF 转换请求**

| 属性 | 说明 |
|------|------|
| 端点 | POST /file_parse |
| 输入 | files(文件), backend, lang_list, return_md |
| 输出 | JSON(包含 md_content, images) |
| 超时 | 300 秒 |

#### 3.2.2 对外 HTTP API

**获取文档内容**

| 属性 | 说明 |
|------|------|
| 端点 | GET /api/v1/documents/{document_id}/content |
| 参数 | format(可选): markdown/text |
| 成功响应 | 200, 包含 content 字段 |
| 错误响应 | 404(文档不存在), 400(未处理完成) |

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| document_id | string | 文档唯一标识 |
| title | string | 文档标题 |
| content_type | string | 原始文件类型 |
| format | string | 返回内容的格式 |
| content | string | Markdown 或纯文本内容 |
| page_count | integer | 文档页数 |
| chunk_count | integer | 分块数量 |
| content_size | integer | 内容大小(字节) |

---

## 4. Data Ownership & Responsibility (数据归属与责任)

### 4.1 数据创建责任

| 数据 | 创建者 | 说明 |
|------|--------|------|
| Document 实体 | DocumentService | 上传时创建 |
| Document.content_path | 本模块 | 转换完成时设置 |
| Markdown 文件 | 本模块 | 转换完成时创建 |
| 图片文件 | 本模块 | 转换时提取并保存 |

### 4.2 数据更新责任

| 数据 | 更新者 | 触发条件 |
|------|--------|----------|
| Document.status | 本模块 | 状态流转时 |
| Document.content_path | 本模块 | 转换完成时 |
| Document.content_size | 本模块 | 转换完成时 |
| Document.error_message | 本模块 | 转换失败时 |

### 4.3 数据删除责任

| 数据 | 删除者 | 触发条件 |
|------|--------|----------|
| Document 实体 | DocumentService | 用户删除文档 |
| Markdown 文件 | DocumentService | 删除 Document 时级联删除 |
| 图片文件 | DocumentService | 删除 Document 时级联删除 |

### 4.4 一致性保证

- 本模块更新 Document 时使用事务,确保状态和路径同时更新
- 文件写入成功后才更新数据库,失败时不更新
- 删除操作先删文件后删数据库记录,保证不留孤立文件

---

## 5. 与 Docker 服务的交互

### 5.1 MinerU API 服务

| 配置项 | 说明 |
|--------|------|
| 服务名 | mineru-api |
| 内部端口 | 8000 |
| 外部端口 | 8001 |
| 网络 | newbee_notebook_network |

### 5.2 调用方式

- Celery Worker 运行在 Docker 网络内,通过 `http://mineru-api:8000` 调用
- 本地开发时,FastAPI 通过 `http://localhost:8001` 调用

### 5.3 健康检查

调用 MinerU API 前应检查服务可用性:
- 端点: GET /docs
- 超时: 5 秒
- 失败处理: 标记任务失败,记录错误信息

---

## 6. 边界条件处理

### 6.1 MinerU 服务不可用

- 行为: 任务标记为 FAILED
- 错误信息: "MinerU service unavailable"
- 不自动重试(避免队列堆积)

### 6.2 文件读取失败

- 行为: 任务标记为 FAILED
- 错误信息: 包含具体 IO 错误
- 原始文件路径不存在时,记录警告日志

### 6.3 转换超时

- 超时阈值: 300 秒
- 行为: 任务标记为 FAILED
- 错误信息: "Conversion timeout exceeded"

### 6.4 内容查询时文件不存在

- 行为: 返回 404 错误
- 响应: {"detail": "Content file not found"}
- 日志: 记录 content_path 与实际文件不一致的警告
