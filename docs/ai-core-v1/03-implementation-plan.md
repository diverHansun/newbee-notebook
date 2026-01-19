# AI Core v1 实施计划

## 1. 实施策略

### 1.1 总体原则

- 增量迭代：每个阶段独立可验证
- 风险控制：保持现有系统可运行
- 功能优先：先实现核心价值
- 质量保证：每个阶段包含测试
- 开源优先：简化部署，开箱即用

### 1.2 迭代周期

每个阶段 1-2 周，共 4 个阶段，总计 8-9 周。

> **注意**：视频处理（YouTube、Bilibili）已从主要计划中移除，作为未来可选增强功能。

## 2. 阶段划分

### 阶段 0：架构准备（1 周）

**目标**
建立新架构的基础框架，不影响现有功能。

**任务清单**
1. 创建目录结构
   - 创建 api/ 目录和基础文件
   - 创建 application/ 目录
   - 创建 domain/ 目录
   - 创建 src/infrastructure/ 新子目录

2. 领域模型定义
   - 定义 Library 实体
   - 定义 Notebook 实体
   - 定义 Document 实体（支持 library_id/notebook_id）
   - 定义 Session 实体
   - 定义 Reference 实体
   - 定义仓储接口

3. 配置管理
   - 添加 configs/redis.yaml
   - 添加 configs/celery.yaml
   - 更新 src/common/config.py 支持新配置

4. 依赖安装
   - FastAPI、Uvicorn
   - Celery、Flower
   - redis-py
   - 其他必要依赖

5. 基础设施搭建
   - Docker Compose 添加 Redis 服务
   - 配置 Celery worker
   - 验证服务连接

**交付物**
- 完整的目录结构
- 领域模型定义
- 可运行的 Redis 和 Celery
- 更新的依赖文件

**验收标准**
- 所有新目录创建完成
- 领域实体和仓储接口定义完成
- Redis 和 Celery 可正常启动
- 现有 main.py 仍可正常运行

---

### 阶段 1：FastAPI 基础 + Notebook/Session 管理（2 周）

**目标**
提供基础的 HTTP API、Notebook/Session 管理和流式对话能力。

#### Sprint 1.1：Library 和 Notebook 管理（1 周）

**任务清单**
1. 数据库模型
   - 设计 library 表
   - 设计 notebooks 表
   - 设计 notebook_document_refs 表
   - 编写迁移脚本

2. 仓储实现
   - 实现 LibraryRepositoryImpl
   - 实现 NotebookRepositoryImpl

3. Library API
   - GET /api/v1/library - 获取 Library 信息
   - GET /api/v1/library/documents - 获取 Library 文档列表
   - DELETE /api/v1/library/documents/{id} - 删除文档（检查引用）

4. Notebook API
   - POST /api/v1/notebooks - 创建 Notebook
   - GET /api/v1/notebooks - 获取 Notebook 列表
   - GET /api/v1/notebooks/{id} - 获取 Notebook 详情
   - PATCH /api/v1/notebooks/{id} - 更新 Notebook
   - DELETE /api/v1/notebooks/{id} - 删除 Notebook（含专属文档）
   - POST /api/v1/notebooks/{id}/references - 从 Library 引用文档
   - DELETE /api/v1/notebooks/{id}/references/{ref_id} - 取消引用

5. 应用服务
   - 实现 library_service.py
   - 实现 notebook_service.py
   - 实现文档引用逻辑
   - 实现删除逻辑（Notebook 级联删除、Library 文档引用检查）

**交付物**
- Library 和 Notebook 管理 API
- 数据库表和迁移脚本
- 仓储实现

**验收标准**
- 可以通过 API 创建/管理 Notebook
- 可以从 Library 引用文档到 Notebook
- 删除逻辑正确执行

#### Sprint 1.2：Session 管理 + 流式对话（1 周）

**任务清单**
1. Session 数据库和仓储
   - 设计 sessions 表
   - 实现 SessionRepositoryImpl
   - 实现 session_count 上限检查（20 个）

