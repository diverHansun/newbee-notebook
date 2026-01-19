# AI Core v1 规划文档

## 文档概述

本目录包含 MediMind Agent AI Core v1 的完整架构设计和实施规划文档。

**项目定位**：开源的、类 NotebookLM 的智能文档助手，支持多格式文档处理、智能问答和内容引用追溯。

**核心特点**：
- 开源优先，本地部署
- 单用户模式，开箱即用
- Notebook + Library 双轨文档管理
- 4 种交互模式（Chat、Ask、Explain、Conclude）
- 文档引用系统，支持溯源

所有文档基于软件工程最佳实践，遵循 SOLID、DRY、KISS、YAGNI 原则。

## 文档列表

### 01. 架构设计
文件：[01-architecture.md](01-architecture.md)

**内容摘要**
- 整体架构设计
- 四层架构模型
- 技术栈选型
- Notebook + Library 核心概念
- 核心模块设计
- 数据流设计
- 性能和安全考虑

**适用读者**
- 技术负责人
- 架构师
- 全体开发团队

---

### 02. 目录结构规划
文件：[02-directory-structure.md](02-directory-structure.md)

**内容摘要**
- 完整目录结构设计
- 模块职责划分
- 文件迁移计划
- 导入路径约定
- 命名规范

**适用读者**
- 开发工程师
- 代码审查者

---

### 03. 实施计划
文件：[03-implementation-plan.md](03-implementation-plan.md)

**内容摘要**
- 5 个阶段的详细实施计划
- 每个阶段的任务清单
- 交付物和验收标准
- 风险管理策略
- 质量保证措施
- 里程碑规划

**适用读者**
- 项目经理
- 开发工程师
- 测试工程师

---

### 04. API 接口设计
文件：[04-api-design.md](04-api-design.md)

**内容摘要**
- Library 管理 API
- Notebook 管理 API
- Session 管理 API（含上限检查）
- 对话 API（4 种模式）
- 文档内容 API
- 引用管理 API
- 流式输出设计
- 错误处理规范

**适用读者**
- 前端工程师
- 后端工程师
- API 使用者

---

### 05. 文档引用系统设计
文件：[05-document-reference-system.md](05-document-reference-system.md)

**内容摘要**
- 核心差异化功能设计
- 文档结构提取方案
- 智能分块策略
- 引用追踪机制
- Explain/Conclude 选中触发
- 前后端交互设计

**适用读者**
- 全栈工程师
- 产品经理
- UX 设计师

---

### 06. Notebook 和 Library 系统设计
文件：[06-notebook-library-system.md](06-notebook-library-system.md)

**内容摘要**
- 双轨文档管理机制
- 文档归属规则
- Session 管理（20 个上限）
- RAG 检索范围限定
- 核心业务流程
- 数据库表设计
- 仓储接口设计

**适用读者**
- 后端工程师
- 数据库设计者
- 系统架构师

---

### 07. 技术决策记录
文件：[07-technical-decisions.md](07-technical-decisions.md)

**内容摘要**
- 设计决策记录（ADR 格式）
- 数据库迁移策略
- 嵌入模型策略
- 检索过滤方案
- 历史消息压缩策略
- 基础设施配置决策

**适用读者**
- 全体开发团队
- 技术负责人

---

### 08. 错误处理设计
文件：[08-error-handling.md](08-error-handling.md)

**内容摘要**
- 异常层次结构
- 错误码规范
- 错误响应格式
- FastAPI 异常处理器
- 使用示例

**适用读者**
- 后端工程师
- 前端工程师

---

### 09. 日志与监控设计
文件：[09-logging-monitoring.md](09-logging-monitoring.md)

**内容摘要**
- 结构化日志策略
- 日志级别规范
- 业务日志规范
- 监控指标
- 健康检查接口
- Celery 任务监控

**适用读者**
- 运维工程师
- 后端工程师

---

## 技术栈总览

### AI 框架
- RAG：LlamaIndex
- Agent：LlamaIndex
- Prompt：Markdown 文件

### 后端
- API：FastAPI
- 异步任务：Celery + Redis
- 流式输出：Server-Sent Events

### 数据层
- 关系数据：PostgreSQL
- 向量存储：pgvector
- 全文搜索：Elasticsearch
- 缓存：Redis

### 内容处理
- PDF：PyMuPDF
- Word：python-docx
- Excel：openpyxl
- YouTube：yt-dlp
- Bilibili：bilibili-api-python

## 实施时间线

| 阶段 | 时间 | 核心交付 |
|------|------|---------|
| 阶段 0 | 第 1 周 | 架构基础 + 领域模型 |
| 阶段 1 | 第 2-3 周 | Notebook/Session + 流式对话 |
| 阶段 2 | 第 4-6 周 | 双轨文档处理 |
| 阶段 3 | 第 7-8 周 | 文档引用系统 |
| 阶段 4 | 第 9 周 | 优化与完善 |

总计：8-9 周

> **注意**：视频处理支持（YouTube、Bilibili）已移至后续版本（v1.1）作为可选增强功能。

## 核心功能列表

### 已有功能（保留）
- 4 种对话模式（Chat、Ask、Conclude、Explain）
- 混合检索（pgvector + Elasticsearch + RRF）
- 多嵌入模型支持（Zhipu、BioBERT）
- 会话管理和持久化
- 工具调用（Tavily、ES 搜索等）

