# Embedding 模型扩展: Qwen3-Embedding 与 Qwen3-VL-Embedding

本文档描述 Embedding 模块新增 Qwen3-Embedding (文本) 和 Qwen3-VL-Embedding (多模态) 两个供应商的设计方案。

---

## 1. 新增模型概览

### 1.1 模型矩阵

| 模型 | 类型 | 使用方式 | 参数量 | 输入类型 | 维度范围 | 统一维度 |
|------|------|----------|--------|----------|----------|----------|
| Qwen3-Embedding-0.6B | 文本 | 本地 (models/) | 0.6B | 纯文本 | 32-1024 | 1024 |
| qwen3-embedding | 文本 | API (百炼) | - | 纯文本 | 32-1024 | 1024 |
| Qwen3-VL-Embedding-2B | 多模态 | 本地 (models/) | 2B | 文本+图片 | 64-2048 | 1024 |
| qwen3-vl-embedding | 多模态 | API (百炼) | - | 文本+图片+视频 | 256-2560 | 1024 |

### 1.2 与现有模型的对比

| 模型 | 中文能力 | 最大上下文 | 维度 | 适用场景 |
|------|----------|----------|------|----------|
| BioBERT (弃用) | 不支持 | 512 tokens | 768 | 生物医学英文 |
| 智谱 embedding-3 (保留) | 良好 | API 限制 | 1024 | 通用中英文 |
| **Qwen3-Embedding-0.6B** | 优秀 | 32K tokens | 1024 | 通用中英文，本地轻量 |
| **qwen3-vl-embedding** | 优秀 | 32K tokens | 1024 | 多模态检索 (图片+文本) |

---

## 2. Qwen3-Embedding: 文本 Embedding

### 2.1 本地模式 (Qwen3-Embedding-0.6B)

**模型下载**:

```bash
cd newbee-notebook
git lfs install
git clone https://huggingface.co/Qwen/Qwen3-Embedding-0.6B models/Qwen3-Embedding-0.6B
```

**目录结构**:

```
models/
├── biobert-v1.1/                # 现有 (弃用)
├── Qwen3-Embedding-0.6B/       # 新增: 文本 embedding
│   ├── config.json
│   ├── model.safetensors
│   ├── tokenizer.json
│   └── ...
└── Qwen3-VL-Embedding-2B/      # 新增: 多模态 embedding (可选)
```

**CPU 推理特性**:

| 指标 | Qwen3-Embedding-0.6B | BioBERT-v1.1 (参考) |
|------|----------------------|---------------------|
| 模型大小 | ~1.2 GB | ~0.4 GB |
| 内存占用 | ~1.5-2 GB | ~0.8 GB |
| CPU 推理速度 | ~50-100ms/句 | ~20-40ms/句 |
| 上下文长度 | 32K tokens | 512 tokens |

0.6B 参数量在 CPU 上可接受，适合开发环境。

### 2.2 实现: QwenEmbedding

