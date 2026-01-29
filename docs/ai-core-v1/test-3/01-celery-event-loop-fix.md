# Celery异步事件循环问题修复

## 问题描述

文档上传后Celery任务执行失败,错误信息:
```
RuntimeError: Event loop is closed
```

### 复现步骤

1. 启动Celery Worker
2. 上传第一个文档 - 处理成功
3. 上传第二个文档 - 处理失败,报Event loop is closed

### 错误堆栈

```
File ".../elastic_transport/_node/_http_aiohttp.py", line 189
    async with self.session.request(
File ".../aiohttp/client.py", line 596
    handle = tm.start()
File ".../asyncio/base_events.py", line 520
    raise RuntimeError('Event loop is closed')
```

## 根因分析

### 当前代码结构

`document_tasks.py`:
```python
_EMBED_MODEL = None
_PG_INDEX = None
_ES_INDEX = None

@app.task
def process_document_task(document_id: str):
    asyncio.run(_process_document_async(document_id))

async def _index_nodes(nodes):
    global _PG_INDEX, _ES_INDEX
    # ... 初始化逻辑
    if _ES_INDEX is None:
        _ES_INDEX = await load_es_index(embed_model, es_config)  # 创建ES客户端
    _ES_INDEX.insert_nodes(nodes)  # 使用ES客户端
```

### 问题机制

```
Task 1执行:
├─ asyncio.run() 创建 EventLoop-A
├─ load_es_index() 创建 AsyncElasticsearch 客户端
│   └─ 内部aiohttp.ClientSession 绑定到 EventLoop-A
├─ _ES_INDEX 缓存到全局变量
└─ EventLoop-A 关闭

Task 2执行:
├─ asyncio.run() 创建 EventLoop-B (新的事件循环)
├─ _ES_INDEX 非空,复用缓存
├─ insert_nodes() 调用 ES 客户端
│   └─ aiohttp session 尝试使用 EventLoop-A (已关闭)
└─ RuntimeError: Event loop is closed
```

### 核心问题

1. **全局状态在任务间共享**: `_ES_INDEX`作为模块级变量,在多次`asyncio.run()`调用间保持
2. **事件循环生命周期不匹配**: 每次`asyncio.run()`创建新循环,但异步客户端绑定到首次创建的循环
3. **aiohttp session不可跨循环复用**: aiohttp的ClientSession与创建时的事件循环强绑定

## 解决方案

### 方案A: 每次任务重新初始化索引 (推荐)

移除全局缓存,每次任务执行时创建新的索引对象:

```python
async def _index_nodes(nodes, embed_model):
    """Index nodes to pgvector and ES."""
    storage_cfg = get_storage_config()

    # 每次创建新的索引对象
    pg_cfg = storage_cfg.get("postgresql", {})
    provider = get_embedding_provider()
    pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
    pg_config = PGVectorConfig(
        host=pg_cfg.get("host", "localhost"),
        port=pg_cfg.get("port", 5432),
        database=pg_cfg.get("database", "medimind"),
        user=pg_cfg.get("user", "postgres"),
        password=pg_cfg.get("password", ""),
        table_name=pgvector_provider_cfg["table_name"],
        embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
    )
    pg_index = await load_pgvector_index(embed_model, pg_config)
    pg_index.insert_nodes(nodes)

    es_cfg = storage_cfg.get("elasticsearch", {})
    es_config = ElasticsearchConfig(
        url=es_cfg.get("url", "http://localhost:9200"),
        index_name=es_cfg.get("index_name", "medimind_docs"),
    )
    es_index = await load_es_index(embed_model, es_config)
    es_index.insert_nodes(nodes)
```

**优点**:
- 实现简单,无状态
- 每次任务使用独立的连接

**缺点**:
- 每次任务都创建新连接,有性能开销
- 适合低频任务场景

### 方案B: 使用同步API (备选)

Celery本身是同步的,可以使用同步版本的索引操作:

