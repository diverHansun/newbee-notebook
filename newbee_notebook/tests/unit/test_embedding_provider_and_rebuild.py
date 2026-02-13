import asyncio

from newbee_notebook.core.rag.embeddings import qwen3_embedding
from newbee_notebook.scripts import rebuild_pgvector


def test_qwen3_resolve_torch_device_fallback_to_cpu(monkeypatch):
    monkeypatch.setattr(qwen3_embedding.torch.cuda, "is_available", lambda: False)
    assert qwen3_embedding._resolve_torch_device("cuda") == "cpu"
    assert qwen3_embedding._resolve_torch_device("auto") == "cpu"


def test_qwen3_resolve_torch_device_auto_uses_cuda_when_available(monkeypatch):
    monkeypatch.setattr(qwen3_embedding.torch.cuda, "is_available", lambda: True)
    assert qwen3_embedding._resolve_torch_device("auto") == "cuda"


def test_build_qwen3_embedding_local_uses_env_overrides(monkeypatch):
    captured_kwargs = {}

    class DummyLocalEmbedding:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(
        qwen3_embedding,
        "_get_qwen3_embedding_config",
        lambda: {
            "mode": "local",
            "model_path": "models/Qwen3-Embedding-0.6B",
            "device": "cpu",
            "max_length": 8192,
            "dim": 1024,
            "embed_batch_size": 32,
        },
    )
    monkeypatch.setattr(qwen3_embedding, "Qwen3LocalEmbedding", DummyLocalEmbedding)
    monkeypatch.setenv("QWEN3_EMBEDDING_DEVICE", "cuda")
    monkeypatch.setenv("QWEN3_EMBEDDING_BATCH_SIZE", "16")

    qwen3_embedding.build_qwen3_embedding(mode="local")

    assert captured_kwargs["device"] == "cuda"
    assert captured_kwargs["embed_batch_size"] == 16


def test_build_qwen3_embedding_api_uses_env_overrides(monkeypatch):
    captured_kwargs = {}

    class DummyAPIEmbedding:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(
        qwen3_embedding,
        "_get_qwen3_embedding_config",
        lambda: {
            "mode": "api",
            "api_model": "text-embedding-v4",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "dim": 1024,
            "embed_batch_size": 32,
        },
    )
    monkeypatch.setattr(qwen3_embedding, "Qwen3APIEmbedding", DummyAPIEmbedding)
    monkeypatch.setenv("QWEN3_EMBEDDING_API_MODEL", "text-embedding-v4")
    monkeypatch.setenv("QWEN3_EMBEDDING_BATCH_SIZE", "8")

    qwen3_embedding.build_qwen3_embedding(mode="api")

    assert captured_kwargs["model"] == "text-embedding-v4"
    assert captured_kwargs["embed_batch_size"] == 8


def test_rebuild_pgvector_uses_registry_builder(monkeypatch):
    call_args = {}

    class DummyEmbed:
        dimensions = 1024
        model_name = "qwen3-embedding-1024d"

    class DummyStore:
        async def initialize(self):
            return None

        async def clear(self):
            return None

        def get_llamaindex_store(self):
            return object()

    class DummyBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def load_and_parse_documents(self, *args, **kwargs):
            return []

    def fake_get_builder(provider):
        call_args["provider"] = provider
        return lambda: DummyEmbed()

    monkeypatch.setattr(rebuild_pgvector, "get_builder", fake_get_builder)
    monkeypatch.setattr(rebuild_pgvector, "get_storage_config", lambda: {"postgresql": {}})
    monkeypatch.setattr(
        rebuild_pgvector,
        "get_pgvector_config_for_provider",
        lambda _provider: {
            "table_name": "documents_qwen3_embedding",
            "embedding_dimension": 1024,
        },
    )
    monkeypatch.setattr(rebuild_pgvector, "PGVectorStore", lambda _config: DummyStore())
    monkeypatch.setattr(rebuild_pgvector, "IndexBuilder", DummyBuilder)
    monkeypatch.setattr(rebuild_pgvector, "VectorStoreIndex", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        rebuild_pgvector.StorageContext,
        "from_defaults",
        lambda **kwargs: object(),
    )

    asyncio.run(
        rebuild_pgvector.rebuild_pgvector_index(
            documents_dir="data/documents",
            clear_only=False,
            provider="qwen3-embedding",
        )
    )

    assert call_args["provider"] == "qwen3-embedding"
