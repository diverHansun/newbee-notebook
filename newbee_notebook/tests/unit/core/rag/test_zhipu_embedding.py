from newbee_notebook.core.rag.embeddings import zhipu as zhipu_embedding


def test_build_zhipu_embedding_uses_openai_compatible_client(monkeypatch):
    captured_kwargs = {}

    class DummyOpenAIEmbedding:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.dimensions = kwargs["dimensions"]

        def _get_query_embedding(self, query: str):
            return [len(query)]

        def _get_text_embedding(self, text: str):
            return [len(text)]

        def _get_text_embeddings(self, texts):
            return [[len(text)] for text in texts]

        async def _aget_query_embedding(self, query: str):
            return [len(query)]

        async def _aget_text_embedding(self, text: str):
            return [len(text)]

        async def _aget_text_embeddings(self, texts):
            return [[len(text)] for text in texts]

    monkeypatch.setattr(zhipu_embedding, "OpenAIEmbedding", DummyOpenAIEmbedding)
    monkeypatch.setattr(
        zhipu_embedding,
        "_get_zhipu_config",
        lambda: {
            "model": "embedding-3",
            "dim": 1024,
        },
    )
    monkeypatch.setattr(zhipu_embedding, "get_zhipu_api_key", lambda: "zhipu-key")
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSION", raising=False)
    monkeypatch.delenv("ZHIPU_API_BASE", raising=False)

    embed_model = zhipu_embedding.build_zhipu_embedding()

    assert captured_kwargs["model"] == "embedding-3"
    assert captured_kwargs["dimensions"] == 1024
    assert captured_kwargs["api_key"] == "zhipu-key"
    assert captured_kwargs["api_base"] == "https://open.bigmodel.cn/api/paas/v4"
    assert embed_model.model_name == "zhipu-embedding-3"
    assert embed_model.dimensions == 1024


def test_build_zhipu_embedding_respects_env_overrides(monkeypatch):
    captured_kwargs = {}

    class DummyOpenAIEmbedding:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.dimensions = kwargs["dimensions"]

        def _get_query_embedding(self, query: str):
            return [len(query)]

        def _get_text_embedding(self, text: str):
            return [len(text)]

        def _get_text_embeddings(self, texts):
            return [[len(text)] for text in texts]

        async def _aget_query_embedding(self, query: str):
            return [len(query)]

        async def _aget_text_embedding(self, text: str):
            return [len(text)]

        async def _aget_text_embeddings(self, texts):
            return [[len(text)] for text in texts]

    monkeypatch.setattr(zhipu_embedding, "OpenAIEmbedding", DummyOpenAIEmbedding)
    monkeypatch.setattr(
        zhipu_embedding,
        "_get_zhipu_config",
        lambda: {
            "model": "embedding-3",
            "dim": 1024,
        },
    )
    monkeypatch.setattr(zhipu_embedding, "get_zhipu_api_key", lambda: "zhipu-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "embedding-4")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "2048")
    monkeypatch.setenv("ZHIPU_API_BASE", "https://zhipu.example.test/v4")

    zhipu_embedding.build_zhipu_embedding()

    assert captured_kwargs["model"] == "embedding-4"
    assert captured_kwargs["dimensions"] == 2048
    assert captured_kwargs["api_base"] == "https://zhipu.example.test/v4"
