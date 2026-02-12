# AI Core v1 架构设计

## 1. 架构概述

### 1.1 项目定位

MediMind Agent 是一个开源的、类 NotebookLM 的智能文档助手，支持多格式文档处理、智能问答和内容引用追溯。

**核心特点**：
- 开源优先，本地部署
- 单用户模式，开箱即用
- Notebook + Library 双轨文档管理
- 4 种交互模式（Chat、Ask、Explain、Conclude）
- 文档引用系统，支持溯源

### 1.2 设计目标

本次重构旨在构建一个清晰的分层架构，支持以下核心能力：
- 多格式文档处理（PDF、Word、Excel、视频）
- Notebook 和 Library 文档管理
- 文档内容查看与引用
- 智能对话与问答
- 异步任务处理
- 可扩展的提示词管理

### 1.3 架构原则

严格遵循以下软件工程原则：

**SOLID 原则**
- 单一职责（SRP）：每个模块只负责一个明确的功能
- 开放封闭（OCP）：通过抽象和工厂模式支持扩展
- 里氏替换（LSP）：接口实现可互相替换
- 接口隔离（ISP）：接口专注且精简
- 依赖倒置（DIP）：依赖抽象而非具体实现

**其他原则**
- KISS：保持简洁，避免过度设计
- YAGNI：只实现当前需要的功能
- DRY：消除重复，提升复用性

### 1.4 分层架构

系统采用四层架构设计：

**API 层**
- 职责：HTTP 请求处理、参数验证、响应序列化
- 技术：FastAPI、Pydantic
- 不包含：业务逻辑、数据访问

**应用服务层**
- 职责：用例编排、事务边界管理
- 技术：纯 Python 业务逻辑
- 不包含：AI 推理细节、数据库操作

**核心逻辑层**
- 职责：AI 核心能力（RAG、Agent、Prompt）
- 技术：LlamaIndex、自定义 AI 逻辑
- 不包含：HTTP 处理、数据库细节

**基础设施层**
- 职责：技术实现（数据库、缓存、外部 API）
- 技术：PostgreSQL、Redis、Celery、第三方库
- 不包含：业务决策

### 1.5 依赖方向

```
API 层 → 应用服务层 → 核心逻辑层
                         ↑
      基础设施层 ─────────┘（依赖抽象接口）
```

核心原则：
- 外层依赖内层
- 内层不依赖外层
- 基础设施层依赖核心层的抽象接口

## 2. 技术栈

### 2.1 已确定的技术选型

**AI 框架**
- RAG 框架：LlamaIndex（保持不变）
- Agent 框架：LlamaIndex（保持不变）
- Prompt 管理：Markdown 文件（保持不变）

**数据存储**
- 关系数据：PostgreSQL
- 向量存储：pgvector
- 全文搜索：Elasticsearch
- 缓存：Redis

**异步任务**
- 任务队列：Celery + Redis
- 监控工具：Flower

**API 层**
- Web 框架：FastAPI
- 流式输出：Server-Sent Events

### 2.2 内容处理工具

**文档处理**
- PDF：PyMuPDF（保留页码、章节信息）
- Word：python-docx
- Excel：openpyxl/pandas
- 其他：保持现有 data/documents 下支持的格式

**视频处理**
- YouTube：yt-dlp（字幕提取）
- Bilibili：bilibili-api-python（开放平台）
- 音频转文本：需从视频提取音频后处理

## 3. 核心业务概念

### 3.1 Notebook 和 Library 模型

系统采用双轨文档管理机制：

**Library（独立文档库）**
- 用户的文档仓库，集中管理所有资料
- 用户上传的文档默认存放在 Library
- 文档可以被多个 Notebook 引用
- 删除时需检查引用关系

**Notebook（笔记本）**
- 用户的工作空间，围绕特定主题组织资料
- 可以从 Library 引用文档
- 也可以直接上传专属文档（不进入 Library）
- 每个 Notebook 独立管理 Session

