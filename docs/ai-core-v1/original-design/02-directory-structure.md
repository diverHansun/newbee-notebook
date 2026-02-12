# AI Core v1 目录结构规划

## 1. 重构目标

在保留所有现有代码的前提下，通过新增和移动文件，建立清晰的分层架构，支持 Notebook 和 Library 双轨文档管理。

## 2. 重构原则

- 不删除任何现有文件
- 通过移动和新增建立新架构
- 保持向后兼容
- 渐进式迁移

## 3. 完整目录结构

```
MediMind-Agent/
├── api/                                    # 新增：API 层
│   ├── __init__.py
│   ├── main.py                            # FastAPI 应用入口
│   ├── dependencies.py                    # 依赖注入
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── cors.py                       # CORS 配置
│   │   ├── logging.py                    # 请求日志
│   │   └── error_handler.py              # 统一错误处理
│   ├── models/                           # API 数据传输对象
│   │   ├── __init__.py
│   │   ├── requests.py                   # 请求模型
│   │   └── responses.py                  # 响应模型
│   └── routers/                          # 路由模块
│       ├── __init__.py
│       ├── library.py                    # 独立文档库路由
│       ├── notebooks.py                  # Notebook 管理路由
│       ├── documents.py                  # 文档管理路由
│       ├── sessions.py                   # Session 管理路由
│       ├── chat.py                       # 对话路由
│       ├── search.py                     # 搜索路由
│       └── references.py                 # 引用路由
│
├── application/                           # 新增：应用服务层
│   ├── __init__.py
│   ├── services/                         # 应用服务
│   │   ├── __init__.py
│   │   ├── library_service.py            # 独立文档库服务
│   │   ├── notebook_service.py           # Notebook 管理服务
│   │   ├── document_service.py           # 文档管理服务
│   │   ├── session_service.py            # Session 管理服务
│   │   └── chat_service.py               # 对话服务
│   └── use_cases/                        # 用例（可选）
│       ├── __init__.py
│       ├── upload_to_library.py          # 上传到 Library
│       ├── upload_to_notebook.py         # 上传到 Notebook
│       ├── reference_document.py         # 引用文档到 Notebook
│       └── chat_in_notebook.py           # Notebook 内对话
│
├── domain/                                # 新增：领域模型层
│   ├── __init__.py
│   ├── entities/                         # 领域实体
│   │   ├── __init__.py
│   │   ├── base.py                      # 实体基类
│   │   ├── library.py                   # 独立文档库实体
│   │   ├── notebook.py                  # Notebook 实体
│   │   ├── document.py                  # 文档实体
│   │   ├── chunk.py                     # 文档块实体
│   │   ├── session.py                   # Session 实体
│   │   └── reference.py                 # 引用实体
│   ├── value_objects/                    # 值对象
│   │   ├── __init__.py
│   │   ├── document_type.py             # 文档类型枚举
│   │   ├── document_status.py           # 文档状态枚举
│   │   ├── chunk_metadata.py            # 块元数据
│   │   └── mode_type.py                 # 模式类型枚举
│   └── repositories/                     # 仓储接口
│       ├── __init__.py
│       ├── library_repository.py         # Library 仓储接口
│       ├── notebook_repository.py        # Notebook 仓储接口
│       ├── document_repository.py        # 文档仓储接口
│       ├── session_repository.py         # Session 仓储接口
│       └── reference_repository.py       # 引用仓储接口
│
├── src/                                   # 保留：现有核心逻辑
│   ├── __init__.py                       # 保留
│   ├── agent/                            # 保留：Agent 实现
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── function_agent.py
│   │   └── react_agent.py
│   ├── engine/                           # 保留并扩展：引擎和模式
│   │   ├── __init__.py
│   │   ├── session.py                   # Session 管理器
│   │   ├── selector.py                  # 模式选择器
│   │   ├── index_builder.py             # 索引构建
│   │   ├── notebook_context.py          # 新增：Notebook 上下文
│   │   └── modes/                       # 交互模式
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── chat_mode.py
│   │       ├── ask_mode.py
│   │       ├── conclude_mode.py
│   │       └── explain_mode.py
│   ├── rag/                              # 保留：RAG 核心
│   │   ├── __init__.py
│   │   ├── embeddings/                  # 嵌入模型
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── zhipu.py
│   │   │   ├── biobert.py
│   │   │   └── registry.py
│   │   ├── retrieval/                   # 检索系统
│   │   │   ├── __init__.py
│   │   │   ├── hybrid_retriever.py
│   │   │   ├── notebook_retriever.py   # 新增：Notebook 范围检索
│   │   │   └── fusion.py
│   │   ├── generation/                  # 生成引擎
│   │   │   ├── __init__.py
│   │   │   ├── query_engine.py
│   │   │   └── chat_engine.py
│   │   ├── document_loader/             # 文档加载
│   │   │   ├── __init__.py
│   │   │   └── loader.py
│   │   ├── text_splitter/               # 文本分块
│   │   │   ├── __init__.py
│   │   │   ├── splitter.py
│   │   │   └── smart_chunker.py         # 新增：智能分块
│   │   ├── postprocessors/              # 后处理器
│   │   │   ├── __init__.py
│   │   │   └── processors.py
│   │   └── context/                      # 新增：上下文管理
│   │       ├── __init__.py
│   │       ├── builder.py               # ContextBuilder
│   │       └── reference_tracker.py     # 引用追踪
│   ├── llm/                              # 保留：LLM 配置
│   │   ├── __init__.py
│   │   ├── zhipu.py
│   │   └── openai.py
│   ├── memory/                           # 保留：记忆管理
│   │   ├── __init__.py
│   │   └── chat_memory.py
│   ├── prompts/                          # 保留：Prompt 管理
│   │   ├── __init__.py
│   │   ├── chat.md
│   │   ├── ask.md
│   │   ├── conclude.md
│   │   └── explain.md
│   ├── tools/                            # 保留：工具集
│   │   ├── __init__.py
│   │   ├── tool_registry.py
│   │   ├── tavily.py
│   │   ├── es_search_tool.py
│   │   ├── zhipu_tools.py
│   │   └── time.py
│   ├── infrastructure/                   # 保留并扩展：基础设施
│   │   ├── __init__.py
│   │   ├── session/                     # Session 存储
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   └── store.py
│   │   ├── pgvector/                    # pgvector 存储
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── store.py
│   │   ├── elasticsearch/               # Elasticsearch
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── store.py
│   │   ├── redis/                       # 新增：Redis 缓存
│   │   │   ├── __init__.py
│   │   │   ├── cache.py                # 通用缓存
│   │   │   └── session_cache.py        # Session 缓存
│   │   ├── content_extraction/          # 新增：内容提取
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # 提取器接口
│   │   │   ├── factory.py              # 提取器工厂
│   │   │   ├── extractors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf_extractor.py    # PDF 提取
│   │   │   │   ├── word_extractor.py   # Word 提取
│   │   │   │   ├── excel_extractor.py  # Excel 提取
│   │   │   │   ├── youtube_extractor.py # YouTube
│   │   │   │   ├── bilibili_extractor.py # Bilibili
│   │   │   │   └── audio_extractor.py  # 音频转文本
│   │   │   └── parsers/
│   │   │       ├── __init__.py
│   │   │       ├── document_parser.py  # 文档结构解析
│   │   │       └── subtitle_parser.py  # 字幕解析
│   │   ├── persistence/                 # 新增：仓储实现
│   │   │   ├── __init__.py
│   │   │   ├── database.py             # 数据库连接
│   │   │   ├── models.py               # SQLAlchemy 模型
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       ├── library_repo_impl.py
│   │   │       ├── notebook_repo_impl.py
│   │   │       ├── document_repo_impl.py
│   │   │       ├── session_repo_impl.py
│   │   │       └── reference_repo_impl.py
│   │   ├── storage/                     # 新增：文件存储
│   │   │   ├── __init__.py
│   │   │   └── local_storage.py
│   │   └── tasks/                       # 新增：Celery 任务
│   │       ├── __init__.py
│   │       ├── celery_app.py           # Celery 配置
│   │       ├── document_tasks.py       # 文档处理任务
│   │       ├── embedding_tasks.py      # 嵌入任务
│   │       └── video_tasks.py          # 视频处理任务
│   └── common/                           # 保留：通用工具
│       ├── __init__.py
│       ├── config.py
│       └── utils/
│           ├── __init__.py
│           ├── text_utils.py
│           └── token_utils.py
│
├── configs/                               # 保留：配置文件
│   ├── llm.yaml
│   ├── embeddings.yaml
│   ├── modes.yaml
│   ├── memory.yaml
│   ├── rag.yaml
│   ├── storage.yaml
│   ├── zhipu_tools.yaml
│   ├── redis.yaml                        # 新增：Redis 配置
│   ├── celery.yaml                       # 新增：Celery 配置
│   ├── api.yaml                          # 新增：API 配置（端口、CORS 等）
│   ├── notebook.yaml                     # 新增：Notebook 配置（Session 上限等）
│   └── logging.yaml                      # 新增：日志配置
│
├── data/                                  # 保留：数据目录
│   └── documents/                        # 文档存储
│       ├── pdf/
│       ├── txt/
│       ├── csv/
│       ├── md/
│       ├── excel/
│       └── word/
│
├── scripts/                               # 保留并扩展：工具脚本
│   ├── rebuild_pgvector.py
│   ├── rebuild_es.py
│   └── migrate_db.py                     # 新增：数据库迁移
│
├── tests/                                 # 保留并扩展：测试
│   ├── __init__.py
│   ├── unit/                             # 单元测试
│   │   ├── test_rag/
│   │   ├── test_agents/
│   │   ├── test_extractors/
│   │   ├── test_notebook/               # 新增
│   │   └── test_library/                # 新增
│   ├── integration/                      # 集成测试
│   │   ├── test_api/
│   │   └── test_tasks/
│   └── e2e/                              # 端到端测试
│       └── test_workflows/
│
├── docs/                                  # 文档
│   ├── ai-core-v1/                       # AI Core v1 规划
│   │   ├── README.md
│   │   ├── 01-architecture.md
│   │   ├── 02-directory-structure.md
│   │   ├── 03-implementation-plan.md
│   │   ├── 04-api-design.md
│   │   ├── 05-document-reference-system.md
│   │   └── 06-notebook-library-system.md  # 新增
│   └── guides/                           # 开发指南
│
├── main.py                                # 保留：CLI 入口
├── docker-compose.yml                     # 保留：Docker 配置
├── requirements.txt                       # 保留：依赖
├── README.md                              # 保留：项目说明
├── medimind-guide.md                      # 保留：技术指南
└── coding_guide.md                        # 保留：编码规范
```

