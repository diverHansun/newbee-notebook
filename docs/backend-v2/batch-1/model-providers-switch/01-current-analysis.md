# 现状分析: 模型配置加载与单例管理机制

本文档完整梳理当前 LLM 和 Embedding 模型的配置来源、加载链路、单例生命周期，以及 Embedding 切换对 RAG 查询的影响，为后续设计提供事实依据。

---

## 1. 配置文件现状

### 1.1 LLM 配置 (`configs/llm.yaml`)

```yaml
llm:
  provider: qwen                        # 'zhipu' | 'qwen' | 'openai'

  zhipu:
    model: glm-4.7-flash
    temperature: 0.7
    max_tokens: 32768
    top_p: 0.8
    api_base: https://open.bigmodel.cn/api/paas/v4
    # ... 其他字段

  qwen:
    model: qwen3.5-plus
    temperature: 0.7
    max_tokens: 32768
    top_p: 0.8
    api_base: https://dashscope.aliyuncs.com/compatible-mode/v1
    enable_search: false
    enable_thinking: true
    # ... 其他字段

  openai:
    model: gpt-4o-mini
    # ... 其他字段
```

每个 Provider 下包含完整的模型参数，通过顶层 `provider` 字段选择激活哪一个。

### 1.2 Embedding 配置 (`configs/embeddings.yaml`)

```yaml
embeddings:
  provider: qwen3-embedding              # 'qwen3-embedding' | 'zhipu'

  qwen3-embedding:
    enabled: true
    mode: local                           # local | api
    model_path: models/Qwen3-Embedding-0.6B
    device: auto
    max_length: 8192
    dim: 1024
    embed_batch_size: 32
    index_dir: data/indexes/qwen3_embedding   # <-- 待废弃字段
    api_model: text-embedding-v4
    api_base: https://dashscope.aliyuncs.com/compatible-mode/v1

  zhipu:
    enabled: true
    model: embedding-3
    dim: 1024
    index_dir: data/indexes/zhipu             # <-- 待废弃字段
```

`qwen3-embedding` 支持 `local` 和 `api` 两种模式:

- **local**: 加载 `models/` 目录下的本地模型，使用 `sentence-transformers` 推理
- **api**: 调用 DashScope 的 OpenAI 兼容接口

### 1.3 环境变量 (`.env`)

```dotenv
# API Keys (必需)
ZHIPU_API_KEY=...
DASHSCOPE_API_KEY=...

# Provider 覆盖 (可选)
# LLM_PROVIDER=qwen
# EMBEDDING_PROVIDER=qwen3-embedding

# Embedding 模式覆盖 (可选)
QWEN3_EMBEDDING_MODE=local
```

### 1.4 关于 `index_dir` 字段

`index_dir` 用于旧的本地文件索引 (VectorStoreIndex 的 `persist_dir`)。当前系统已全面迁移至 pgvector，该字段的使用情况:

| 引用位置 | 用途 | 是否活跃 |
|----------|------|----------|
| `config.py: get_index_directory()` | 返回索引目录路径 | 被调用但非核心路径 |
| `test_chat_engine_integration.py` | 集成测试中使用 | 仅测试代码 |
| `config.py: get_config()` | 聚合到全局配置字典 | 信息性暴露 |

主流程 (文档索引、RAG 查询) 均通过 pgvector 进行，不再依赖此字段。**建议标记废弃，后续版本移除。**

---

## 2. LLM 加载链路

### 2.1 完整调用链

```
HTTP 请求
  --> dependencies.py: get_llm_singleton()
        --> 检查 _llm 全局变量是否为 None
        --> 若 None:
              core/llm/__init__.py: build_llm()
                --> config.py: get_llm_provider()
                      优先级: env LLM_PROVIDER > YAML llm.provider > 默认 "zhipu"
                --> registry.py: get_builder(provider)
                      从 _LLM_REGISTRY 获取已注册的 builder 函数
                --> 调用 builder 函数 (build_qwen_llm / build_zhipu_llm)
                      --> 读取 YAML 中 provider 子配置
                      --> 构造 QwenOpenAI / ZhipuOpenAI 实例
        --> 缓存到 _llm 全局变量，后续请求复用
```

### 2.2 Builder 函数签名

