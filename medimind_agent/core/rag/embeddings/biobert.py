"""
BioBERT embedding wrapper.

Provides sentence embeddings using a locally cached or HF-hosted BioBERT model.
"""

import logging
from typing import List, Any, Optional, Dict
import torch
from transformers import AutoTokenizer, AutoModel

from .base import BaseEmbeddingModel
from .registry import register_embedding
from medimind_agent.core.common.config import get_embeddings_config

logger = logging.getLogger(__name__)


def _resolve_torch_device(device: str) -> str:
    """Resolve requested device and fallback safely when accelerator is unavailable."""
    requested = (device or "").strip().lower()
    if requested in {"", "auto"}:
        return "cuda" if torch.cuda.is_available() else "cpu"

    if requested.startswith("cuda") and not torch.cuda.is_available():
        logger.warning(
            "BioBERT configured to use '%s', but CUDA is unavailable; falling back to CPU.",
            device,
        )
        return "cpu"

    if requested == "mps":
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is None or not mps_backend.is_available():
            logger.warning(
                "BioBERT configured to use '%s', but MPS is unavailable; falling back to CPU.",
                device,
            )
            return "cpu"

    return requested


class BioBERTEmbedding(BaseEmbeddingModel):
    """BioBERT embedding model."""

    def __init__(
        self,
        model_name_or_path: str = "dmis-lab/biobert-v1.1",
        normalize: bool = True,
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_name_or_path = model_name_or_path
        self._normalize = normalize
        self._device = _resolve_torch_device(device)

        # Load tokenizer/model (prefer local cache, then fallback to HF Hub)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name_or_path,
                local_files_only=True,
            )
            self._model = AutoModel.from_pretrained(
                model_name_or_path,
                local_files_only=True,
            )
        except Exception:
            self._tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
            self._model = AutoModel.from_pretrained(model_name_or_path)

        self._model.to(self._device)
        self._model.eval()

    @property
    def dimensions(self) -> int:
        """Return embedding dimension (hidden size)."""
        return self._model.config.hidden_size

    @property
    def model_name(self) -> str:
        return f"biobert-{self._model.config.hidden_size}d"

    def _mean_pooling(
        self,
        last_hidden_state: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        sum_embeddings = torch.sum(last_hidden_state * mask_expanded, 1)
        sum_mask = torch.clamp(mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        encoded = {k: v.to(self._device) for k, v in encoded.items()}
        with torch.no_grad():
            outputs = self._model(**encoded)
            last_hidden_state = outputs.last_hidden_state

        embeddings = self._mean_pooling(last_hidden_state, encoded["attention_mask"])
        if self._normalize:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy().tolist()

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_text_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embeddings([text])[0]


def _get_biobert_config() -> Dict[str, Any]:
    embeddings_config = get_embeddings_config()
    return embeddings_config.get("embeddings", {}).get("biobert", {})


@register_embedding("biobert")
def build_biobert_embedding(
    model_path: Optional[str] = None,
    normalize: Optional[bool] = None,
    device: Optional[str] = None,
    embed_batch_size: Optional[int] = None,
) -> BioBERTEmbedding:
    """Factory for BioBERTEmbedding using values from embeddings.yaml when available."""
    cfg = _get_biobert_config()
    model_path = model_path or cfg.get("model_path", "models/biobert-v1.1")
    normalize = normalize if normalize is not None else cfg.get("normalize", True)
    device = device or cfg.get("device", "cpu")
    if embed_batch_size is None:
        embed_batch_size = cfg.get("embed_batch_size")

    kwargs: Dict[str, Any] = {}
    if embed_batch_size is not None:
        kwargs["embed_batch_size"] = int(embed_batch_size)

    return BioBERTEmbedding(
        model_name_or_path=model_path,
        normalize=normalize,
        device=device,
        **kwargs,
    )