```python
from medimind_agent.core.engine.index_builder import (
    load_pgvector_index_sync,
    load_es_index_sync,
)

_PG_INDEX = None
_ES_INDEX = None

def _index_nodes_sync(nodes, embed_model):
    global _PG_INDEX, _ES_INDEX
    # ... config setup
    if _PG_INDEX is None:
        _PG_INDEX = load_pgvector_index_sync(embed_model, pg_config)
    if _ES_INDEX is None:
        _ES_INDEX = load_es_index_sync(embed_model, es_config)

    _PG_INDEX.insert_nodes(nodes)
    _ES_INDEX.insert_nodes(nodes)
```

**优点**:
- 避免事件循环问题
- 可复用连接

**缺点**:
- 需要确认所有依赖库支持同步操作
- 可能需要修改`load_*_index_sync`实现

### 方案C: Worker进程内维护单一事件循环

使用`asyncio.get_event_loop()`代替`asyncio.run()`:

```python
import asyncio

_loop = None

def get_or_create_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop

@app.task
def process_document_task(document_id: str):
    loop = get_or_create_loop()
    loop.run_until_complete(_process_document_async(document_id))
```

**优点**:
- 保持事件循环存活,客户端可复用
- 性能较好

**缺点**:
- 需要管理事件循环生命周期
- 可能与Celery prefork模型冲突

## 推荐方案

**采用方案A**: 每次任务重新初始化索引

理由:
1. 文档处理是低频操作,连接开销可接受
2. 实现简单,无需修改外部依赖
3. 无状态设计更适合分布式任务队列

## 代码修改

### 修改文件

`medimind_agent/infrastructure/tasks/document_tasks.py`

### 修改内容

1. 移除全局索引变量:
```python
# 删除以下行
_PG_INDEX = None
_ES_INDEX = None
```

2. 修改`_index_nodes`函数:
```python
async def _index_nodes(nodes: list, embed_model) -> None:
    """Index nodes to pgvector and Elasticsearch.

    Creates fresh index connections for each call to avoid event loop issues.
    """
    storage_cfg = get_storage_config()

    # pgvector indexing
    pg_cfg = storage_cfg.get("postgresql", {})
    provider = get_embedding_provider()
    pgvector_provider_cfg = get_pgvector_config_for_provider(provider)
    pg_config = PGVectorConfig(
        host=pg_cfg.get("host", "localhost"),
        port=pg_cfg.get("port", 5432),
        database=pg_cfg.get("database", "medimind"),
        user=pg_cfg.get("user", "postgres"),
        password=pg_cfg.get("password", ""),
        table_name=pgvector_provider_cfg["table_name"],
        embedding_dimension=pgvector_provider_cfg["embedding_dimension"],
    )
    pg_index = await load_pgvector_index(embed_model, pg_config)
    pg_index.insert_nodes(nodes)

    # Elasticsearch indexing
    es_cfg = storage_cfg.get("elasticsearch", {})
    es_config = ElasticsearchConfig(
        url=es_cfg.get("url", "http://localhost:9200"),
        index_name=es_cfg.get("index_name", "medimind_docs"),
    )
    es_index = await load_es_index(embed_model, es_config)
    es_index.insert_nodes(nodes)
```

3. 更新调用点:
```python
async def _process_document_async(document_id: str):
    # ... 文档处理逻辑
    embed_model = build_embedding()
    await _index_nodes(nodes, embed_model)
```

## 验证步骤

1. 重启Celery Worker:
```bash
docker restart medimind-celery-worker
```

2. 连续上传多个文档:
```bash
for i in 1 2 3; do
  echo "Test document $i" > /tmp/test_$i.txt
  curl -X POST http://localhost:8000/api/v1/documents/library/upload \
    -F "file=@/tmp/test_$i.txt"
  sleep 5
done
```

3. 验证所有文档状态为completed:
```bash
curl http://localhost:8000/api/v1/library/documents | jq '.data[].status'
```

4. 检查Worker日志无Event loop错误:
```bash
docker logs medimind-celery-worker --tail 50 | grep -i "event loop"
```