## 4. 模块职责说明

### 4.1 API 层（新增）

**api/**
- 所有 HTTP 相关逻辑
- 不调用基础设施层，只调用应用服务层
- 职责：请求验证、响应序列化、错误处理

**路由模块**
- library.py：Library CRUD、文档上传到 Library
- notebooks.py：Notebook CRUD、引用管理
- documents.py：文档状态查询、内容获取
- sessions.py：Session CRUD（含 20 个上限检查）
- chat.py：4 种模式对话
- references.py：引用管理

### 4.2 应用服务层（新增）

**application/**
- 编排核心逻辑层和基础设施层
- 管理事务边界
- 实现具体用例

**服务模块**
- library_service.py：Library 管理、文档删除检查
- notebook_service.py：Notebook 管理、专属文档删除
- document_service.py：文档处理、状态管理
- session_service.py：Session 管理、上限检查
- chat_service.py：对话编排、模式选择

### 4.3 领域模型层（新增）

**domain/**
- 定义业务实体和值对象
- 仓储抽象接口
- 不依赖任何基础设施

**核心实体**
- Library：独立文档库，全局唯一
- Notebook：笔记本，可创建多个
- Document：文档，可属于 Library 或 Notebook
- Session：对话会话，属于 Notebook
- Reference：引用，关联 Session 和 Chunk

### 4.4 核心逻辑层（保留）

**src/agent/**
- Agent 实现保持不变

**src/engine/**
- 会话管理和模式选择保持不变
- 新增 notebook_context.py：Notebook 上下文管理

**src/rag/**
- 所有 RAG 组件保持不变
- 新增 context/：上下文管理
- 新增 smart_chunker：智能分块
- 新增 notebook_retriever：Notebook 范围检索

**src/prompts/**
- Markdown 文件管理保持不变

**src/tools/**
- 工具注册和现有工具保持不变

### 4.5 基础设施层（保留并扩展）

**现有模块**
- src/infrastructure/session/：Session 存储
- src/infrastructure/pgvector/：pgvector 存储
- src/infrastructure/elasticsearch/：Elasticsearch 存储

**新增模块**
- src/infrastructure/redis/：Redis 缓存
- src/infrastructure/content_extraction/：内容提取器
- src/infrastructure/persistence/：SQLAlchemy 仓储实现
- src/infrastructure/storage/：文件存储
- src/infrastructure/tasks/：Celery 任务

## 5. 模块间依赖关系

### 5.1 依赖图

```
api/
  ↓ 调用
application/
  ↓ 调用                    ↓ 调用
src/（核心逻辑）           domain/（抽象）
  ↑ 实现接口                 ↑ 实现接口
src/infrastructure/
```

### 5.2 导入规则

**禁止的导入**
- src/ 不能导入 api/
- src/ 不能导入 application/
- domain/ 不能导入 src/infrastructure/
- 核心逻辑不能导入具体实现

**允许的导入**
- api/ 可以导入 application/
- application/ 可以导入 src/ 和 domain/
- src/infrastructure/ 可以导入 domain/（实现接口）
- 所有层都可以导入 src/common/（共享工具）

## 6. 文件迁移计划

### 6.1 阶段一：新增目录和文件

创建新的目录结构，不移动现有文件：
- 创建 api/
- 创建 application/
- 创建 domain/
- 创建 src/infrastructure/ 下的新目录

### 6.2 阶段二：新功能使用新架构

所有新功能在新目录中实现：
- Notebook 和 Library 在 domain/ 中定义
- 内容提取器在 src/infrastructure/content_extraction/
- API 接口在 api/

### 6.3 阶段三：渐进式重构

逐步将现有功能迁移到新架构：
- 保持旧代码可运行
- 新旧代码共存
- 逐个模块验证和替换

## 7. 配置文件管理

### 7.1 新增配置

**configs/redis.yaml**
- Redis 连接配置
- 缓存策略配置

**configs/celery.yaml**
- Celery broker 配置
- 任务路由配置
- 重试策略配置

### 7.2 配置加载

保持现有的配置加载机制：
- 使用 src/common/config.py
- 支持环境变量覆盖
- YAML 文件优先

## 8. 数据库模型设计

### 8.1 新增表

**library 表**
- id, created_at, updated_at

**notebooks 表**
- id, title, description
- session_count, document_count
- created_at, updated_at

**documents 表**
- id, library_id(nullable), notebook_id(nullable)
- title, content_type, file_path, url
- status, page_count, chunk_count
- created_at, updated_at

**notebook_document_refs 表**
- id, notebook_id, document_id
- created_at

**sessions 表**
- id, notebook_id, title
- message_count, created_at, updated_at

**document_chunks 表**
- id, document_id, content, embedding
- page_number, section_title, section_level
- start_position, end_position, timestamp
- created_at

**references 表**
- id, session_id, message_id
- chunk_id, document_id
- quoted_text, context
- created_at

### 8.2 现有表保留

- chat_sessions（逐步迁移到 sessions）
- chat_messages
- 其他现有表保持不变

## 9. 导入路径约定

### 9.1 绝对导入

所有导入使用绝对路径：

从 api 层导入：
```python
from application.services.chat_service import ChatService
from application.services.notebook_service import NotebookService
```

从应用层导入核心逻辑：
```python
from src.engine.session import SessionManager
from src.rag.retrieval.hybrid_retriever import HybridRetriever
```

从基础设施导入：
```python
from src.infrastructure.redis.cache import RedisCache
from src.infrastructure.persistence.repositories.notebook_repo_impl import NotebookRepositoryImpl
```

### 9.2 相对导入

仅在同一目录内使用相对导入：
```python
from .base import BaseExtractor
```

## 10. 命名约定

### 10.1 目录命名

- 小写字母
- 使用下划线分隔（snake_case）
- 复数形式表示集合（extractors、repositories）

### 10.2 文件命名

- 小写字母
- 使用下划线分隔（snake_case）
- 名词或动宾结构（document_parser、upload_to_notebook）

### 10.3 类命名

- 大驼峰（PascalCase）
- 清晰表达职责（NotebookService、LibraryRepository）

### 10.4 函数命名

- 小写字母加下划线（snake_case）
- 动词开头（create_notebook、get_documents）

## 11. 兼容性策略

### 11.1 保持向后兼容

- main.py 继续可用（CLI 入口）
- 现有 CLI 命令保持不变
- 配置文件格式不变

### 11.2 弃用策略

- 使用 @deprecated 装饰器标记
- 提供迁移指南
- 保留至少两个版本

## 12. 文档同步

### 12.1 代码文档

- 所有公共接口添加 docstring
- 复杂逻辑添加注释
- 保持文档与代码同步

### 12.2 架构文档

- 每次重大变更更新架构文档
- 维护变更日志
- 提供迁移指南
