"""Serve the existing local Qwen3 embedding implementation on loopback."""

from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    dimensions: int = Field(default=1024, ge=1)
    encoding_format: Literal["float"] = "float"


def create_app(encode, model_name: str, dimensions: int) -> FastAPI:
    app = FastAPI(title="Newbee local embeddings")
    lock = Lock()

    @app.get("/health")
    def health():
        return {"status": "ok", "model": model_name, "dimensions": dimensions}

    @app.post("/v1/embeddings")
    def embed(request: EmbeddingRequest):
        if request.model != model_name:
            raise HTTPException(400, "Requested model is not loaded")
        if request.dimensions != dimensions:
            raise HTTPException(400, "Dimensions must match the local service configuration")
        texts = [request.input] if isinstance(request.input, str) else request.input
        if not 1 <= len(texts) <= 32 or any(not text.strip() or len(text) > 100_000 for text in texts):
            raise HTTPException(400, "Expected 1–32 nonempty texts of at most 100000 characters each")
        # Serialize inference to bound unified-memory usage across API/worker requests.
        with lock:
            vectors = encode(texts)
        return {
            "object": "list", "model": model_name,
            "data": [{"object": "embedding", "index": i, "embedding": vector} for i, vector in enumerate(vectors)],
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=Path("models/Qwen3-Embedding-0.6B"))
    parser.add_argument("--device", default="auto", choices=("auto", "mps", "cuda", "cpu"))
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=8192)
    args = parser.parse_args()
    if not args.model_path.is_dir():
        parser.error("Download the local model before starting the service")

    import uvicorn
    from newbee_notebook.core.local_embeddings import encode_qwen3, load_qwen3_model, resolve_torch_device

    device = resolve_torch_device(args.device)
    model = load_qwen3_model(str(args.model_path.resolve()), device, args.max_length)
    encode = partial(encode_qwen3, model, batch_size=args.batch_size, dim=args.dimensions)
    print(f"Loaded {args.model_path.name} on {device}", flush=True)
    uvicorn.run(
        create_app(encode, args.model_path.name, args.dimensions), host="127.0.0.1", port=args.port,
    )


if __name__ == "__main__":
    main()