2. Session API
   - POST /api/v1/notebooks/{id}/sessions - 创建 Session（含上限检查）
   - GET /api/v1/notebooks/{id}/sessions - 获取 Session 列表
   - GET /api/v1/notebooks/{id}/sessions/latest - 获取最近 Session
   - GET /api/v1/sessions/{id} - 获取 Session 详情
   - DELETE /api/v1/sessions/{id} - 删除 Session

3. Notebook 上下文
   - 实现 src/engine/notebook_context.py
   - 获取 Notebook 的文档列表（直接上传 + 引用）
   - 提供给 RAG 检索使用

4. 流式对话 API
   - POST /api/v1/notebooks/{id}/chat - 非流式对话
   - POST /api/v1/notebooks/{id}/chat/stream - SSE 流式对话
   - 对接 SessionManager 和 ModeSelector
   - RAG 检索限定在 Notebook 文档范围

5. 应用服务
   - 实现 session_service.py（含上限检查）
   - 实现 chat_service.py（Notebook 上下文）

6. 测试
   - 单元测试：Session 上限检查
   - 集成测试：SSE 端到端
   - 性能测试：首字节延迟

**交付物**
- Session 管理 API（含上限检查）
- 流式对话接口
- Notebook 上下文实现
- 测试用例

**验收标准**
- Session 达到 20 个时拒绝创建
- 打开 Notebook 可恢复最近 Session
- 流式输出首字节延迟 < 200ms
- RAG 检索只在 Notebook 文档范围内

---

### 阶段 2：文档处理管道（2-3 周）

**目标**
实现完整的文档上传、处理、存储流程，支持 Library 和 Notebook 双轨。

#### Sprint 2.1：基础文档上传（1 周）

**任务清单**
1. 数据库模型
   - 设计 documents 表（支持 library_id/notebook_id）
   - 设计 document_chunks 表
   - 编写迁移脚本

2. 仓储实现
   - 实现 DocumentRepositoryImpl
   - 支持按 Library/Notebook 查询

3. 文档上传接口
   - POST /api/v1/library/documents/upload - 上传到 Library
   - POST /api/v1/notebooks/{id}/documents/upload - 上传到 Notebook
   - 实现文件存储
   - 创建文档记录

4. Celery 任务基础
   - 配置 src/infrastructure/tasks/celery_app.py
   - 实现基础任务结构
   - 配置任务路由

**交付物**
- 文档表结构
- 双轨文档上传接口
- Celery 任务框架

**验收标准**
- 可以上传文档到 Library
- 可以上传文档到 Notebook
- 文档归属正确记录
- Celery 任务可正常调度

#### Sprint 2.2：内容提取与分块（1 周）

**任务清单**
1. 内容提取器
   - 实现 extractors/pdf_extractor.py（保留页码）
   - 实现 extractors/word_extractor.py
   - 实现 extractors/excel_extractor.py
   - 实现 factory.py 工厂模式

2. 智能分块
   - 实现 src/rag/text_splitter/smart_chunker.py
   - 保留章节信息
   - 保留页码信息
   - 保留位置信息

3. 文档处理任务
   - 实现 tasks/document_tasks.py
   - 内容提取 → 分块 → 保存
   - 错误处理和重试

4. 状态管理
   - 文档状态：processing、completed、failed
   - GET /api/v1/documents/{id}/status
   - 状态更新机制

**交付物**
- PDF、Word、Excel 提取器
- 智能分块器
- 文档处理任务

**验收标准**
- 正确提取文档内容
- 分块保留元数据（页码、章节）
- 处理状态正确更新

#### Sprint 2.3：嵌入与 Notebook 范围检索（1 周）

**任务清单**
1. 嵌入生成
   - 实现 tasks/embedding_tasks.py
   - 批量嵌入优化
   - 嵌入结果存储

2. Notebook 范围检索
   - 实现 src/rag/retrieval/notebook_retriever.py
   - 获取 Notebook 文档列表
   - 限定检索范围
   - 支持 vector、text、hybrid 模式

3. 搜索接口
   - POST /api/v1/notebooks/{id}/search - 在 Notebook 范围搜索
   - 返回带元数据的结果

4. Redis 缓存
   - 实现 src/infrastructure/redis/cache.py
   - 缓存搜索结果
   - 缓存文档内容

