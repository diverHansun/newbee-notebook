# 向量维度策略: 统一 1024 维

本文档描述 improve-7 中向量维度的统一策略，包括 MRL 机制原理、各模型维度对齐方案、BioBERT 弃用处理，以及 pgvector 存储层的兼容性分析。

---

## 1. 问题陈述

### 1.1 当前维度不一致

| 模型 | 输出维度 | 状态 |
|------|---------|------|
| BioBERT-v1.1 | 768 | 弃用 |
| 智谱 embedding-3 | 1024 | 在用 |

如果新增 Qwen3-Embedding 采用原生最高维度 (1024)，恰好与智谱 embedding-3 一致。但需要确保:

1. 所有新旧模型输出维度统一为 **1024**
2. BioBERT 的 768 维数据需要处理
3. pgvector 索引不需要频繁重建

### 1.2 目标

**所有 embedding 模型统一输出 1024 维向量**，使:
- 切换 embedding provider 时，pgvector 索引无需迁移
- 不同模型产生的向量可以共存于同一张表
- 向量检索的 `<=>` (cosine) / `<->` (L2) 操作符正常工作

---

## 2. Matryoshka Representation Learning (MRL)

### 2.1 MRL 原理

MRL (俄罗斯套娃表示学习) 是一种训练技术，使得模型输出的向量在任意前缀长度上都保留语义信息:

```
原始向量 (1024 维): [v1, v2, v3, ..., v1024]
                     |___________|___________|
                     前 512 维      后 512 维
                     (保留主要语义)  (补充细节)
```

**截断操作**:

```python
# 取前 N 维即可得到 N 维向量
full_embedding = model.encode("text")    # shape: (1024,)
dim_512 = full_embedding[:512]           # shape: (512,), 仍有效
dim_256 = full_embedding[:256]           # shape: (256,), 仍有效
```

截断后需要重新做 L2 归一化 (unit norm):

```python
import numpy as np

truncated = full_embedding[:target_dim]
normalized = truncated / np.linalg.norm(truncated)
```

### 2.2 Qwen3-Embedding 的 MRL 支持

Qwen3-Embedding-0.6B 和 API 版 qwen3-embedding 都支持 MRL:

| 平台 | 维度范围 | 默认维度 | 推荐维度 |
|------|---------|---------|---------|
| 本地 (sentence-transformers) | 32 - 1024 | 1024 | 1024 |
| API (text-embedding-v4) | 32 - 1024 | 1024 | 1024 |
| API (qwen3-vl-embedding) | 256 - 2560 | 1024 | 1024 |
| 本地 (Qwen3-VL-Embedding-2B) | 64 - 2048 | 1024 | 1024 |

### 2.3 API 端的维度控制

DashScope OpenAI 兼容端点通过 `dimensions` 参数控制输出维度:

```python
# OpenAI SDK 方式
response = client.embeddings.create(
    model="text-embedding-v4",
    input=["文本"],
    dimensions=1024,    # 指定输出维度
)
```

DashScope 原生 API 通过 `parameters.dimension` 控制:

```json
{
    "model": "qwen3-vl-embedding",
    "input": {"contents": [{"text": "文本"}]},
    "parameters": {"dimension": 1024}
}
```

### 2.4 本地模型的维度控制

`sentence-transformers` 方式:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("models/Qwen3-Embedding-0.6B")

# 方法1: 使用 truncate_dim 参数 (如果模型支持)
embeddings = model.encode(texts, normalize_embeddings=True)

# 方法2: 手动截断 + 归一化
embeddings = model.encode(texts, normalize_embeddings=True)
truncated = embeddings[:, :1024]
norms = np.linalg.norm(truncated, axis=1, keepdims=True)
truncated = truncated / np.clip(norms, 1e-10, None)
```

由于 Qwen3-Embedding-0.6B 的原生最大维度就是 1024，所以 **不需要截断**，直接使用原始输出即可。

---

## 3. 各模型维度对齐方案

### 3.1 统一维度表

| 模型 | 原生最大维度 | 统一输出维度 | 处理方式 |
|------|-------------|-------------|---------|
| 智谱 embedding-3 | 1024 | 1024 | 无需处理，原生输出 |
| Qwen3-Embedding-0.6B | 1024 | 1024 | 无需截断，原生输出 |
| text-embedding-v4 (API) | 1024 | 1024 | `dimensions=1024` |
| qwen3-vl-embedding (API) | 2560 | 1024 | `dimension=1024` (MRL 截断) |
| Qwen3-VL-Embedding-2B | 2048 | 1024 | 手动截断 + L2 归一化 |
| BioBERT-v1.1 (弃用) | 768 | N/A | 弃用，不参与统一 |

### 3.2 维度一致性保证

在每个 Embedding 类的 `dimensions` 属性中统一返回 1024:

```python
class QwenLocalEmbedding(BaseEmbeddingModel):
    @property
    def dimensions(self) -> int:
        return 1024  # 统一维度

class QwenVLAPIEmbedding(BaseEmbeddingModel):
    @property
    def dimensions(self) -> int:
        return 1024  # 统一维度
```

在 `build_embedding()` 工厂函数中可增加断言:

```python
def build_embedding() -> BaseEmbeddingModel:
    model = get_builder(provider)()
    assert model.dimensions == 1024, (
        f"Embedding model {model.model_name} outputs {model.dimensions}D, "
        f"expected 1024D. Check dim config in embeddings.yaml."
    )
    return model
