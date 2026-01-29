# AI Core v1 - Test 3: Celery异步处理与检索过滤修复

## 概述

本次测试发现两个核心问题:
1. Celery Worker中异步对象生命周期管理问题导致文档处理间歇性失败
2. Elasticsearch向量存储不支持IN过滤操作符导致文档范围检索失败

## 文档索引

| 文档 | 内容 | 优先级 |
|------|------|--------|
| [01-celery-event-loop-fix.md](01-celery-event-loop-fix.md) | Celery异步事件循环问题修复 | P0 - 阻塞性问题 |
| [02-metadata-filter-fix.md](02-metadata-filter-fix.md) | 元数据过滤器IN操作符修复 | P0 - 阻塞性问题 |

## 问题总结

### 1. Celery Event Loop问题

**现象**: 文档上传后第一次处理成功,后续处理失败,报错`RuntimeError: Event loop is closed`

**根因**:
- `document_tasks.py`中`_ES_INDEX`和`_PG_INDEX`作为全局变量缓存
- Celery每个任务调用`asyncio.run()`创建新的事件循环
- 首次任务创建的ES客户端内部aiohttp session绑定到该事件循环
- 后续任务使用新事件循环,但复用旧的ES客户端导致session失效

**状态**: 待修复

### 2. FilterOperator.IN不支持

**现象**: Explain/Conclude/Ask模式在有文档的notebook中执行时报错`Vector Store only supports exact match filters`

**根因**:
- LlamaIndex的Elasticsearch向量存储使用`legacy_filters()`方法转换过滤器
- 该方法仅支持`FilterOperator.EQ`,不支持`IN`操作符
- pgvector存储本身支持IN操作符,问题出在ES端

**状态**: 待修复

## 相关文件

- `medimind_agent/infrastructure/tasks/document_tasks.py` - Celery任务定义
- `medimind_agent/core/engine/modes/explain_mode.py` - Explain模式过滤器
- `medimind_agent/core/engine/modes/conclude_mode.py` - Conclude模式过滤器
- `medimind_agent/core/engine/modes/ask_mode.py` - Ask模式过滤器
- `medimind_agent/core/rag/retrieval/hybrid_retriever.py` - 混合检索器

## 实施顺序

1. **修复Celery Event Loop** - 重构全局索引管理
2. **修复元数据过滤器** - 将IN操作拆分为多个EQ操作
3. **回归测试** - 验证完整文档处理和检索流程