两个 builder 函数均接受可选参数:

```python
# core/llm/qwen.py
@register_llm("qwen")
def build_qwen_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system_prompt: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:

# core/llm/zhipu.py
@register_llm("zhipu")
def build_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    system_prompt: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
```

传入参数时使用传入值，未传入时从 YAML 读取。这意味着 Builder 已经天然支持外部参数注入，无需修改 Builder 架构即可接入 DB 配置。

### 2.3 参数解析逻辑 (以 Qwen 为例)

```python
cfg = _get_qwen_config()  # 从 YAML 读取

final_model = model or cfg.get("model", "qwen-plus")
final_temperature = temperature if temperature is not None else float(cfg.get("temperature", 0.7))
final_max_tokens = max_tokens if max_tokens is not None else int(cfg.get("max_tokens", 8192))
final_top_p = top_p if top_p is not None else cfg.get("top_p", 0.8)
```

每个参数都有 "传入值 > YAML > 硬编码默认" 的 fallback 链。

### 2.4 Registry 模式

```python
# core/llm/registry.py
_LLM_REGISTRY: Dict[str, Callable[[], LLM]] = {}

# 已注册的 Provider:
# - "qwen"  --> build_qwen_llm
# - "zhipu" --> build_zhipu_llm (build_llm)
# - "openai" --> build_openai_llm
```

通过 `@register_llm("name")` 装饰器在模块导入时自动注册。新增 Provider 只需创建新文件，符合开闭原则 (OCP)。

---

## 3. Embedding 加载链路

### 3.1 完整调用链

```
HTTP 请求
  --> dependencies.py: get_embedding_singleton()
        --> 检查 _embed_model 全局变量是否为 None
        --> 若 None:
              core/rag/embeddings/__init__.py: build_embedding()
                --> config.py: get_embedding_provider()
                      优先级: env EMBEDDING_PROVIDER > YAML embeddings.provider > 默认 "qwen3-embedding"
                --> registry.py: get_builder(provider)
                --> 调用 builder 函数

              [provider == "qwen3-embedding"]:
                build_qwen3_embedding()
                  --> 确定 mode: env QWEN3_EMBEDDING_MODE > 参数 > YAML mode > 默认 "local"
                  --> mode == "local":
                        Qwen3LocalEmbedding(model_path, dim=1024, device, ...)
                          --> SentenceTransformer 加载本地模型
                  --> mode == "api":
                        Qwen3APIEmbedding(model="text-embedding-v4", dim=1024, ...)
                          --> OpenAI 兼容客户端

              [provider == "zhipu"]:
                build_zhipu_embedding()
                  --> ZhipuAIEmbedding(model="embedding-3", dimensions=1024)
```

### 3.2 Embedding 维度

所有当前支持的 Embedding provider 输出维度均为 1024:

| Provider | 模型 | 维度 |
|----------|------|------|
| qwen3-embedding (local) | Qwen3-Embedding-0.6B | 1024 (可截断) |
| qwen3-embedding (api) | text-embedding-v4 | 1024 |
| zhipu | embedding-3 | 1024 |

Qwen3LocalEmbedding 支持维度截断 (Matryoshka Representation Learning)，但统一使用 1024 以保持 pgvector 表兼容。

### 3.3 本地模型目录

```
models/
  .gitkeep
  Qwen3-Embedding-0.6B/
    config.json
    model.safetensors
    tokenizer.json
    ...
```

当前仅有一个本地模型。扫描 `models/` 目录可识别有效模型目录 (包含 `config.json` 或 `model.safetensors`)。

---

## 4. 单例管理

### 4.1 FastAPI 进程单例

```python
# api/dependencies.py
_llm = None
_embed_model = None
_pgvector_index = None
_es_index = None

def get_llm_singleton():
    global _llm
    if _llm is None:
        _llm = build_llm()
    return _llm

def get_embedding_singleton():
    global _embed_model
    if _embed_model is None:
        _embed_model = build_embedding()
    return _embed_model
```

模块级全局变量，首次访问时初始化，进程生命周期内不会重建。修改 YAML 或 `.env` 后必须重启 FastAPI 进程才能生效。

特殊情况: `SessionManager` 中 LLM 每次请求重建 (`build_llm()`)，注释说明是为避免 transport 状态泄漏。

