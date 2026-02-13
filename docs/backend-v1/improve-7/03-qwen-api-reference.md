# 阿里云百炼 DashScope API 参考

本文档整理阿里云百炼 (DashScope) 平台的 LLM 和 Embedding 相关 API 信息，作为 improve-7 实现的技术参考。

---

## 1. 平台概述

**阿里云百炼 (DashScope)** 是阿里云的大模型服务平台，提供 Qwen 系列模型的 API 接入。

- 控制台: https://dashscope.console.aliyun.com/
- API Key 管理: 控制台 → API-KEY 管理
- 文档中心: https://help.aliyun.com/zh/model-studio/

### 1.1 认证方式

所有 API 请求通过 HTTP Header 传递 API Key:

```
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

环境变量约定:

```bash
# .env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 2. LLM API (OpenAI 兼容模式)

### 2.1 端点

```
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

该端点完全兼容 OpenAI Chat Completions API 规范，可直接使用 OpenAI SDK 调用。

### 2.2 请求结构

```json
{
    "model": "qwen-plus",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "max_tokens": 8192,
    "top_p": 0.8,
    "stream": true
}
```

### 2.3 响应结构 (非流式)

```json
{
    "id": "chatcmpl-xxxxxxxxx",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "qwen-plus",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好！有什么可以帮助你的吗？"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 15,
        "total_tokens": 35
    }
}
```

### 2.4 流式响应 (SSE)

```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}],"model":"qwen-plus"}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"你"},"finish_reason":null}],"model":"qwen-plus"}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}],"model":"qwen-plus"}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"！"},"finish_reason":"stop"}],"model":"qwen-plus"}