```

---

## 4. BioBERT 弃用方案

### 4.1 弃用原因

| 问题 | 说明 |
|------|------|
| 中文不支持 | BioBERT 仅支持英文，无法处理中文文档 |
| 维度不兼容 | 768 维 ≠ 1024 维统一标准 |
| 上下文太短 | 512 tokens，长文本需要切分更多 chunk |
| 领域局限 | 生物医学专用，通用文本效果差 |

### 4.2 处理步骤

1. **embeddings.yaml**: 设置 `biobert.enabled: false`
2. **代码保留**: `biobert.py` 文件保留，`@register_embedding("biobert")` 装饰器保留
3. **Registry**: enabled=false 时 registry 中仍注册该 provider，但在 `build_embedding()` 中不会被默认选择
4. **数据迁移**: 如果 pgvector 中存在 768 维的旧数据，需要重新用新模型编码

### 4.3 数据迁移 (如需)

如果数据库中有 BioBERT 生成的 768 维向量:

```sql
-- 1. 检查现有向量维度
SELECT vector_dims(embedding) AS dim, COUNT(*)
FROM document_chunks
GROUP BY vector_dims(embedding);

-- 2. 如果存在 768 维数据，需要重新编码
-- 通过 Python 脚本批量处理:
--   a. 读取所有 768 维记录的原文
--   b. 用新的 1024 维模型重新编码
--   c. 更新 embedding 列

-- 3. 修改列定义 (如果列定义了固定维度)
ALTER TABLE document_chunks
ALTER COLUMN embedding TYPE vector(1024);

-- 4. 重建索引
DROP INDEX IF EXISTS idx_document_chunks_embedding;
CREATE INDEX idx_document_chunks_embedding
ON document_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 4.4 安全回退

如果 Qwen3-Embedding 出现问题，可以快速回退到智谱 embedding-3:

```yaml
# embeddings.yaml - 回退方案
embeddings:
  provider: zhipu    # 切换回智谱
```

不需要回退到 BioBERT，因为智谱 embedding-3 同样输出 1024 维。

---

## 5. pgvector 兼容性分析

### 5.1 现有 pgvector 结构

```sql
-- 当前表结构 (假设)
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),     -- 或 vector(768) (BioBERT 时代)
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 维度统一后的优势

统一 1024 维后:

| 操作 | 是否需要 | 说明 |
|------|---------|------|
| 修改列定义 | 一次性 | 如果之前是 `vector(768)`，改为 `vector(1024)` |
| 重建索引 | 一次性 | 列维度变化后需重建 |
| 切换 provider | 否 | zhipu ↔ qwen 切换，维度不变 |
| 混合数据 | 支持 | 不同模型的 1024 维向量可共存 |

### 5.3 索引类型选择

```sql
-- IVFFlat: 适合中小规模 (< 1M 条)
CREATE INDEX ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- HNSW: 适合大规模 (> 1M 条)，查询更快但建索引更慢
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

对于当前项目规模，IVFFlat 即可满足需求。

### 5.4 查询兼容性

cosine similarity 查询不依赖于 embedding 的来源模型:

```sql
-- cosine distance (越小越相似)
SELECT content, embedding <=> $1::vector AS distance
FROM document_chunks
ORDER BY embedding <=> $1::vector
LIMIT 10;
```

只要维度一致 (1024)，无论向量由哪个模型产生，查询操作都正常。

**注意**: 不同模型产生的向量虽然维度相同，但语义空间不同。如果文档从模型 A 编码，查询却用模型 B 编码，检索效果会下降。因此:
- 切换 embedding 模型后，应重新编码所有文档
- 不要混用不同模型的向量进行相似度比较

---

## 6. 语义空间一致性

### 6.1 问题

不同模型的 1024 维向量处于不同的语义空间:

```
智谱 embedding-3:  "深度学习" → [0.12, -0.34, 0.56, ...]
Qwen3-Embedding:  "深度学习" → [0.45, 0.23, -0.11, ...]
```

维度相同，但数值含义不同，不能跨模型比较。

### 6.2 解决方案

在 `document_chunks` 表中记录 embedding 模型信息:

```sql
-- metadata 中记录 embedding 模型
INSERT INTO document_chunks (content, embedding, metadata)
VALUES (
    '深度学习的基本概念...',
    $1::vector,
    '{"embed_model": "qwen3-embedding-1024d", "embed_time": "2026-02-13"}'::jsonb
);
```

切换模型时，通过 metadata 标记哪些记录需要重新编码:

```sql
-- 查找需要重新编码的记录
SELECT id, content FROM document_chunks
WHERE metadata->>'embed_model' != 'qwen3-embedding-1024d';
```

### 6.3 渐进式迁移

不需要一次性重新编码所有文档，可以:

1. 新文档使用新模型编码
2. 后台批量任务逐步重新编码旧文档
3. 通过 metadata 区分已迁移和未迁移的记录

---

## 7. 总结

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 统一维度 | 1024 | 智谱和 Qwen 原生最大维度一致 |
| MRL 截断 | 仅 VL 模型需要 | 文本模型原生 1024，无需截断 |
| BioBERT | 弃用，不参与统一 | 768 维不兼容，中文不支持 |
| 维度校验 | build_embedding() 中断言 | 防止配置错误导致维度不匹配 |
| 迁移策略 | metadata 标记 + 渐进式 | 不中断服务 |
| 索引方案 | IVFFlat + cosine distance | 当前规模适用 |