```python
# core/rag/embeddings/qwen_embedding.py

"""Qwen3-Embedding wrapper for local and API modes.

本地模式: 使用 sentence-transformers 加载 Qwen3-Embedding-0.6B
API 模式: 通过 DashScope OpenAI 兼容端点调用 qwen3-embedding
"""

import logging
from typing import List, Any, Optional, Dict

from .base import BaseEmbeddingModel
from .registry import register_embedding
from newbee_notebook.core.common.config import get_embeddings_config

logger = logging.getLogger(__name__)


class QwenLocalEmbedding(BaseEmbeddingModel):
    """Qwen3-Embedding 本地推理。

    使用 sentence-transformers 库加载模型，支持 MRL 自定义维度。
    """

    def __init__(
        self,
        model_path: str = "models/Qwen3-Embedding-0.6B",
        dim: int = 1024,
        device: str = "cpu",
        max_length: int = 8192,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_path = model_path
        self._dim = dim
        self._device = device
        self._max_length = max_length

        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(
            model_path,
            device=device,
            trust_remote_code=True,
        )

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return f"qwen3-embedding-{self._dim}d"

    def _encode(self, texts: List[str]) -> List[List[float]]:
        """统一编码方法，支持 MRL 维度截断。"""
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # MRL: 截断到目标维度
        if embeddings.shape[1] > self._dim:
            embeddings = embeddings[:, :self._dim]
            # 重新 L2 归一化
            import numpy as np
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.clip(norms, 1e-10, None)

        return embeddings.tolist()

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._encode(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._encode([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._encode([text])[0]


class QwenAPIEmbedding(BaseEmbeddingModel):
    """Qwen Embedding 通过 DashScope OpenAI 兼容 API 调用。

    使用 OpenAI SDK 的 embeddings.create() 方法。
    """

    def __init__(
        self,
        model: str = "text-embedding-v4",
        dim: int = 1024,
        api_key: Optional[str] = None,
        api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model = model
        self._dim = dim

        import os
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY"),
            base_url=api_base,
        )

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return f"qwen-api-{self._model}-{self._dim}d"

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dim,
        )
        return [item.embedding for item in response.data]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._call_api([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._call_api([text])[0]


def _get_qwen_embedding_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("qwen-embedding", {})


@register_embedding("qwen-embedding")
def build_qwen_embedding(
    mode: Optional[str] = None,
) -> BaseEmbeddingModel:
    """Factory for Qwen Embedding, supporting local and API modes.

    mode 优先级: 参数 > yaml 配置 > 默认 'local'
    """
    cfg = _get_qwen_embedding_config()
    final_mode = mode or cfg.get("mode", "local")

    if final_mode == "api":
        import os
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not set for qwen-embedding API mode.")
        return QwenAPIEmbedding(
            model=cfg.get("api_model", "text-embedding-v4"),
            dim=cfg.get("dim", 1024),
            api_key=api_key,
            api_base=cfg.get("api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
    else:
        model_path = cfg.get("model_path", "models/Qwen3-Embedding-0.6B")
        return QwenLocalEmbedding(
            model_path=model_path,
            dim=cfg.get("dim", 1024),
            device=cfg.get("device", "cpu"),
            max_length=cfg.get("max_length", 8192),
        )
```

---

## 3. Qwen3-VL-Embedding: 多模态 Embedding

### 3.1 API 模式 (qwen3-vl-embedding)

**关键区别**: qwen3-vl-embedding 的 API **不走** OpenAI 兼容端点，而是使用 DashScope 原生 `MultiModalEmbedding` API。

**API 端点**:

```
POST https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding
```

**请求体结构**:

```json
{
    "model": "qwen3-vl-embedding",
    "input": [
        {
            "text": "Find similar documents about neural networks",
            "image": "https://example.com/figure1.png"
        }
    ],
    "dimension": 1024
}
```

**支持的输入组合**:
- 纯文本: `{"text": "..."}`
- 纯图片: `{"image": "url_or_base64"}`
- 文本+图片: `{"text": "...", "image": "..."}`
- 文本+视频: `{"text": "...", "video": "..."}`
- 图片格式: JPEG, PNG, WEBP, BMP, TIFF
- 视频格式: MP4, MOV, AVI

### 3.2 本地模式 (Qwen3-VL-Embedding-2B)

**模型下载**:

```bash
git clone https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B models/Qwen3-VL-Embedding-2B
```

**CPU 环境注意**: 2B 参数的 VL 模型在 CPU 上推理较慢 (~500ms-1s/次)，图片处理更耗资源。建议:
- 日常开发: 使用 API 模式
- 本地测试: 仅用于验证功能，不用于批量处理

### 3.3 实现: QwenVLEmbedding