**交付物**
- 嵌入生成任务
- Notebook 范围检索器
- 搜索接口
- Redis 缓存

**验收标准**
- 文档可被搜索到
- 搜索只在 Notebook 文档范围内
- 搜索结果包含页码和章节
- 缓存命中率 > 50%

---

### 阶段 3：文档引用系统（2 周）

**目标**
实现类似 NotebookLM 的文档查看和引用功能。

#### Sprint 3.1：结构化文档内容（1 周）

**任务清单**
1. 文档结构解析
   - 实现 parsers/document_parser.py
   - 提取章节层级
   - 提取目录结构
   - 提取页面分隔

2. 文档内容接口
   - GET /api/v1/documents/{id}/content - 结构化内容
   - GET /api/v1/documents/{id}/chunks - 分块列表
   - GET /api/v1/documents/{id}/structure - 文档结构

3. 内容格式化
   - 返回章节树形结构
   - 包含页码和位置信息
   - 支持分页加载

**交付物**
- 文档结构解析器
- 结构化内容接口
- 文档大纲

**验收标准**
- 正确识别章节层级
- 返回完整文档结构
- 支持大文档分页

#### Sprint 3.2：引用系统（1 周）

**任务清单**
1. 引用实体和仓储
   - 实现 ReferenceRepositoryImpl
   - 设计 references 表
   - 编写迁移脚本

2. 引用接口
   - POST /api/v1/references - 创建引用
   - GET /api/v1/sessions/{id}/references - 获取 Session 引用
   - GET /api/v1/references/{id} - 获取引用详情

3. 引用追踪
   - 实现 src/rag/context/reference_tracker.py
   - AI 回答时自动记录引用
   - 引用来源追溯

4. Explain/Conclude 模式增强
   - 支持文档阅读器选中触发
   - 右键"讲解"调用 Explain 模式
   - 右键"总结"调用 Conclude 模式

**交付物**
- 引用管理系统
- 引用追踪
- Explain/Conclude 选中触发

**验收标准**
- 可以创建和查询引用
- AI 回答自动关联来源
- 选中文本可触发讲解/总结

---

### 阶段 4：优化与完善（1 周）

**目标**
性能优化、监控、文档完善。

#### Sprint 4.1：性能优化与监控（1 周）

**任务清单**
1. 数据库优化
   - 添加必要索引
   - 查询优化
   - 连接池配置

2. 缓存优化
   - Session 缓存策略
   - 搜索结果缓存
   - 文档内容缓存
   - 缓存失效机制

3. 批处理优化
   - 嵌入批量生成
   - 批量查询优化
   - 异步任务并发控制

4. 监控系统
   - 配置 Flower 监控 Celery
   - 添加关键指标日志
   - 错误追踪

5. 文档完善
   - API 文档（Swagger）
   - 开发指南
   - 部署文档
   - 故障排查指南

6. 测试补充
   - 单元测试覆盖率 > 70%
   - 集成测试覆盖核心流程
   - E2E 测试主要场景

**交付物**
- 性能优化报告
- Flower 监控面板
- 完整文档
- 测试报告

**验收标准**
- API 平均响应时间 < 500ms
- 支持 100 并发请求
- 10MB PDF 处理 < 30 秒
- 文档完整可用
- 测试覆盖率达标

---

## 3. 风险管理

### 3.1 技术风险

**风险点**
- 现有代码重构引入 Bug
- 新旧代码接口不兼容
- 性能下降

**应对策略**
- 充分的单元测试
- 保持向后兼容
- 性能基准测试

### 3.2 进度风险

**风险点**
- 任务估算不准确
- 依赖阻塞
- 需求变更

**应对策略**
- 每周评审进度
- 优先级动态调整
- 留有缓冲时间

### 3.3 质量风险

**风险点**
- 测试覆盖不足
- 边界情况遗漏
- 文档不同步

**应对策略**
- 测试驱动开发
- 代码审查
- 文档同步更新

## 4. 资源需求

### 4.1 人力资源

**后端开发**
- 至少 1 人全职
- 熟悉 Python、FastAPI、Celery
- 了解 LlamaIndex 和 RAG 概念

**测试**
- 可由开发兼任
- 需要编写自动化测试

### 4.2 基础设施

