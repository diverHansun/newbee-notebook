import asyncio

from newbee_notebook.core.rag.embeddings import biobert
from newbee_notebook.scripts import rebuild_pgvector


def test_resolve_torch_device_fallback_to_cpu(monkeypatch):
    monkeypatch.setattr(biobert.torch.cuda, "is_available", lambda: False)
    assert biobert._resolve_torch_device("cuda") == "cpu"
    assert biobert._resolve_torch_device("auto") == "cpu"


def test_resolve_torch_device_auto_uses_cuda_when_available(monkeypatch):
    monkeypatch.setattr(biobert.torch.cuda, "is_available", lambda: True)
    assert biobert._resolve_torch_device("auto") == "cuda"


def test_build_biobert_embedding_reads_embed_batch_size_from_config(monkeypatch):
    captured_kwargs = {}

    class DummyEmbedding:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(
        biobert,
        "_get_biobert_config",
        lambda: {
            "model_path": "models/biobert-v1.1",
            "normalize": True,
            "device": "cuda",
            "embed_batch_size": 32,
        },
    )
    monkeypatch.setattr(biobert, "BioBERTEmbedding", DummyEmbedding)

    biobert.build_biobert_embedding()

    assert captured_kwargs["device"] == "cuda"
    assert captured_kwargs["embed_batch_size"] == 32


def test_rebuild_pgvector_biobert_does_not_force_cpu(monkeypatch):
    call_args = {}

    class DummyEmbed:
        dimensions = 768

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

    def fake_build_biobert_embedding(*args, **kwargs):
        call_args["args"] = args
        call_args["kwargs"] = kwargs
        return DummyEmbed()

    monkeypatch.setattr(rebuild_pgvector, "build_biobert_embedding", fake_build_biobert_embedding)
    monkeypatch.setattr(rebuild_pgvector, "get_storage_config", lambda: {"postgresql": {}})
    monkeypatch.setattr(
        rebuild_pgvector,
        "get_pgvector_config_for_provider",
        lambda _provider: {"table_name": "documents_biobert", "embedding_dimension": 768},
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
            provider="biobert",
        )
    )

    assert call_args["args"] == ()
    assert "device" not in call_args["kwargs"]