```python
# core/rag/embeddings/qwen_vl_embedding.py

"""Qwen3-VL-Embedding wrapper for multimodal retrieval.

API 模式: 通过 DashScope 原生 MultiModalEmbedding API 调用
本地模式: 使用 transformers 加载 Qwen3-VL-Embedding-2B
"""

import logging
from typing import List, Any, Optional, Dict

from .base import BaseEmbeddingModel
from .registry import register_embedding
from newbee_notebook.core.common.config import get_embeddings_config

logger = logging.getLogger(__name__)


class QwenVLAPIEmbedding(BaseEmbeddingModel):
    """Qwen3-VL-Embedding 通过 DashScope 原生 API 调用。

    注意: 此模型使用 DashScope 原生 MultiModalEmbedding API，
    而非 OpenAI 兼容 /v1/embeddings 端点。
    需要安装 dashscope SDK: pip install dashscope
    """

    def __init__(
        self,
        model: str = "qwen3-vl-embedding",
        dim: int = 1024,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_name_str = model
        self._dim = dim

        import os
        import dashscope
        dashscope.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return f"qwen-vl-api-{self._dim}d"

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed pure text inputs via MultiModalEmbedding API."""
        import dashscope
        from dashscope import MultiModalEmbedding

        results = []
        for text in texts:
            response = MultiModalEmbedding.call(
                model=self._model_name_str,
                input=[{"text": text}],
                dimension=self._dim,
            )
            embedding = response.output["embeddings"][0]["embedding"]
            results.append(embedding)
        return results

    def embed_image(self, image_url: str, text: Optional[str] = None) -> List[float]:
        """Embed an image (optionally with text) for multimodal retrieval.

        Args:
            image_url: 图片 URL 或 Base64 数据
            text: 可选的文本描述，与图片一起编码

        Returns:
            Embedding vector
        """
        import dashscope
        from dashscope import MultiModalEmbedding

        input_data = {"image": image_url}
        if text:
            input_data["text"] = text

        response = MultiModalEmbedding.call(
            model=self._model_name_str,
            input=[input_data],
            dimension=self._dim,
        )
        return response.output["embeddings"][0]["embedding"]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._embed_texts(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed_texts([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed_texts([text])[0]


class QwenVLLocalEmbedding(BaseEmbeddingModel):
    """Qwen3-VL-Embedding-2B 本地推理。

    注意: 2B 模型在 CPU 上推理较慢，建议仅用于功能验证。
    """

    def __init__(
        self,
        model_path: str = "models/Qwen3-VL-Embedding-2B",
        dim: int = 1024,
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_path = model_path
        self._dim = dim
        self._device = device

        from transformers import AutoModel, AutoProcessor
        import torch

        self._processor = AutoProcessor.from_pretrained(
            model_path, trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            model_path, trust_remote_code=True, torch_dtype=torch.float32
        )
        self._model.to(device)
        self._model.eval()

    @property
    def dimensions(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return f"qwen-vl-local-{self._dim}d"

    def _encode_texts(self, texts: List[str]) -> List[List[float]]:
        import torch
        import numpy as np

        embeddings = []
        for text in texts:
            inputs = self._processor(
                text=text, return_tensors="pt"
            ).to(self._device)
            with torch.no_grad():
                outputs = self._model(**inputs)
                emb = outputs.last_hidden_state[:, -1, :]  # EOS token
                # 截断到目标维度
                emb = emb[:, :self._dim]
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            embeddings.append(emb.cpu().numpy()[0].tolist())
        return embeddings

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._encode_texts(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._encode_texts([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._encode_texts([text])[0]


def _get_vl_embedding_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("qwen-vl-embedding", {})


@register_embedding("qwen-vl-embedding")
def build_qwen_vl_embedding(
    mode: Optional[str] = None,
) -> BaseEmbeddingModel:
    """Factory for Qwen VL Embedding.

    mode: 'api' (推荐) 或 'local'
    """
    cfg = _get_vl_embedding_config()
    final_mode = mode or cfg.get("mode", "api")

    if final_mode == "api":
        import os
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY not set for qwen-vl-embedding API mode.")
        return QwenVLAPIEmbedding(
            model=cfg.get("model", "qwen3-vl-embedding"),
            dim=cfg.get("dim", 1024),
            api_key=api_key,
        )
    else:
        return QwenVLLocalEmbedding(
            model_path=cfg.get("model_path", "models/Qwen3-VL-Embedding-2B"),
            dim=cfg.get("dim", 1024),
            device=cfg.get("device", "cpu"),
        )
```