**开发环境**
- PostgreSQL + pgvector
- Elasticsearch
- Redis
- Celery worker

**测试环境**
- 与开发环境相同
- 独立的数据库实例

## 5. 质量保证

### 5.1 代码质量

**代码规范**
- 遵循 PEP 8
- 使用 Black 格式化
- 使用 Pylint 静态检查

**代码审查**
- 所有代码经过审查
- 遵循 SOLID 原则
- 消除重复代码

### 5.2 测试策略

**单元测试**
- 测试核心逻辑
- Mock 外部依赖
- 覆盖率 > 70%

**集成测试**
- 测试 API 接口
- 测试数据库交互
- 测试 Celery 任务

**E2E 测试**
- 测试完整用户流程
- 测试典型场景

### 5.3 文档质量

**代码文档**
- 所有公共接口有 docstring
- 复杂逻辑有注释

**架构文档**
- 保持与代码同步
- 记录设计决策
- 提供迁移指南

## 6. 发布策略

### 6.1 版本管理

**语义化版本**
- v1.0.0：第一个完整版本
- v1.1.0：新增功能
- v1.0.1：Bug 修复

**分支策略**
- main：稳定版本
- develop：开发分支
- feature/*：功能分支

### 6.2 部署策略

**本地部署**
- Docker Compose 一键启动
- 详细的部署文档
- 配置模板

**回滚方案**
- 保留上一个版本
- 数据库迁移可回滚
- 配置文件版本控制

## 7. 验收标准

### 7.1 功能完整性

- 支持 Library 和 Notebook 双轨文档管理
- 支持从 Library 引用文档到 Notebook
- 支持 PDF、Word、Excel 上传和处理
- 支持 YouTube、Bilibili 视频
- 支持文档查看和引用
- 支持流式对话
- 支持 4 种模式（Chat、Ask、Conclude、Explain）
- 支持 Explain/Conclude 选中触发
- Session 上限检查（20 个）
- 删除逻辑正确（Notebook 级联删除、Library 引用检查）

### 7.2 性能指标

- API 平均响应时间 < 500ms
- 流式输出首字节延迟 < 200ms
- 10MB PDF 处理 < 30 秒
- 支持 100 并发请求

### 7.3 质量指标

- 单元测试覆盖率 > 70%
- 核心流程有集成测试
- 主要场景有 E2E 测试
- 代码通过静态检查

### 7.4 文档完整性

- API 文档（Swagger）完整
- 架构文档与代码同步
- 部署文档可用
- 开发指南清晰

## 8. 里程碑

| 阶段 | 时间 | 关键交付 | 验收指标 |
|------|------|---------|---------|
| 阶段 0 | 第 1 周 | 架构基础 + 领域模型 | 目录结构完整，领域模型定义完成 |
| 阶段 1 | 第 2-3 周 | Notebook/Session + 流式对话 | Notebook 管理完整，Session 上限检查正常 |
| 阶段 2 | 第 4-6 周 | 双轨文档处理 | Library/Notebook 上传完整，Notebook 范围检索正常 |
| 阶段 3 | 第 7-8 周 | 引用系统 | 文档可查看，引用可追踪，选中触发正常 |
| 阶段 4 | 第 9 周 | 优化完善 | 性能达标，文档完整 |

总计：8-9 周

## 9. 后续规划

### 9.1 v1.1 版本 - 视频处理支持

> 从 AI Core v1 主要计划中移出，作为可选增强功能

**YouTube 支持**
- extractors/youtube_extractor.py（yt-dlp）
- 字幕提取和时间段分块
- URL 上传和异步处理

**Bilibili 支持**
- extractors/bilibili_extractor.py（bilibili-api-python）
- CC 字幕提取
- 音频转文本（Whisper，无字幕时）

**预估时间**：2 周

### 9.2 v1.2 版本 - 多用户支持

- 用户认证和权限
- 用户数据隔离
- 审计日志

### 9.3 v1.3 版本

- 图表和公式识别
- 多语言支持
- 更多文档格式

### 9.4 v2.0 版本

- 高级 RAG 策略
- 自定义 Agent
- 知识图谱集成

---

最后更新：2026-01-19
版本：v1.0.1
