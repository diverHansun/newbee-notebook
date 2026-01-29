# AI Core v1 - Test 2: 系统优化与问题修复

## 概述

本次测试聚焦于文档处理流程的问题排查与系统优化，包含三个核心议题。

## 文档索引

| 文档 | 内容 | 优先级 |
|------|------|--------|
| [01-celery-queue-fix.md](01-celery-queue-fix.md) | Celery队列配置问题排查与修复 | P0 - 阻塞性问题 |
| [02-admin-api-design.md](02-admin-api-design.md) | 管理接口设计(reindex/reprocess/stats) | P1 - 运维需求 |
| [03-reference-protection.md](03-reference-protection.md) | 删除文档时保留对话引用 | P2 - 数据完整性 |

## 问题总结

### 1. Celery队列不匹配 (已定位)

**现象**: 文档上传后状态始终为pending

**根因**: `celery_app.py`配置task_routes将任务路由到`documents`队列，但Worker只监听`default`队列

**解决**: 移除task_routes配置，统一使用default队列

**状态**: 待修复

### 2. 缺少管理接口

**现象**: 无法手动触发处理pending文档，无法查看索引状态

**解决**: 新增三个管理API
- `POST /admin/reprocess-pending`
- `POST /admin/documents/{id}/reindex`
- `GET /admin/index-stats`

**状态**: 待实现

### 3. 删除文档丢失引用

**现象**: 删除文档时级联删除对话中的引用记录

**解决**: 修改FK约束为SET NULL，新增is_source_deleted标记

**状态**: 待实现

## 数据库现状 (2026-01-28)

执行清理后的数据状态:

| 表 | 记录数 | 说明 |
|----|--------|------|
| documents | 4 | 全部pending状态 |
| notebooks | 0 | 已清理测试数据 |
| sessions | 0 | 已清理 |
| messages | 0 | 已清理 |
| pgvector | 0 | 已清理孤立数据 |
| elasticsearch | 0 | 已重建空索引 |

## 实施顺序

1. **修复Celery队列** - 修改celery_app.py，重启Worker
2. **验证文档处理** - 处理4个pending文档，确认流程正常
3. **实现管理接口** - 按设计文档实现三个API
4. **实现引用保护** - 数据库迁移 + 代码修改

## 相关文件

- `medimind_agent/infrastructure/tasks/celery_app.py` - Celery配置
- `medimind_agent/infrastructure/tasks/document_tasks.py` - 文档处理任务
- `medimind_agent/application/services/document_service.py` - 文档服务
- `medimind_agent/scripts/db/init-postgres.sql` - 数据库初始化
- `docker-compose.yml` - Docker服务配置