---

## 4. embeddings.yaml 改造

```yaml
# configs/embeddings.yaml

embeddings:
  # Provider selection: 'qwen-embedding', 'qwen-vl-embedding', 'zhipu', 'biobert'
  # 可通过环境变量 EMBEDDING_PROVIDER 覆盖
  provider: qwen-embedding

  # ---- Qwen3 文本 Embedding ---- (新增，推荐)
  qwen-embedding:
    enabled: true
    mode: local                       # 'local' 或 'api'
    # 本地模式配置
    model_path: models/Qwen3-Embedding-0.6B
    device: cpu                       # 'cpu', 'cuda', 'auto'
    max_length: 8192
    dim: 1024                         # MRL 自定义维度，统一 1024
    # API 模式配置
    api_model: text-embedding-v4      # DashScope 上的文本 embedding 模型名
    api_base: https://dashscope.aliyuncs.com/compatible-mode/v1

  # ---- Qwen3 多模态 VL Embedding ---- (新增)
  qwen-vl-embedding:
    enabled: true
    mode: api                         # 推荐 API 模式 (CPU 环境本地推理较慢)
    model: qwen3-vl-embedding         # DashScope 上的 API 模型名
    dim: 1024                         # 统一维度
    # 本地模式配置 (可选)
    model_path: models/Qwen3-VL-Embedding-2B
    device: cpu

  # ---- ZhipuAI Embedding ---- (保留)
  zhipu:
    enabled: true
    model: embedding-3
    dim: 1024

  # ---- BioBERT ---- (弃用，保留代码以备回退)
  biobert:
    enabled: false
    model_path: models/biobert-v1.1
    normalize: true
    dim: 768
    device: cpu
    embed_batch_size: 15
```

---

## 5. __init__.py 改造

```python
# core/rag/embeddings/__init__.py (新增 import)

# Import provider modules to trigger @register_embedding decorators
from newbee_notebook.core.rag.embeddings import biobert          # noqa: F401
from newbee_notebook.core.rag.embeddings import zhipu            # noqa: F401
from newbee_notebook.core.rag.embeddings import qwen_embedding   # noqa: F401  (新增)
from newbee_notebook.core.rag.embeddings import qwen_vl_embedding  # noqa: F401  (新增)
```

---

## 6. 依赖管理

### 6.1 新增 Python 依赖

```
# requirements.txt 新增

# Qwen3-Embedding 本地推理
sentence-transformers>=3.0.0

# Qwen3-VL-Embedding API 模式
dashscope>=1.20.0

# Qwen3-VL-Embedding 本地推理 (可选)
# transformers>=4.45.0  (已有)
# torch>=2.0            (已有)
```

### 6.2 依赖说明

| 依赖 | 用途 | 必需性 |
|------|------|--------|
| `sentence-transformers` | Qwen3-Embedding-0.6B 本地推理 | qwen-embedding local 模式必需 |
| `dashscope` | Qwen3-VL-Embedding API 调用 | qwen-vl-embedding api 模式必需 |
| `openai` | Qwen embedding API (兼容模式) | qwen-embedding api 模式必需 (已有) |

---

## 7. 需要新增/修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/rag/embeddings/qwen_embedding.py` | 新增 | QwenLocalEmbedding + QwenAPIEmbedding |
| `core/rag/embeddings/qwen_vl_embedding.py` | 新增 | QwenVLAPIEmbedding + QwenVLLocalEmbedding |
| `core/rag/embeddings/__init__.py` | 修改 | 新增 import 触发注册 |
| `configs/embeddings.yaml` | 修改 | 新增 qwen-embedding 和 qwen-vl-embedding sections |
| `requirements.txt` | 修改 | 新增 sentence-transformers, dashscope |
| `.env.example` | 修改 | 新增 DASHSCOPE_API_KEY |
