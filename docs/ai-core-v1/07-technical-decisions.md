# 技术决策记录

## 1. 概述

本文档记录 MediMind Agent AI Core v1 开发过程中的关键技术决策，供团队参考和未来回顾。

每个决策遵循 ADR（Architecture Decision Record）格式：
- 背景：为什么需要做这个决策
- 选项：考虑过的方案
- 决策：最终选择
- 理由：为什么这样选择

## 2. 数据库与迁移

### 2.1 现有表结构迁移策略

**背景**

当前数据库已有 `chat_sessions`、`chat_messages` 表，以及 LlamaIndex 自动创建的向量表。新架构引入 `notebooks`、`sessions`、`library`、`documents` 等表。

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. 并存 | 保留旧表，新增新表，逐步迁移 | 兼容性好，但数据割裂 |
| B. 原地升级 | 重命名旧表，添加字段 | 需要停机迁移 |
| C. 全新开始 | 忽略旧数据，全部新建 | 简单清爽，但丢失历史 |

**决策**

采用 **方案 C：全新开始**

**理由**

1. 开源项目，用户数据量通常不大
2. 结构差异较大（新增 `notebook_id` 外键等）
3. 简化开发，专注新功能
4. 可提供可选迁移脚本给有需要的用户

---

### 2.2 LlamaIndex 向量表与 Chunks 表的关系

**背景**

LlamaIndex 自动创建 `data_documents_*` 表存储向量。新架构设计了 `document_chunks` 表。

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. 使用 LlamaIndex 表 | 不单独建 chunks 表，元数据存在 LlamaIndex 的 metadata_ 字段 | 复用现有代码，减少同步问题 |
| B. 完全自建 | 不用 LlamaIndex 的向量表 | 完全控制，但需重写向量操作 |
| C. 混合 | 元数据在自建表，向量在 LlamaIndex 表 | 可能有同步问题 |

**决策**

采用 **方案 A：使用 LlamaIndex 表**

**理由**

1. LlamaIndex 的索引构建、检索优化都可复用
2. 减少数据同步问题
3. 通过 `metadata_` JSON 字段存储扩展信息（document_id、page_number 等）
4. 仅维护 `documents` 表管理文档级别信息

**references 表设计**

`references.chunk_id` 字段：
- 类型：`VARCHAR(64)`（存储 LlamaIndex 的 `node_id`）
- **不设外键约束**
- 查询时通过 `chunk_id` 去 LlamaIndex 表按 `node_id` 字段查询

**理由**：LlamaIndex 表使用 `BIGSERIAL` 作为主键，与我们的 UUID 体系不匹配。

---

### 2.3 Documents 表归属约束

**背景**

`documents.library_id` 和 `documents.notebook_id` 需要互斥规则。

**决策**

采用 **严格二选一**

```sql
CONSTRAINT check_document_owner CHECK (
    (library_id IS NOT NULL AND notebook_id IS NULL)
    OR (library_id IS NULL AND notebook_id IS NOT NULL)
)
```

**理由**

不存在文档不属于任何 Library 或 Notebook 的业务场景。

---

### 2.4 主键类型

**背景**

表主键使用自增整数还是 UUID？

**选项**

| 类型 | 优点 | 缺点 |
|------|------|------|
| SERIAL | 节省空间、有序、性能好 | 可预测、分布式困难 |
| UUID | 全局唯一、分布式友好 | 占用空间大、无序 |

**决策**

采用 **UUID**

**理由**

1. 未来可能需要分布式部署
2. API 中暴露 ID 更安全（不可预测）
3. 与 LlamaIndex 的 node_id（UUID）保持一致

---

## 3. 嵌入模型

### 3.1 多嵌入模型支持策略

**背景**

当前支持 zhipu（1024 dims）和 biobert（768 dims）两种嵌入模型。

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. 多表 | 不同模型使用不同表 | 简单，现有实现 |
| B. 统一表 | 所有向量一张表，用字段区分 | 查询复杂 |
| C. 配置固定 | 项目级别选定一个模型 | 简化，但灵活性低 |

**决策**