**文档归属规则**
- 用户通过 Library 页面上传 → 存入 Library
- 用户通过 Notebook 内部上传 → 只属于该 Notebook
- 从 Library 引用到 Notebook → 软引用，不复制

```
文档管理结构示意：

Library (文档仓库)
├── doc-A.pdf        ──────┐
├── doc-B.docx       ──────┼──→ 可被多个 Notebook 引用
└── video-url-1      ──────┘

Notebook 1
├── [引用] doc-A.pdf       ← 从 Library 引用
├── [引用] video-url-1     ← 从 Library 引用
├── notebook-only-doc.pdf  ← 只属于此 Notebook
└── Sessions (max 20)

Notebook 2
├── [引用] doc-A.pdf       ← 同一文档可被多个 Notebook 引用
├── [引用] doc-B.docx
└── Sessions (max 20)
```

### 3.2 Session 管理

**Session 规则**
- 每个 Notebook 最多 20 个 Session
- 达到上限后拒绝创建，提示删除旧 Session 或新建 Notebook
- 打开 Notebook 时默认恢复上一个 Session
- 用户可以选择创建新 Session

**Session 生命周期**
```
打开 Notebook
    ↓
检查是否有 Session
    ↓
有 → 恢复最近的 Session
无 → 创建新 Session
    ↓
用户对话（4种模式）
    ↓
消息自动保存
    ↓
关闭 Notebook（Session 保留）
```

### 3.3 四种交互模式

**在 Notebook 上下文中运行**

| 模式 | 说明 | RAG 检索 | 触发方式 |
|------|------|----------|----------|
| **Chat** | 自由对话 + 工具调用 | 可选 | 对话框输入 |
| **Ask** | 深度问答 + 混合检索 | Notebook 文档范围 | 对话框输入 |
| **Explain** | 概念讲解 | 相关上下文 | 文档阅读器选中 → 右键"讲解" |
| **Conclude** | 内容总结 | 选中内容 | 文档阅读器选中 → 右键"总结" |

**RAG 检索范围**
- 只检索当前 Notebook 内的文档
- 包括：直接上传的文档 + 从 Library 引用的文档
- 不包括：Library 中未引用的文档、其他 Notebook 的文档

## 4. 核心模块设计

### 4.1 现有模块保留方案

所有现有模块完整保留，仅调整位置和命名：