### 新增功能
- **Notebook 管理**：创建、编辑、删除 Notebook
- **Library 管理**：独立文档库，集中管理资料
- **双轨文档上传**：上传到 Library 或直接上传到 Notebook
- **文档引用**：从 Library 引用文档到 Notebook
- **Session 管理**：每个 Notebook 最多 20 个 Session
- **Notebook 范围检索**：RAG 只检索当前 Notebook 的文档
- **RESTful API 接口**
- **流式对话输出（SSE）**
- **文档上传和处理**（PDF、Word、Excel、视频）
- **文档结构化展示**
- **文档内容引用**
- **引用来源追溯**
- **Explain/Conclude 选中触发**
- **异步任务处理**
- **Redis 缓存**
- **性能监控（Flower）**

## 核心业务规则

### Notebook 规则
- 数量不限
- 删除时级联删除专属文档和所有 Session
- 可以从 Library 引用文档
- 可以直接上传专属文档

### Session 规则
- 每个 Notebook 最多 20 个 Session
- 达到上限后拒绝创建，提示删除旧 Session 或新建 Notebook
- 打开 Notebook 时默认恢复最近 Session

### 文档归属规则
- 通过 Library 页面上传 → 属于 Library
- 通过 Notebook 内部上传 → 属于 Notebook（专属文档）
- 从 Library 引用 → 软引用，不复制

### 删除规则
- 删除 Notebook → 专属文档一并删除
- 删除 Library 文档 → 提示用户，自动解除引用后删除

### RAG 检索规则
- 只检索当前 Notebook 的文档
- 包括：专属文档 + 从 Library 引用的文档

## 设计原则

本项目严格遵循以下软件工程原则：

### SOLID 原则
- **S**ingle Responsibility：单一职责
- **O**pen/Closed：开放封闭
- **L**iskov Substitution：里氏替换
- **I**nterface Segregation：接口隔离
- **D**ependency Inversion：依赖倒置

### 其他原则
- **KISS**：保持简洁
- **YAGNI**：只实现需要的功能
- **DRY**：消除重复

## 架构层次

```
┌─────────────────────────────────────┐
│         API 层（FastAPI）            │  HTTP 请求处理
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      应用服务层（业务编排）           │  Notebook、Session、Document
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   核心逻辑层（AI + RAG）              │  LlamaIndex + 4种模式
└─────────────────────────────────────┘
              ↑
┌─────────────────────────────────────┐
│   基础设施层（数据库、缓存等）         │  PostgreSQL、Redis、ES
└─────────────────────────────────────┘
```

## 关键设计决策

### 1. 开源优先
- 单用户模式，简化部署
- 无登录认证
- Docker Compose 一键启动

### 2. 保留现有代码
- 所有 src/ 下的代码完整保留
- 仅调整位置和新增功能
- 保持向后兼容

### 3. LlamaIndex 为主
- RAG 场景使用 LlamaIndex
- 保持现有 Agent 实现
- Prompt 管理使用 Markdown

### 4. Notebook + Library 双轨管理
- Library 作为文档仓库
- Notebook 作为工作空间
- 软引用机制

### 5. Session 上限控制
- 每个 Notebook 最多 20 个 Session
- 避免资源浪费
- 鼓励创建新 Notebook

### 6. 文档引用系统
- 核心差异化功能
- 类似 NotebookLM
- 完整溯源能力

### 7. 异步任务处理
- 使用 Celery + Redis
- 文档处理异步化
- Flower 监控

## 质量保证

### 测试策略
- 单元测试覆盖率 > 70%
- 核心流程集成测试
- 主要场景 E2E 测试

### 性能指标
- API 平均响应时间 < 500ms
- 流式输出首字节延迟 < 200ms
- 10MB PDF 处理 < 30 秒
- 支持 100 并发请求

### 代码质量
- 遵循 PEP 8 规范
- 使用 Black 格式化
- Pylint 静态检查
- 代码审查

## 文档使用指南

### 开始开发前
1. 阅读 [01-architecture.md](01-architecture.md) 理解整体架构
2. 阅读 [06-notebook-library-system.md](06-notebook-library-system.md) 理解核心业务
3. 阅读 [02-directory-structure.md](02-directory-structure.md) 了解目录组织
4. 阅读 [03-implementation-plan.md](03-implementation-plan.md) 确定任务

### 开发 API 时
1. 参考 [04-api-design.md](04-api-design.md) 了解接口规范
2. 遵循统一的请求/响应格式
3. 实现完整的错误处理

### 开发引用功能时
1. 阅读 [05-document-reference-system.md](05-document-reference-system.md)
2. 理解文档解析和分块策略
3. 实现引用追踪机制

## 后续版本规划

### v1.1
- 多用户支持（可选）
- 更多文档格式
- 图表和公式识别

### v1.2
- 多语言支持
- 性能进一步优化
- 高级搜索功能

### v2.0
- 高级 RAG 策略
- 自定义 Agent
- 知识图谱集成

## 文档维护

### 更新原则
- 代码变更同步更新文档
- 重大设计变更需讨论
- 保留设计决策记录

### 版本管理
- 文档与代码版本对应
- 使用 Git 追踪变更
- 维护变更日志

---

最后更新：2026-01-17
版本：v1.0.0