采用 **方案 A：多表**（保持现状）

**补充要求**

根据配置文件中的 `default_provider` 决定查询哪张表。

**理由**

1. 现有代码已实现此模式
2. 不同维度的向量无法放在同一列
3. 切换模型时需要重建索引（提供脚本）

---

## 4. Session 管理

### 4.1 Session 计数一致性

**背景**

当创建/删除 Session 时，需要同时更新 `notebooks.session_count`。

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. 应用层更新 | 简单直观 | 可能不一致（并发/异常）|
| B. 数据库触发器 | 自动保证一致 | 增加 DB 复杂度 |
| C. 每次查询时 COUNT | 始终准确 | 性能开销 |
| D. 事务内同步更新 | 较可靠 | 需要事务管理 |

**决策**

采用 **方案 D：事务内同步更新**

**实现示例**

```python
async def create_session(self, notebook_id: str, title: str) -> Session:
    async with self.db.transaction():
        # 1. 检查上限
        count = await self.session_repo.count_by_notebook(notebook_id)
        if count >= 20:
            raise SessionLimitExceededError(...)
        
        # 2. 创建 Session
        session = await self.session_repo.create(...)
        
        # 3. 更新计数
        await self.notebook_repo.increment_session_count(notebook_id)
        
        return session
```

---

### 4.2 Session 删除策略

**背景**

删除 Session 后是否支持恢复？

**决策**

采用 **硬删除**

**理由**

1. 开源单用户版本，优先简单
2. 遵循 KISS 原则
3. 未来版本可加软删除 + 回收站

---

### 4.3 历史消息压缩

**背景**

当历史消息过多时，如何处理上下文窗口限制？

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. 保留最近 N 轮 | 删除旧消息 | 简单，可能丢失重要上下文 |
| B. 压缩摘要 | 将旧消息压缩成摘要 | 保留上下文，但增加 LLM 调用 |
| C. 重要性评分 | 根据相关性保留 | 复杂度高 |

**决策**

采用 **方案 B：压缩摘要**

**参数配置**

- 阈值：10 轮消息（user + assistant 各算 1 条，共 20 条消息）
- 保留最近 5 轮原始消息
- 摘要存储在 Session 表的 `context_summary` 字段

**实现要点**

```python
class ConversationCompressor:
    COMPRESSION_THRESHOLD = 10  # 10 轮 = 20 条消息
    KEEP_RECENT = 5  # 保留最近 5 轮

    async def compress_if_needed(self, messages: List[Message]) -> List[Message]:
        rounds = len(messages) // 2  # 计算轮数
        if rounds <= self.COMPRESSION_THRESHOLD:
            return messages
        
        # 压缩旧消息，保留最近的
        ...
```

---

## 5. 检索设计

### 5.1 Notebook 范围检索过滤

**背景**

使用单表存储时，如何按 Notebook 范围过滤检索结果？

**选项**

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A. Chunk 表冗余 notebook_id | 快速过滤 | 数据冗余，更新复杂 |
| B. 通过 document_id 关联查询 | 规范化 | 多一次查询 |

**决策**

采用 **方案 B：通过 document_id 关联查询**

**实现方式**

LlamaIndex pgvector 支持 `FilterOperator.IN` 操作符，可以直接使用：

```python
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator

# 1. 获取 Notebook 的文档 ID 列表
doc_ids = await get_notebook_document_ids(notebook_id)

# 2. 构建 metadata filter
filters = MetadataFilters(
    filters=[
        MetadataFilter(
            key="document_id",
            value=doc_ids,
            operator=FilterOperator.IN
        )
    ]
)

# 3. 检索
retriever = index.as_retriever(
    similarity_top_k=top_k,
    filters=filters
)
results = await retriever.aretrieve(query)
```

**验证**

已确认 LlamaIndex pgvector 实现支持 IN 操作符（见源码 `base.py` 第 666-700 行）。

---

### 5.2 混合检索 RRF 参数

**背景**

向量检索和全文检索如何融合？

**决策**

- 使用 RRF（Reciprocal Rank Fusion）融合
- 默认 k = 60（标准值）
- **默认等权**，暂不支持自定义权重