### 4.2 Celery Worker 单例

```python
# infrastructure/tasks/document_tasks.py
_EMBED_MODEL = None

def _get_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = build_embedding()
    return _EMBED_MODEL
```

Celery Worker 是独立进程，拥有自己的 `_EMBED_MODEL` 全局单例，与 FastAPI 进程的 `_embed_model` 互不影响。

### 4.3 pgvector Index 单例

pgvector index 依赖 embedding model 和 provider 配置:

```python
async def get_pg_index_singleton():
    global _pgvector_index
    if _pgvector_index is None:
        provider = get_embedding_provider()
        pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
        pg_config = PGVectorConfig(
            table_name=pgvector_provider_cfg["table_name"],
            embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
            ...
        )
        _pgvector_index = await load_pgvector_index(get_embedding_singleton(), pg_config)
    return _pgvector_index
```

切换 Embedding provider 后，pgvector index 必须同步重置，因为不同 provider 使用不同的数据库表。

---

## 5. Embedding 切换对 RAG 的影响

### 5.1 pgvector 多表机制

`configs/storage.yaml` 已为每个 Embedding provider 定义了独立的 pgvector 表:

```yaml
pgvector:
  tables:
    qwen3-embedding:
      table_name: documents_qwen3_embedding     # 实际表: data_documents_qwen3_embedding
      embedding_dimension: 1024
    zhipu:
      table_name: documents_zhipu               # 实际表: data_documents_zhipu
      embedding_dimension: 1024
```

### 5.2 索引时的路由

文档索引任务 `_index_pg_nodes()` 根据当前 Embedding provider 自动路由到对应表:

```python
provider = get_embedding_provider()
pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
# table_name 随 provider 变化
```

### 5.3 查询时的路由

RAG 查询通过 `get_pg_index_singleton()` 获取 pgvector index，该 index 绑定到当前 provider 的表。切换 provider 后:

- 重置 `_pgvector_index = None`
- 下次查询重建时绑定到新 provider 的表
- 已索引文档的向量数据保留在原 provider 表中不受影响

### 5.4 切换后的行为

```
场景: 用户将 Embedding 从 qwen3-embedding 切换到 zhipu

已索引文档 (100 篇):
  - 向量存储在 data_documents_qwen3_embedding 表中
  - 切换后 RAG 查询指向 data_documents_zhipu 表
  - 这 100 篇文档对当前 RAG 查询不可见

新索引文档:
  - 使用 zhipu embedding-3 生成向量
  - 存储到 data_documents_zhipu 表
  - 对 RAG 查询可见

如需让旧文档在新 provider 下可用:
  - 用户通过 Admin 面板触发 re-index
  - 使用新 Embedding 模型重新生成向量并写入新表
```

前端必须在切换 Embedding 时清晰告知用户这一行为。

---

## 6. 当前配置读取优先级

```
环境变量 (.env)
    |
    v (未设置时)
YAML 配置文件 (configs/*.yaml)
    |
    v (未配置时)
代码硬编码默认值
```

以 `get_llm_provider()` 为例:

```python
def get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER")          # 1. 环境变量
    if provider and provider.strip():
        return provider.strip().lower()

    llm_config = get_llm_config()                  # 2. YAML
    if llm_config and "llm" in llm_config:
        provider = llm_config["llm"].get("provider")
        if provider:
            return str(provider).strip().lower()

    return "zhipu"                                 # 3. 硬编码默认
```

本方案需在最顶层插入 DB 查询，形成四级优先级链。

---

## 7. 存在的问题总结

| 问题 | 影响 | 解决方向 |
|------|------|----------|
| 配置修改需重启 | 用户无法通过 UI 即时切换模型 | DB 持久化 + 单例重置 |
| 无类型验证 | YAML 拼写/类型错误运行时才暴露 | Pydantic 校验 (可后续补充) |
| 每次读取磁盘 I/O | `get_llm_config()` 无缓存 | DB 查询带缓存替代 |
| `index_dir` 遗留字段 | 与 pgvector 方案不一致 | 标记废弃 |
| Celery Worker 独立单例 | 切换 Embedding 后 Worker 需同步感知 | Worker 按任务读取最新配置 |
