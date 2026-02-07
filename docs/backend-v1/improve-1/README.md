# 文档管理系统改进方案 v1

## 概述

本次改进主要针对 MediMind Agent 的文档管理系统进行架构优化，解决当前存在的以下问题：

1. 文档存储结构分散，难以通过 `document_id` 统一管理
2. 上传即 Embedding 导致计算资源浪费
3. 删除文档时未清理文件系统
4. 缺少 Notebook-Document 关联管理 API

## 改进目标

| 目标 | 描述 |
|------|------|
| 统一存储结构 | 所有文件按 `document_id` 组织，便于管理和清理 |
| 延迟处理 | 上传到 Library 时仅保存文件，添加到 Notebook 时才进行转换和 Embedding |
| 完整删除 | 删除文档时清理所有相关数据（文件、向量、索引、数据库记录） |
| 关联管理 | 提供完整的 Notebook-Document 关联 API |

## 核心设计原则

1. **Library 优先**：所有文档必须先上传到 Library，再添加到 Notebook
2. **按需处理**：只有加入 Notebook 的文档才进行转换和 Embedding，节省计算资源
3. **软硬删除分离**：从 Notebook 移除仅解除关联，从 Library 删除才完全清理
4. **批量操作**：支持批量上传和批量添加，提升效率

## 文档索引

| 文档 | 描述 |
|------|------|
| [01-architecture.md](./01-architecture.md) | 架构设计：存储结构、处理流程、状态流转 |
| [02-api-design.md](./02-api-design.md) | API 端点设计：新增、修改、废弃的端点 |
| [03-data-model.md](./03-data-model.md) | 数据模型变更：实体、状态、数据库表结构 |
| [04-implementation-plan.md](./04-implementation-plan.md) | 实现计划：任务分解、优先级、依赖关系 |

## 影响范围

### 需要修改的模块

- `medimind_agent/infrastructure/storage/local_storage.py`
- `medimind_agent/infrastructure/document_processing/store.py`
- `medimind_agent/application/services/document_service.py`
- `medimind_agent/infrastructure/tasks/document_tasks.py`
- `medimind_agent/api/routes/documents.py`
- `medimind_agent/domain/entities/document.py`
- `medimind_agent/domain/value_objects/document_status.py`

### 需要新增的模块

- `medimind_agent/api/routes/notebook_documents.py`
- `medimind_agent/application/services/notebook_document_service.py`

### 废弃的功能

- `POST /documents/notebooks/{notebook_id}/upload` 端点

## 版本信息

- 文档版本：1.0
- 创建日期：2026-02-07
- 状态：设计中
