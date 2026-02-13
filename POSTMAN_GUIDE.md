# Newbee Notebook API - Postman 测试指南

本指南详细说明如何使用 Postman 测试 Newbee Notebook 后端 API，包括环境搭建、数据库初始化、接口测试和问题排查。

---

## 目录
- [前置条件](#前置条件)
- [环境准备](#环境准备)
- [导入 Postman 集合](#导入-postman-集合)
- [配置变量](#配置变量)
- [完整测试流程](#完整测试流程)
- [模块测试详解](#模块测试详解)
- [已知问题和解决方案](#已知问题和解决方案)
- [高级功能](#高级功能)
- [故障排查](#故障排查)

---

## 前置条件

### 必需的软件
- Python 3.10+
- Docker 和 Docker Compose
- Postman Desktop 或 Postman Web

### 必需的服务
- PostgreSQL (通过 Docker)
- Elasticsearch (通过 Docker)
- Redis (通过 Docker)

---

## 环境准备

### 1. 启动 Docker 服务

```bash
# 进入项目目录
cd newbee-notebook

# 启动所有依赖服务
docker-compose up -d

# 验证服务状态
docker-compose ps
```

预期输出应显示以下容器正在运行：
- `newbee-notebook-postgres` (PostgreSQL + pgvector)
- `newbee-notebook-elasticsearch` (Elasticsearch)
- `newbee-notebook-redis` (Redis)
- `newbee-notebook-celery-worker` (Celery 异步任务处理)

### 2. 验证数据库初始化

数据库表会在容器首次启动时自动创建。验证数据库状态：

```bash
# 检查数据库表
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "\dt"

# 检查 pgvector 扩展
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

预期应看到以下表：
- library
- notebooks
- documents
- sessions
- messages
- references
- notebook_document_refs
- chat_sessions
- chat_messages

### 3. 安装 Python 依赖

```bash
# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 安装依赖（如果尚未安装）
pip install -r requirements.txt

# 确保安装 redis 包（用于 Celery）
pip install redis
```

### 4. 配置环境变量

确保 `.env` 文件中包含正确的配置：

```env
# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=newbee_notebook_password
POSTGRES_DB=newbee_notebook

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# Elasticsearch 配置
ELASTICSEARCH_URL=http://localhost:9200

# LLM API 配置
ZHIPU_API_KEY=your_api_key_here
```

### 5. 启动 API 服务器

```bash
# 方式 1：使用 uvicorn 直接运行
python -m uvicorn newbee_notebook.api.main:app --reload --port 8000

# 方式 2：使用项目入口脚本（仅启动 FastAPI，Docker 服务请先单独启动）
python main.py --reload --port 8000
```

验证服务器启动成功：
```bash
curl http://localhost:8000/api/v1/health
```

预期响应：`{"status":"ok"}`

---

## 导入 Postman 集合

### 步骤 1：打开 Postman
启动 Postman Desktop 应用或访问 Postman Web。

### 步骤 2：导入集合
1. 点击左上角 **Import** 按钮
2. 选择 **Upload Files**
3. 浏览到项目根目录，选择 `postman_collection.json`
4. 点击 **Import** 确认

### 步骤 3：验证导入
导入成功后，在左侧 Collections 面板应该看到：
- **Newbee Notebook API (local)**
  - Health (4 个请求)
  - Library (3 个请求)
  - Documents (7 个请求)
  - Notebooks (7 个请求)
  - Sessions (6 个请求，包含消息列表接口)
  - Chat (3 个请求)

---

## 配置变量

### 集合级变量配置

点击 Collections 中的 "Newbee Notebook API (local)"，进入 Variables 标签页：

| 变量名 | 初始值 | 当前值 | 说明 |
|--------|--------|--------|------|
| `base_url` | `http://localhost:8000` | `http://localhost:8000` | API 基础 URL |
| `api_prefix` | `/api/v1` | `/api/v1` | API 路径前缀 |
| `api_base` | `{{base_url}}{{api_prefix}}` | - | 完整 API 基础路径（自动计算） |
| `notebook_id` | - | - | 创建 Notebook 后自动填充 |
| `session_id` | - | - | 创建 Session 后自动填充 |
| `document_id` | - | - | 创建 Document 后自动填充 |
| `reference_id` | - | - | 创建 Reference 后自动填充 |
| `message_id` | - | - | 聊天消息 ID |

**注意**：集合中的请求已配置测试脚本，会自动提取响应中的 ID 并保存到变量中，无需手动复制粘贴。

### 环境变量（可选）

如果需要测试多个环境（本地/开发/生产），可以创建 Postman 环境：

1. 点击右上角眼睛图标
2. 选择 **Environments**
3. 创建新环境并配置 `base_url`

---

## 完整测试流程

### 测试流程图

```
1. Health Check (验证服务状态)
   |
2. Get System Info (获取系统信息)
   |
3. Get Library (获取库信息)
   |
4. Create Notebook (创建笔记本) --> 自动保存 notebook_id
   |
5. List Notebooks (验证笔记本创建成功)
   |
6. Create Session (创建会话) --> 自动保存 session_id
   |
7. List Sessions (验证会话创建成功)
   |
8. Send Chat Message (发送聊天消息)
   |
9. Verify Message History (验证消息持久化)
   |
10. Update/Delete Resources (可选清理操作)
```

### 快速测试序列

按顺序执行以下请求（每个请求都包含自动测试脚本）：

1. **Health/Basic** - 基础健康检查
2. **Health/System Info** - 获取系统信息
3. **Library/Get Library** - 获取库信息
4. **Notebooks/Create Notebook** - 创建测试笔记本
5. **Sessions/Create Session** - 创建测试会话
6. **Chat/Chat (non-stream)** - 发送测试消息

每个请求执行后，检查 **Tests** 标签页，确保所有测试通过（绿色勾号）。

---

## 模块测试详解

### 1. Health 模块

#### 目的
验证 API 服务器和依赖服务（数据库、缓存等）的运行状态。

#### 测试请求

**1.1 Basic Health Check**
```
GET /api/v1/health
```
验证：
- 响应状态码 200
- 返回 `{"status": "ok"}`

**1.2 Readiness Check**
```
GET /api/v1/health/ready
```
验证：
- 响应状态码 200
- 数据库连接正常
- 必要的服务已就绪

**1.3 Liveness Check**
```
GET /api/v1/health/live
```
验证：
- 响应状态码 200
- 进程存活且响应请求

**1.4 System Info**
```
GET /api/v1/info
```
验证：
- 返回系统名称、版本
- 返回支持的功能列表
- 返回支持的聊天模式

预期响应示例：
```json
{
  "name": "Newbee Notebook",
  "version": "1.0.0",
  "features": {
    "library": true,
    "notebooks": true,
    "sessions": true,
    "chat_modes": ["chat", "ask", "explain", "conclude"]
  }
}
```

### 2. Library 模块

#### 目的
测试文档库的管理功能。Library 是一个单例实体，用于存储共享文档。

#### 测试请求

**2.1 Get Library**
```
GET /api/v1/library
```
验证：
- 返回库的 UUID
- 返回文档计数
- 包含创建和更新时间戳

**2.2 List Library Documents**
```
GET /api/v1/library/documents?limit=20&offset=0&status=completed
```
参数说明：
- `limit`: 返回结果数量（默认 20）
- `offset`: 分页偏移量（默认 0）
- `status`: 文档状态过滤（pending/processing/completed/failed）

验证：
- 返回文档列表
- 包含分页信息
- 正确过滤文档状态

### 3. Notebooks 模块

#### 目的
测试笔记本的 CRUD 操作。Notebook 是组织文档和会话的容器。

#### 测试请求

**3.1 Create Notebook**
```
POST /api/v1/notebooks
Content-Type: application/json

{
  "title": "Test Notebook",
  "description": "Backend testing notebook"
}
```
验证：
- 响应状态码 201
- 返回新创建的 notebook_id
- 自动保存 notebook_id 到集合变量
- session_count 和 document_count 初始为 0

**3.2 List Notebooks**
```
GET /api/v1/notebooks?limit=20&offset=0
```
验证：
- 返回笔记本列表
- 包含完整的分页信息
- 按更新时间排序

**3.3 Get Notebook**
```
GET /api/v1/notebooks/{{notebook_id}}
```
验证：
- 返回指定笔记本的详细信息
- 包含所有字段

**3.4 Update Notebook**
```
PATCH /api/v1/notebooks/{{notebook_id}}
Content-Type: application/json

{
  "title": "Updated Title",
  "description": "Updated description"
}
```
验证：
- 响应状态码 200
- 更新的字段已生效
- updated_at 时间戳已更新

**3.5 Delete Notebook**
```
DELETE /api/v1/notebooks/{{notebook_id}}
```
验证：
- 响应状态码 204
- 相关的 Session 和 Reference 被级联删除

### 4. Sessions 模块

#### 目的
测试会话管理。每个 Notebook 最多可以有 20 个 Session。

#### 测试请求

**4.1 Create Session**
```
POST /api/v1/notebooks/{{notebook_id}}/sessions
Content-Type: application/json

{
  "title": "Test Session",
  "include_ec_context": false
}
```
验证：
- 响应状态码 201
- 返回新创建的 session_id
- 自动保存 session_id 到集合变量
- message_count 初始为 0
- include_ec_context 默认值正确（未传时为 false）

**4.2 List Sessions**
```
GET /api/v1/notebooks/{{notebook_id}}/sessions?limit=20&offset=0
```
验证：
- 返回会话列表
- 按创建时间倒序排列

**4.3 Get Latest Session**
```
GET /api/v1/notebooks/{{notebook_id}}/sessions/latest
```
验证：
- 返回最新创建的会话
- 如果没有会话则返回 404

**4.4 Get Session**
```
GET /api/v1/sessions/{{session_id}}
```
验证：
- 返回指定会话的详细信息

**4.5 Delete Session**
```
DELETE /api/v1/sessions/{{session_id}}
```
验证：
- 响应状态码 204
- 相关的 Message 和 Reference 被级联删除

**4.6 Get Session Messages**
```
GET /api/v1/sessions/{{session_id}}/messages?mode=chat,ask&limit=20&offset=0
```
参数说明：
- `mode`: 可选，逗号分隔过滤（`chat|ask|explain|conclude`）
- `limit`: 每页条数（1-100）
- `offset`: 分页偏移量

验证：
- 响应状态码 200
- 返回 `data + pagination`
- mode 过滤生效（如 `mode=explain,conclude`）

### 5. Chat 模块

#### 目的
测试聊天功能，包括非流式和流式响应。

#### 测试请求

**5.1 Chat (non-stream)**
```
POST /api/v1/chat/notebooks/{{notebook_id}}/chat
Content-Type: application/json

{
  "message": "Hello, can you help me?",
  "mode": "chat",
  "session_id": "{{session_id}}",
  "context": null,
  "include_ec_context": null
}
```
参数说明：
- `message`: 用户消息内容（必需）
- `mode`: 聊天模式（chat/ask/explain/conclude）
- `session_id`: 会话 ID（可选，如果省略会自动创建新会话）
- `context`: 额外上下文信息（可选）
- `include_ec_context`: 可选，请求级覆盖开关。`true` 时在 Chat/Ask 中注入近期 Explain/Conclude 摘要；`null` 时沿用 Session 默认值

验证：
- 响应状态码 200
- 返回 session_id、message_id、content
- content 包含助手的回复
- sources 数组（在 RAG 模式下会包含引用来源）

预期响应示例：
```json
{
  "session_id": "b4915538-aee3-40b5-b24d-ecf7c6154c85",
  "message_id": 1,
  "content": "\nHello! I'd be happy to help you. What can I assist you with today?",
  "mode": "chat",
  "sources": []
}
```

**5.2 Chat Stream (SSE)**
```
POST /api/v1/chat/notebooks/{{notebook_id}}/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "message": "Stream a short answer",
  "mode": "ask",
  "session_id": "{{session_id}}",
  "context": null,
  "include_ec_context": true
}
```
验证：
- Content-Type 为 `text/event-stream`
- 接收多个 SSE 事件
- 事件格式符合 SSE 规范

SSE 事件格式：
```
event: chunk
data: {"content": "Hello", "delta": "Hello"}

event: chunk
data: {"content": "Hello world", "delta": " world"}

event: done
data: {"session_id": "...", "message_id": 1, "sources": []}
```

**5.3 Cancel Stream**
```
POST /api/v1/chat/stream/{{message_id}}/cancel
```
验证：
- 响应状态码 200
- 流式传输被中止

### 6. Documents 模块

#### 目的
测试文档的上传、注册和管理。

#### 重要说明
文档上传功能依赖 Celery 异步任务处理。如果遇到错误，请参考"已知问题和解决方案"部分。

#### 测试请求

**6.1 Register Library Document (metadata) [已废弃]**
```
POST /api/v1/documents/library
Content-Type: application/json

{
  "title": "Example report",
  "content_type": "pdf",
  "url": "https://example.com/report.pdf",
  "file_path": "",
  "file_size": 102400
}
```
当前行为：
- 返回 `410 Gone`（已废弃）
- 请改用 `POST /api/v1/documents/library/upload`

**6.2 Upload File to Library（推荐）**
```
POST /api/v1/documents/library/upload
Content-Type: multipart/form-data

file: [选择本地文件]
```
步骤：
1. 在 Body 标签页选择 `form-data`
2. 添加 key 为 `file`，类型选择 `File`
3. 点击 "Select Files" 选择本地文件

验证：
- 响应状态码 201
- 文件被上传并创建文档记录
- 自动触发异步处理

**6.3 Get Document**
```
GET /api/v1/documents/{{document_id}}
```
验证：
- 返回文档的详细信息
- 包含处理状态和元数据

**6.4 List Library Documents**
```
GET /api/v1/documents/library?limit=20&offset=0&status=completed
```
验证：
- 返回属于 Library 的文档列表
- 支持状态过滤

**6.5 Delete Document（软删除）**
```
DELETE /api/v1/documents/{{document_id}}
```
行为：
- 删除 DB 记录 + 清除索引数据
- 保留文件系统目录 `data/documents/{{document_id}}/`

**6.6 Delete Library Document（可选硬删除）**
```
DELETE /api/v1/library/documents/{{document_id}}?force=true
```
行为：
- `force=false`（默认）：软删除（同上）
- `force=true`：硬删除（额外删除 `data/documents/{{document_id}}/`）

**6.7 Remove Document from Notebook（仅取消关联）**
```
DELETE /api/v1/notebooks/{{notebook_id}}/documents/{{document_id}}
```
行为：
- 仅删除 notebook-document 关联
- 不删除文档本体，不删除文件系统

---

## 已知问题和解决方案

### 问题 1：Document 上传返回 500 错误

**症状**：
```
POST /api/v1/documents/library
Status: 500 Internal Server Error

AttributeError: 'NoneType' object has no attribute 'Redis'
```

**原因**：
缺少 `redis` Python 包，导致 Celery 无法连接到 Redis。

**解决方案**：
```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装 redis 包
pip install redis

# 重启 API 服务器
# 停止当前运行的服务器（Ctrl+C）
# 重新启动
python -m uvicorn newbee_notebook.api.main:app --reload --port 8000
```

### 问题 2：数据库表不存在

**症状**：
```
relation "library" does not exist
relation "documents" does not exist
```

**原因**：
数据库容器在初始化脚本添加之前就已经创建，导致表未创建。

**解决方案**：
```bash
# 重置 Docker volumes 并重新创建容器
docker-compose down -v
docker-compose up -d

# 说明：down -v 只会清理 Docker volumes，不会删除宿主机 data/documents
# 如需清理孤儿文档目录，可执行：
make clean-orphans
# 或按 document_id 精确删除：
make clean-doc ID=<document_id>

# 等待容器启动（约 10 秒）
# 验证表已创建
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "\dt"
```

### 问题 3：Celery Worker 无法连接到 Redis

**症状**：
Celery worker 日志显示连接错误。

**解决方案**：
```bash
# 检查 Redis 容器状态
docker ps | grep redis

# 检查 .env 文件中的 Redis 配置
# REDIS_HOST=localhost
# REDIS_PORT=6379

# 重启 Celery worker
docker-compose restart celery-worker

# 查看 worker 日志
docker logs -f newbee-notebook-celery-worker
```

### 问题 4：API 服务器无法连接到 PostgreSQL

**症状**：
```
Connection refused
could not connect to server
```

**解决方案**：
```bash
# 检查 PostgreSQL 容器状态
docker ps | grep postgres

# 检查容器健康状态
docker exec newbee-notebook-postgres pg_isready -U postgres

# 验证 .env 配置
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=newbee_notebook_password
# POSTGRES_DB=newbee_notebook
```

---

## 高级功能

### 批量执行测试

Postman 支持运行整个集合或文件夹的所有请求：

1. 点击集合或文件夹旁边的 `...` 菜单
2. 选择 **Run folder**
3. 配置迭代次数和延迟
4. 点击 **Run** 执行

### 使用环境变量

创建多个环境用于不同的测试场景：

```json
// 本地环境
{
  "base_url": "http://localhost:8000"
}

// 开发环境
{
  "base_url": "https://dev.newbee-notebook.example.com"
}

// 生产环境
{
  "base_url": "https://api.newbee-notebook.example.com"
}
```

### 导出测试结果

1. 运行集合后，点击 **Export Results**
2. 选择导出格式（JSON 或 HTML）
3. 保存测试报告

### 命令行测试（Newman）

使用 Newman 在 CI/CD 流程中运行测试：

```bash
# 安装 Newman
npm install -g newman

# 运行测试集合
newman run postman_collection.json \
  --environment local.json \
  --reporters cli,json,html

# 查看结果
cat newman-run-report.html
```

---

## 故障排查

### 常见 HTTP 状态码

| 状态码 | 说明 | 可能原因 | 解决方案 |
|--------|------|----------|----------|
| 200 | 成功 | - | - |
| 201 | 创建成功 | - | - |
| 204 | 删除成功（无内容） | - | - |
| 400 | 请求参数错误 | 缺少必需字段、格式错误 | 检查请求体格式和必需字段 |
| 404 | 资源不存在 | ID 错误、资源已删除 | 验证 ID 是否正确 |
| 409 | 业务冲突 | 资源状态冲突（非删除端点常态） | 检查错误详情并调整请求 |
| 422 | 验证错误 | 字段值不符合要求 | 检查字段类型和约束 |
| 500 | 服务器内部错误 | 数据库连接、依赖服务 | 检查服务器日志 |

### 检查服务器日志

```bash
# 查看 API 服务器日志
# 在运行 uvicorn 的终端窗口查看输出

# 查看 Celery worker 日志
docker logs -f newbee-notebook-celery-worker

# 查看 PostgreSQL 日志
docker logs -f newbee-notebook-postgres

# 查看所有容器日志
docker-compose logs -f
```

### 验证数据库状态

```bash
# 连接到数据库
docker exec -it newbee-notebook-postgres psql -U postgres -d newbee_notebook

# 查看所有表
\dt

# 查看表结构
\d notebooks

# 查询数据
SELECT * FROM notebooks ORDER BY created_at DESC LIMIT 5;

# 退出
\q
```

### 清理测试数据

```bash
# 方式 1：删除特定记录（通过 Postman DELETE 请求）

# 方式 2：清空所有表（危险操作，仅用于测试环境）
docker exec newbee-notebook-postgres psql -U postgres -d newbee_notebook -c "
TRUNCATE TABLE messages CASCADE;
TRUNCATE TABLE references CASCADE;
TRUNCATE TABLE sessions CASCADE;
TRUNCATE TABLE notebook_document_refs CASCADE;
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE notebooks CASCADE;
TRUNCATE TABLE library CASCADE;
"

# 方式 3：完全重置数据库
docker-compose down -v
docker-compose up -d

# 可选：清理宿主机孤儿文档目录
make clean-orphans
```

---

## 测试检查清单

使用此清单确保完整测试覆盖：

- [ ] Health 模块
  - [ ] Basic health check
  - [ ] Readiness check
  - [ ] Liveness check
  - [ ] System info

- [ ] Library 模块
  - [ ] Get library
  - [ ] List library documents

- [ ] Notebooks 模块
  - [ ] Create notebook
  - [ ] List notebooks
  - [ ] Get notebook
  - [ ] Update notebook
  - [ ] Delete notebook

- [ ] Sessions 模块
  - [ ] Create session
  - [ ] List sessions
  - [ ] Get session
  - [ ] Get latest session
  - [ ] Get session messages
  - [ ] Delete session

- [ ] Chat 模块
  - [ ] Non-stream chat
  - [ ] Stream chat (SSE)
  - [ ] Cancel stream

- [ ] Documents 模块
  - [ ] Upload file to library
  - [ ] Get document
  - [ ] List documents
  - [ ] Delete document（soft）
  - [ ] Delete library document（force hard delete）
  - [ ] Remove document from notebook（unlink only）

- [ ] Integration 测试
  - [ ] Create notebook -> session -> chat (完整流程)
  - [ ] Upload document -> create reference (文档关联)
  - [ ] Multiple messages in session (会话连续性)

---

## 附录

### API 基础路径
```
http://localhost:8000/api/v1
```

### 支持的聊天模式
- `chat`: 自由对话模式
- `ask`: RAG 深度问答模式
- `explain`: 概念讲解模式
- `conclude`: 文档总结模式

### 文档状态
- `pending`: 等待处理
- `processing`: 正在处理
- `completed`: 处理完成
- `failed`: 处理失败

### 分页参数
- `limit`: 返回结果数量（默认 20，最大 100）
- `offset`: 跳过的记录数（默认 0）

### 相关文档
- API 文档：http://localhost:8000/docs
- ReDoc 文档：http://localhost:8000/redoc
- OpenAPI Schema：http://localhost:8000/openapi.json

---

如需技术支持或报告问题，请查看项目 README 或提交 Issue。