data: [DONE]
```

与 OpenAI 标准 SSE 格式完全一致，LlamaIndex `astream_chat()` 无需任何适配。

### 2.5 Qwen 特有参数

通过 OpenAI 兼容模式的 `extra_body` 传递:

| 参数 | 类型 | 说明 |
|------|------|------|
| `enable_search` | bool | 启用联网搜索增强，模型回答时参考实时网络信息 |
| `enable_thinking` | bool | 启用深度思考模式 (Qwen3 系列)，返回思考过程 |
| `search_options` | object | 搜索选项: `forced_search` (强制搜索), `search_strategy` |

**enable_thinking 示例**:

```json
{
    "model": "qwen3-max",
    "messages": [...],
    "extra_body": {
        "enable_thinking": true
    }
}
```

启用后响应中的 `message` 会包含 `reasoning_content` 字段:

```json
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "最终回答...",
            "reasoning_content": "让我思考一下这个问题..."
        }
    }]
}
```

### 2.6 Function Calling

DashScope 兼容 OpenAI Function Calling 规范:

```json
{
    "model": "qwen-plus",
    "messages": [...],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
}
```

---

## 3. LLM 模型矩阵

### 3.1 Qwen 系列可用模型

| 模型 | 上下文窗口 | 特点 | 适用场景 |
|------|-----------|------|----------|
| `qwen3-max` | 262K | 最强推理，支持 thinking | 复杂推理、代码生成 |
| `qwen-plus` | 1M | 性价比最优，长上下文 | **推荐默认选择** |
| `qwen-turbo` | 1M | 速度最快，成本最低 | 简单对话、分类 |
| `qwen-max` | 32K | 旧版旗舰 | 一般用途 |
| `qwen-max-latest` | 131K | max 系列最新版 | 一般用途 |
| `qwen-long` | 10M | 超长上下文 | 长文档分析 |

### 3.2 定价参考 (截至 2025 年)

| 模型 | 输入 (元/百万 tokens) | 输出 (元/百万 tokens) |
|------|----------------------|----------------------|
| qwen3-max | 2.0 | 8.0 |
| qwen-plus | 0.8 | 2.0 |
| qwen-turbo | 0.3 | 0.6 |
| qwen-max | 2.0 | 6.0 |
| qwen-long | 0.5 | 2.0 |

### 3.3 模型选型建议

对于 newbee-notebook 项目:

- **默认推荐**: `qwen-plus` — 性价比最优，1M 上下文窗口足够覆盖长文档 RAG 场景
- **复杂推理**: `qwen3-max` — 需要深度思考时切换
- **低成本**: `qwen-turbo` — 简单对话、测试环境

---

## 4. Embedding API

### 4.1 文本 Embedding (OpenAI 兼容模式)

**端点**:

```
POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
```

**请求**:

```json
{
    "model": "text-embedding-v4",
    "input": ["第一段文本", "第二段文本"],
    "dimensions": 1024,
    "encoding_format": "float"
}
```

**响应**:

```json
{
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "index": 0,
            "embedding": [0.0123, -0.0456, ...]
        },
        {
            "object": "embedding",
            "index": 1,
            "embedding": [0.0789, -0.0321, ...]
        }
    ],
    "model": "text-embedding-v4",
    "usage": {
        "prompt_tokens": 10,
        "total_tokens": 10
    }
}
```

**关键参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名，如 `text-embedding-v4` |
| `input` | string/array | 输入文本，最多 6 条 |
| `dimensions` | int | 输出维度，`text-embedding-v4` 支持 32-1024 |
| `encoding_format` | string | `float` 或 `base64` |

### 4.2 多模态 Embedding (DashScope 原生 API)

**重要**: 多模态 Embedding API 不走 OpenAI 兼容端点，使用 DashScope 原生 API。

**端点**:

```
POST https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding
```

**请求 Header**:

```
Authorization: Bearer sk-xxx
Content-Type: application/json
X-DashScope-DataInspection: enable  (可选，内容安全检测)
```

**请求体 — 纯文本**:

```json
{
    "model": "qwen3-vl-embedding",
    "input": {
        "contents": [
            {"text": "这是一段用于检索的文本"}
        ]
    },
    "parameters": {
        "dimension": 1024
    }
}
```

**请求体 — 图片+文本**:

```json
{
    "model": "qwen3-vl-embedding",
    "input": {
        "contents": [
            {
                "text": "一只在草地上奔跑的金毛犬",
                "image": "https://example.com/golden-retriever.jpg"
            }
        ]
    },
    "parameters": {
        "dimension": 1024
    }
}
```

**请求体 — 纯图片**:

```json
{
    "model": "qwen3-vl-embedding",
    "input": {
        "contents": [
            {
                "image": "https://example.com/figure1.png"
            }
        ]
    },
    "parameters": {
        "dimension": 1024
    }
}
```

**响应**:

```json
{
    "output": {
        "embeddings": [
            {
                "embedding": [0.0123, -0.0456, ...],
                "index": 0
            }
        ]
    },
    "usage": {
        "total_tokens": 52,
        "image_tokens": 40,
        "text_tokens": 12
    },
    "request_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**图片输入格式**:
- URL: 公网可访问的 HTTP/HTTPS 图片链接
- Base64: `data:image/jpeg;base64,/9j/4AAQ...`
- 支持格式: JPEG, PNG, WEBP, BMP, TIFF
- 图片大小限制: 不超过 10MB

**视频输入格式**:
- URL: 公网可访问的视频链接
- 支持格式: MP4, MOV, AVI
- 视频时长限制: 不超过 5 分钟

### 4.3 DashScope Python SDK 调用 (多模态)

```python
import dashscope
from dashscope import MultiModalEmbedding

dashscope.api_key = "sk-xxx"

# 纯文本
response = MultiModalEmbedding.call(
    model="qwen3-vl-embedding",
    input=[{"text": "检索文本"}],
    dimension=1024,
)
embedding = response.output["embeddings"][0]["embedding"]

# 图片+文本
response = MultiModalEmbedding.call(
    model="qwen3-vl-embedding",
    input=[{
        "text": "图片描述",
        "image": "https://example.com/image.jpg"
    }],
    dimension=1024,
)
```

---

## 5. Embedding 模型矩阵

### 5.1 文本 Embedding

| 模型名 (API) | 本地模型 | 最大 token | 维度范围 | 语言 |
|--------------|---------|-----------|----------|------|
| `text-embedding-v4` | - | 8192 | 32-1024 | 中英多语言 |
| `text-embedding-v3` | - | 8192 | 32-1024 | 中英多语言 |
| - | `Qwen3-Embedding-0.6B` | 32768 | 32-1024 | 中英多语言 |

### 5.2 多模态 Embedding

| 模型名 (API) | 本地模型 | 维度范围 | 输入类型 |
|--------------|---------|----------|---------|
| `qwen3-vl-embedding` | - | 256-2560 | 文本+图片+视频 |
| - | `Qwen3-VL-Embedding-2B` | 64-2048 | 文本+图片 |

### 5.3 定价参考

| 模型 | 单价 (元/百万 tokens) |
|------|---------------------|
| text-embedding-v4 | 0.7 |
| text-embedding-v3 | 0.7 |
| qwen3-vl-embedding | 1.0 |

---

## 6. 错误处理

### 6.1 常见错误码

| HTTP 状态码 | 错误码 | 说明 | 处理方式 |
|------------|--------|------|---------|
| 400 | `InvalidParameter` | 参数错误 | 检查请求参数 |
| 401 | `Unauthorized` | API Key 无效 | 检查 DASHSCOPE_API_KEY |
| 403 | `AccessDenied` | 无权限访问模型 | 检查模型是否已开通 |
| 429 | `Throttling` | 请求频率超限 | 重试 + 退避 |
| 500 | `InternalError` | 服务内部错误 | 重试 |

### 6.2 重试策略

```python
# LlamaIndex OpenAI 类已内置重试机制
# max_retries 参数控制最大重试次数
# 默认使用指数退避策略

llm = QwenOpenAI(
    model="qwen-plus",
    max_retries=3,    # 最多重试 3 次
    timeout=60.0,     # 单次请求超时 60 秒
)
```

### 6.3 速率限制

| 模型 | QPM (每分钟请求数) | TPM (每分钟 token 数) |
|------|-------------------|---------------------|
| qwen-plus | 500 | 500,000 |
| qwen-turbo | 1000 | 1,000,000 |
| qwen-max | 300 | 300,000 |
| text-embedding-v4 | 1000 | - |

> 以上为默认限额，可通过控制台申请提升。

---

## 7. SDK 使用概览

### 7.1 OpenAI SDK (LLM + 文本 Embedding)

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxx",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# Chat
response = client.chat.completions.create(
    model="qwen-plus",
    messages=[{"role": "user", "content": "你好"}],
    stream=True,
)

# Embedding
response = client.embeddings.create(
    model="text-embedding-v4",
    input=["文本1", "文本2"],
    dimensions=1024,
)
```

### 7.2 DashScope SDK (多模态 Embedding)

```python
import dashscope
from dashscope import MultiModalEmbedding

dashscope.api_key = "sk-xxx"

response = MultiModalEmbedding.call(
    model="qwen3-vl-embedding",
    input=[{"text": "文本", "image": "https://example.com/img.jpg"}],
    dimension=1024,
)
```

### 7.3 项目中的使用方式

在 improve-7 的实现中:

- **LLM (QwenOpenAI)**: 通过 LlamaIndex `OpenAI` 类 + `api_base` 间接使用 OpenAI SDK，不直接调用
- **文本 Embedding API 模式**: 通过 OpenAI SDK 直接调用 `/v1/embeddings`
- **文本 Embedding 本地模式**: 通过 `sentence-transformers` 加载本地模型，不调用 API
- **多模态 Embedding API 模式**: 通过 `dashscope` SDK 调用原生 API
- **多模态 Embedding 本地模式**: 通过 `transformers` 加载本地模型，不调用 API
