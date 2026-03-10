# MinIO 对象存储迁移方案

## 1. 背景

在 backend-v1/improve-6 阶段，项目确定了 **Bind Mount + 清理工具** 作为文档文件的存储策略。这一决策在后端开发期是合理的:开发者可以直接在 `data/documents/{document_id}/` 目录下查看 MinerU 转换结果，调试效率高。

> 当前 batch-1 已完成 MinIO 落地: 运行时持久真源是 MinIO，对 `data/documents` 的引用仅代表历史方案、迁移来源或离线/测试场景下的本地后端。

随着 frontend-v1 开发的推进，前后端联调将引入新的需求维度:

1. **前端需要高效获取图片资源**: MinerU 解析后的文档通常包含数十甚至上百张图片，全部经由 FastAPI 代理转发会造成后端性能瓶颈。
2. **Markdown 中的图片路径需要统一管理**: 当前 MinerU 在生成的 Markdown 中嵌入了 `/api/v1/documents/{id}/assets/images/{hash}.jpg` 格式的完整 API 路径，所有图片请求都经过 FastAPI 后端。
3. **部署环境的存储需求**: 从开发机迁移到服务器部署时，Bind Mount 的单机限制和缺乏标准化访问协议的问题将逐步显现。

本方案设计 **MinIO 对象存储** 作为 Bind Mount 的渐进式替代方案，通过引入存储抽象层实现平滑迁移。方案采用前瞻性设计，在前端第一版开发完成后再执行实际迁移。

## 2. 设计原则

1. **渐进式迁移**: 先通过抽象层完成兼容，再将运行时持久真源收口到 MinIO。
2. **前端零感知**: 存储后端切换对前端透明，前端只需要能正常获取 Markdown 内容和图片资源。
3. **最小改动量**: 后端只需改造存储层和内容服务层，不涉及 RAG 管线、对话引擎等核心模块。
4. **环境适配**: 运行时统一使用 MinIO，本地文件系统仅保留给离线脚本、测试和迁移场景。

## 3. 核心决策

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 存储后端切换策略 | 环境变量控制，接口抽象 | 开发和生产环境需求不同 |
| 前端图片获取方式 | MinIO Presigned URL | 绕过 FastAPI，减轻后端负载 |
| Markdown 图片路径处理 | 内容服务层动态替换 | 前端零改动，后端统一处理 |
| MinIO 部署方式 | Docker Compose 单节点 | 与现有基础设施一致 |
| 桶设计 | 单桶 `documents`，按 document_id 前缀组织 | 简单直观，与现有目录结构对应 |
| 迁移时机 | 前端第一版联调完成后 | 避免在前端开发期引入额外变量 |

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-current-analysis.md](./01-current-analysis.md) | 现状分析: 当前 Bind Mount 方案的架构、数据流、前端集成痛点 |
| 02 | [02-storage-abstraction.md](./02-storage-abstraction.md) | 存储抽象层: StorageBackend 接口设计、LocalStorage 和 MinIOStorage 实现规范 |
| 03 | [03-minio-architecture.md](./03-minio-architecture.md) | MinIO 架构: Docker 集成、桶设计、Python SDK 用法、运维配置 |
| 04 | [04-frontend-integration.md](./04-frontend-integration.md) | 前端集成: Markdown 图片路径转换、Presigned URL 机制、内容 API 改造 |
| 05 | [05-migration-plan.md](./05-migration-plan.md) | 迁移计划: 分阶段实施路径、任务拆分、回滚策略、验收标准 |

## 5. 与现有文档的关系

- **backend-v1/improve-6/05-document-storage.md**: 描述了当前 Bind Mount + 清理工具方案。本方案是其后续演进方向，不替代而是扩展。
- **frontend-v1/01-tech-stack.md ~ 03-components.md**: 描述了前端的 Markdown 渲染和图片加载需求。本方案的前端集成部分(04)直接衔接这些设计。

## 6. 当前状态

- 文档状态: 前瞻性设计，待前端第一版联调后实施
- 创建日期: 2026-02-12
- 前置依赖: frontend-v1 第一版基本可用
