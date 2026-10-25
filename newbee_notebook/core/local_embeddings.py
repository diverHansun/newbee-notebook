"""Small shared local embedding runtime, independent of the RAG application."""

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)


def resolve_torch_device(device: str) -> str:
    """Resolve requested device with safe fallback.

    Supports:
    - auto/empty: CUDA, then Apple MPS, otherwise CPU
    - cuda/cuda:0/...: fall back to CPU when CUDA is unavailable
    - mps: fall back to CPU when MPS is unavailable
    """
    requested = (device or "").strip().lower()
    if requested in {"", "auto"}:
        if torch.cuda.is_available():
            return "cuda"
        mps_backend = getattr(torch.backends, "mps", None)
        return "mps" if mps_backend is not None and mps_backend.is_available() else "cpu"

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



def load_qwen3_model(model_path: str, device: str, max_length: int):
    from sentence_transformers import SentenceTransformer

    try:
        model = SentenceTransformer(model_path, device=device, trust_remote_code=True, local_files_only=True)
    except Exception:
        # Preserve the existing native Windows/model-ID download fallback.
        model = SentenceTransformer(model_path, device=device, trust_remote_code=True)
    model.max_seq_length = max_length
    return model


def encode_qwen3(model, texts: list[str], *, batch_size: int, dim: int) -> list[list[float]]:
    embeddings = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True,
        show_progress_bar=False, convert_to_numpy=True,
    )
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)
    if embeddings.shape[1] < dim:
        raise ValueError(f"Qwen3 embedding output dim {embeddings.shape[1]} is less than configured target dim {dim}.")
    if embeddings.shape[1] > dim:
        embeddings = embeddings[:, :dim]
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, 1e-10, None)
    return embeddings.tolist()