**src/rag/** → 完整保留
- embeddings/：嵌入模型系统
- retrieval/：混合检索系统
- generation/：查询和对话引擎
- document_loader/：文档加载器
- text_splitter/：文本分块
- postprocessors/：后处理器

**src/agent/** → 完整保留
- base.py：Agent 基类
- function_agent.py：Chat 模式
- react_agent.py：Ask 模式

**src/engine/** → 完整保留并扩展
- modes/：四种模式（chat、ask、conclude、explain）
- session.py：会话管理
- selector.py：模式选择器
- index_builder.py：索引构建

**src/infrastructure/** → 完整保留并扩展
- session/：会话存储
- pgvector/：向量存储
- elasticsearch/：全文搜索

**src/tools/** → 完整保留
- 工具注册表和现有工具

### 4.2 新增模块

**API 层（新增）**
- api/：FastAPI 路由和中间件
- 不修改现有 src/ 代码

**应用服务层（新增）**
- application/：用例和服务编排
- 封装现有 src/ 的调用

**领域模型层（新增）**
- domain/：实体、值对象、仓储接口
- 核心实体：Notebook、Library、Document、Session、Reference

**基础设施扩展（新增）**
- infrastructure/content_extraction/：内容提取器
- infrastructure/redis/：Redis 缓存
- infrastructure/tasks/：Celery 任务
- infrastructure/persistence/：仓储实现

## 5. 关键功能设计

### 5.1 文档引用系统

这是类似 NotebookLM 的核心差异化功能。

**功能描述**
- 左侧显示文档结构化内容（章节、页码）
- 用户选中文本可引用到对话
- AI 回答引用来源，点击可跳转

**技术实现**
- 文档分块时保留元数据（章节、页码、位置）
- 引用实体记录引用关系
- API 提供结构化文档内容和引用接口

### 5.2 智能分块策略

**现有能力**
- 使用 SentenceSplitter，固定 chunk_size

**增强方案**
- PDF：按页面或章节分块
- Word/Excel：按自然段落或表格分块
- 视频字幕：按时间段分块
- 保留元数据：页码、章节标题、时间戳

### 5.3 上下文构建器

**增强方案**
- 实现 ContextBuilder 类
- 支持优先级排序
- 智能截断以适应上下文窗口
- 支持文档、洞察、历史消息的融合
- 限定在 Notebook 文档范围内

### 5.4 模式扩展

**现有模式**
- Chat：自由对话 + 工具调用
- Ask：深度问答 + 混合检索
- Conclude：文档总结
- Explain：概念讲解

**增强**
- 所有模式在 Notebook 上下文中运行
- RAG 检索限定在 Notebook 文档范围
- Explain/Conclude 支持文档阅读器选中触发

## 6. 数据流设计

### 6.1 文档上传流程

**上传到 Library**
```
用户上传 → API 接收 → 创建 Document 记录（library_id）
                                ↓
                         提交 Celery 任务
                                ↓
                 内容提取 → 结构解析 → 分块 → 嵌入 → 存储
                                ↓
                         更新文档状态
```

**上传到 Notebook**
```
用户在 Notebook 内上传 → API 接收 → 创建 Document 记录（notebook_id）
                                          ↓
                                   提交 Celery 任务
                                          ↓
                           内容提取 → 结构解析 → 分块 → 嵌入 → 存储
                                          ↓
                                   更新文档状态
```

### 6.2 对话流程

```
用户消息 → API 验证 → 获取 Notebook 上下文
                            ↓
                      获取 Notebook 文档列表（直接上传 + 引用）
                            ↓
                      SessionManager → ModeSelector
                            ↓
                      选择模式（Chat/Ask/Explain/Conclude）
                            ↓
                      ContextBuilder（限定 Notebook 文档范围）
                            ↓
                      Agent 处理 → LLM 生成
                            ↓
                      流式返回（SSE）
```

### 6.3 引用查询流程

```
获取文档内容 → API 请求 → 验证文档属于当前 Notebook
                              ↓
                        查询文档分块
                              ↓
                        返回结构化内容（章节、页码）
                              ↓
                        前端渲染可引用视图
```

## 7. 删除逻辑设计

### 7.1 删除 Notebook

```
用户请求删除 Notebook
    ↓
删除 Notebook 专属文档（直接上传的文档）
    ↓
删除 Notebook 引用关系（不删除 Library 文档）
    ↓
删除所有 Session 和消息
    ↓
删除 Notebook 记录
```

### 7.2 删除 Library 文档

```
用户请求删除 Library 文档
    ↓
检查是否被 Notebook 引用
    ↓
有引用 → 提示用户"该文档被 X 个 Notebook 引用，确认删除？"
    ↓
用户确认 → 自动解除所有引用关系 → 删除文档
用户取消 → 保留文档
```

## 8. 接口设计原则

### 8.1 RESTful 风格

- 资源导向的 URL 设计
- 使用标准 HTTP 方法（GET、POST、PATCH、DELETE）
- 版本控制：/api/v1/

### 8.2 响应格式

统一的响应结构：
- 成功：返回数据对象或列表
- 失败：返回错误代码和消息
- 流式：使用 SSE 格式

### 8.3 分页与过滤

- 列表接口支持分页（limit、offset）
- 支持基础过滤和排序
- 遵循 YAGNI，只实现必要的查询

## 9. 安全性考虑

### 9.1 当前阶段（开源版）

重点：功能实现，单用户模式
- 基础参数验证
- SQL 注入防护（使用 ORM）
- 文件上传限制（大小、类型）
- 本地部署，不暴露公网

### 9.2 未来扩展

如需多用户支持，可增加：
- JWT 认证
- 用户隔离
- 权限控制
- 审计日志

## 10. 性能优化策略

### 10.1 缓存策略

**Redis 缓存**
- 会话状态缓存
- 向量搜索结果缓存
- 频繁访问的文档内容缓存

**缓存失效**
- 文档更新时清除相关缓存
- 设置合理的过期时间

### 10.2 异步处理

**适用场景**
- 文档内容提取（耗时）
- 嵌入生成（批量）
- 视频下载和处理

**不适用场景**
- 对话生成（需要实时反馈）
- 简单查询

### 10.3 数据库优化

**索引策略**
- notebook_id、document_id 等外键
- created_at 时间戳
- 向量索引（pgvector）

**查询优化**
- 使用连接池
- 避免 N+1 查询
- 批量操作

## 11. 可扩展性设计

### 11.1 内容提取器扩展

使用工厂模式和策略模式：
- 新增提取器无需修改现有代码
- 通过配置注册新的提取器
- 符合开放封闭原则

### 11.2 模型提供商扩展

保持现有的 embeddings registry 机制：
- 通过装饰器注册新模型
- 动态加载和切换
- 配置驱动

### 11.3 模式扩展

基于现有的 BaseMode 和 ModeSelector：
- 新模式继承 BaseMode
- 在 ModeSelector 中注册
- 符合里氏替换原则

## 12. 测试策略

### 12.1 测试分层

**单元测试**
- 核心逻辑层：RAG、Agent 逻辑
- 领域模型：实体和值对象
- 工具函数：text_utils、token_utils

**集成测试**
- API 层：端到端请求响应
- 数据库层：仓储实现
- Celery 任务：异步处理流程

**E2E 测试**
- 完整用户流程
- 文档上传到对话的全链路

### 12.2 测试优先级

第一阶段重点：
- 核心 API 接口
- 文档处理流程
- 对话生成逻辑

## 13. 监控与日志

### 13.1 日志策略

**日志级别**
- ERROR：系统错误、异常
- WARNING：性能问题、降级
- INFO：关键业务操作
- DEBUG：详细调试信息

**日志内容**
- 请求 ID 追踪
- 业务操作记录
- 性能指标（响应时间）

### 13.2 监控指标

**系统指标**
- API 响应时间
- Celery 任务队列长度
- 数据库连接池状态
- Redis 缓存命中率

**业务指标**
- 文档处理成功率
- 对话响应质量
- 引用使用频率

## 14. 迁移策略

### 14.1 数据库迁移策略

采用 **全新开始** 策略：

- 现有 `chat_sessions`、`chat_messages` 表保留但不再使用
- 新建 `notebooks`、`sessions`、`documents` 等表
- 提供可选迁移脚本供有需要的用户

**理由**：
- 开源项目，用户数据量通常不大
- 新旧表结构差异较大
- 简化开发，专注新功能

### 14.2 向量存储策略

采用 **使用 LlamaIndex 表** 策略：

- 继续使用 LlamaIndex 自动创建的 `data_documents_*` 表
- 不单独创建 `document_chunks` 表
- 通过 `metadata_` JSON 字段存储扩展信息（document_id、page_number 等）
- 只维护 `documents` 表管理文档级别信息

**优点**：
- 复用 LlamaIndex 的索引构建和检索优化
- 减少数据同步问题
- 支持按配置切换嵌入模型表

### 14.3 风险控制

- 充分的单元测试覆盖
- 功能开关控制新特性
- 回滚方案准备

## 15. 总结

本架构设计遵循软件工程最佳实践，在保持现有功能的基础上，为系统提供清晰的分层结构和扩展能力。重点关注：

1. 清晰的职责分离
2. Notebook + Library 双轨文档管理
3. 4 种交互模式在 Notebook 上下文中运行
4. 可测试性和可维护性
5. 符合 SOLID 原则
6. 开源优先，简化部署