**理由**

1. RRF 对参数不敏感，k=60 是业界标准
2. 等权避免引入额外复杂度
3. 未来可根据实际效果调优

---

## 6. 基础设施

### 6.1 文件存储路径

**背景**

上传的文档文件存储在哪里？

**决策**

存储在项目目录下：

```
data/documents/
├── library/
│   └── {document_id}/
│       └── original.{ext}
└── notebooks/
    └── {notebook_id}/
        └── {document_id}/
            └── original.{ext}
```

**理由**

1. 开发阶段简单直接
2. 未来可扩展到 XDG 标准目录或云存储

---

### 6.2 Celery 任务设计

**背景**

文档处理涉及多个步骤，如何组织 Celery 任务？

**决策**

采用 **任务链模式**

```
process_document (入口)
    → extract_content (内容提取)
        → chunk_document (智能分块)
            → generate_embeddings (生成嵌入)
                → finalize_document (更新状态)
```

**理由**

1. 职责分离，每个任务专注一件事
2. 失败可以从断点重试
3. 便于监控和调试

---

### 6.3 Docker Compose 服务

**背景**

需要添加哪些新服务？

**决策**

添加以下服务：

1. **Redis** - Celery broker 和结果后端
2. **Celery Worker** - 异步任务执行（可选 profile）
3. **Flower** - Celery 任务监控

**配置**

```yaml
profiles:
  - worker   # celery-worker
  - debug    # flower, kibana
```

---

### 6.4 配置文件组织

**背景**

新增配置如何组织？

**决策**

保持分散，新增以下文件：

```
configs/
├── llm.yaml           # 保持
├── embeddings.yaml    # 保持
├── storage.yaml       # 保持
├── rag.yaml           # 保持
├── memory.yaml        # 保持
├── modes.yaml         # 保持
├── redis.yaml         # 新增
├── celery.yaml        # 新增
├── api.yaml           # 新增
└── notebook.yaml      # 新增
```

---

## 7. API 设计

### 7.1 SSE 流式输出

**决策**

- 心跳间隔：**15 秒**
- 超时时间：120 秒
- 事件类型：start, content, sources, done, error, heartbeat

---

### 7.2 分页响应格式

**决策**

使用嵌套 pagination 对象：

```json
{
    "data": [...],
    "pagination": {
        "total": 100,
        "limit": 20,
        "offset": 0,
        "has_next": true,
        "has_prev": false
    }
}
```

---

### 7.3 健康检查接口

**决策**

需要实现：

```
GET /api/v1/health          # 基础健康检查
GET /api/v1/health/ready    # 所有依赖就绪检查
GET /api/v1/health/live     # 服务存活检查
```

---

## 8. 日志与监控

### 8.1 日志策略

**决策**

使用 **结构化日志**（JSON 格式）

**日志级别规范**

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 系统错误，需要告警 | 数据库连接失败 |
| WARNING | 可恢复的问题 | 任务重试 |
| INFO | 关键业务操作 | 创建 Notebook、上传文档 |
| DEBUG | 详细调试信息 | 检索结果详情 |

---

## 9. 视频处理

### 9.1 Phase 4 调整

**背景**

原计划 Phase 4 实现 YouTube 和 Bilibili 视频处理。

**决策**

- 从主要实施计划中**移除 Phase 4**
- 保留为**可选任务**，标记为 "Future Enhancement"
- 视频时间戳字段设计为 `INTEGER`（秒级），预留扩展能力

---

## 10. 前端集成

### 10.1 开发阶段

**背景**

AI Core v1 阶段专注后端核心模块。

**决策**

- 当前不实现前端
- CLI 暂由 `main.py` 负责
- 未来由 React + Next.js 前端负责
- 新建独立 CLI 模块，待 FastAPI 实现后再对接

---

## 文档维护

### 更新记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-01-19 | 1.0.0 | 初始版本，记录所有技术决策 |
| 2026-01-19 | 1.0.1 | 补充 references.chunk_id 不设外键的说明 |

---

最后更新：2026-01-19
版本：v1.0.1
