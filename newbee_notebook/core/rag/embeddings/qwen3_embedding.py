"""Qwen3 embedding provider (local/API text embedding)."""

import logging
import os
from typing import List, Any, Optional, Dict

import numpy as np
import torch

from newbee_notebook.core.common.config import get_embeddings_config
from newbee_notebook.core.rag.embeddings.base import BaseEmbeddingModel
from newbee_notebook.core.rag.embeddings.registry import register_embedding


logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

ENV_QWEN3_MODE = "QWEN3_EMBEDDING_MODE"
ENV_QWEN3_MODEL_PATH = "QWEN3_EMBEDDING_MODEL_PATH"
ENV_QWEN3_DEVICE = "QWEN3_EMBEDDING_DEVICE"
ENV_QWEN3_MAX_LENGTH = "QWEN3_EMBEDDING_MAX_LENGTH"
ENV_QWEN3_DIM = "QWEN3_EMBEDDING_DIM"
ENV_QWEN3_BATCH_SIZE = "QWEN3_EMBEDDING_BATCH_SIZE"
ENV_QWEN3_API_MODEL = "QWEN3_EMBEDDING_API_MODEL"
ENV_QWEN3_API_BASE = "QWEN3_EMBEDDING_API_BASE"


def _resolve_torch_device(device: str) -> str:
    """Resolve requested device with safe fallback.

    Supports:
    - auto/empty: CUDA if available, otherwise CPU
    - cuda/cuda:0/...: fall back to CPU when CUDA is unavailable
    - mps: fall back to CPU when MPS is unavailable
    """
    requested = (device or "").strip().lower()
    if requested in {"", "auto"}:
        return "cuda" if torch.cuda.is_available() else "cpu"

    if requested.startswith("cuda") and not torch.cuda.is_available():
        logger.warning(
            "Qwen3 embedding configured to use '%s', but CUDA is unavailable; falling back to CPU.",
            device,
        )
        return "cpu"

    if requested == "mps":
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is None or not mps_backend.is_available():
            logger.warning(
                "Qwen3 embedding configured to use '%s', but MPS is unavailable; falling back to CPU.",
                device,
            )
            return "cpu"

    return requested


class Qwen3LocalEmbedding(BaseEmbeddingModel):
    """Qwen3 local text embedding based on sentence-transformers."""

    def __init__(
        self,
        model_path: str = "models/Qwen3-Embedding-0.6B",
        dim: int = 1024,
        device: str = "cpu",
        max_length: int = 8192,
        embed_batch_size: int = 32,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=f"qwen3-embedding-{int(dim)}d", **kwargs)
        self._model_path = model_path
        self._dim = int(dim)
        self._device = _resolve_torch_device(device)
        self._max_length = int(max_length)
        self._embed_batch_size = max(int(embed_batch_size), 1)

        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(
                model_path,
                device=self._device,
                trust_remote_code=True,
                local_files_only=True,
            )
        except Exception:
            # Fallback for model IDs or partially cached paths.
            self._model = SentenceTransformer(
                model_path,
                device=self._device,
                trust_remote_code=True,
            )
        # Cap max sequence length at runtime.
        self._model.max_seq_length = self._max_length

    @property
    def dimensions(self) -> int:
        return self._dim

    def _encode(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts,
            batch_size=self._embed_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        if embeddings.shape[1] < self._dim:
            raise ValueError(
                f"Qwen3 embedding output dim {embeddings.shape[1]} is less than configured "
                f"target dim {self._dim}."
            )

        if embeddings.shape[1] > self._dim:
            # For smaller target dimensions, truncate and re-normalize.
            embeddings = embeddings[:, : self._dim]
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.clip(norms, 1e-10, None)

        return embeddings.tolist()

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._encode(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._encode([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._encode([text])[0]


class Qwen3APIEmbedding(BaseEmbeddingModel):
    """Qwen text embedding via DashScope OpenAI-compatible embeddings API."""

    def __init__(
        self,
        model: str = "text-embedding-v4",
        dim: int = 1024,
        api_key: Optional[str] = None,
        api_base: str = DEFAULT_DASHSCOPE_BASE,
        embed_batch_size: int = 32,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=f"qwen3-api-{model}-{int(dim)}d", **kwargs)
        self._model_name_str = model
        self._dim = int(dim)
        self._embed_batch_size = max(int(embed_batch_size), 1)

        from openai import OpenAI

        resolved_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "DASHSCOPE_API_KEY not set for qwen3-embedding API mode."
            )

        self._client = OpenAI(
            api_key=resolved_key,
            base_url=api_base,
        )

    @property
    def dimensions(self) -> int:
        return self._dim

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        all_embeddings: List[List[float]] = []
        for start in range(0, len(texts), self._embed_batch_size):
            batch = texts[start: start + self._embed_batch_size]
            response = self._client.embeddings.create(
                model=self._model_name_str,
                input=batch,
                dimensions=self._dim,
                encoding_format="float",
            )
            all_embeddings.extend(item.embedding for item in response.data)
        return all_embeddings

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._call_api([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._call_api([text])[0]


def _get_qwen3_embedding_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("qwen3-embedding", {})


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer value for %s=%r, using default %s", name, raw, default)
        return default


@register_embedding("qwen3-embedding")
def build_qwen3_embedding(mode: Optional[str] = None) -> BaseEmbeddingModel:
    """Build qwen3 embedding model from config."""
    cfg = _get_qwen3_embedding_config()
    final_mode = (mode or os.getenv(ENV_QWEN3_MODE) or cfg.get("mode", "local")).strip().lower()
    dim = _get_int_env(ENV_QWEN3_DIM, int(cfg.get("dim", 1024)))
    embed_batch_size = _get_int_env(ENV_QWEN3_BATCH_SIZE, int(cfg.get("embed_batch_size", 32)))

    if final_mode == "api":
        return Qwen3APIEmbedding(
            model=os.getenv(ENV_QWEN3_API_MODEL, cfg.get("api_model", "text-embedding-v4")),
            dim=dim,
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            api_base=os.getenv(ENV_QWEN3_API_BASE, cfg.get("api_base", DEFAULT_DASHSCOPE_BASE)),
            embed_batch_size=embed_batch_size,
        )

    if final_mode != "local":
        raise ValueError(
            f"Unsupported qwen3-embedding mode '{final_mode}'. Expected 'local' or 'api'."
        )

    model_path = cfg.get("model_path", "models/Qwen3-Embedding-0.6B")
    return Qwen3LocalEmbedding(
        model_path=os.getenv(ENV_QWEN3_MODEL_PATH, model_path),
        dim=dim,
        device=os.getenv(ENV_QWEN3_DEVICE, cfg.get("device", "auto")),
        max_length=_get_int_env(ENV_QWEN3_MAX_LENGTH, int(cfg.get("max_length", 8192))),
        embed_batch_size=embed_batch_size,
    )


# Backward-compatible naming style
build_embedding = build_qwen3_embedding
