from newbee_notebook.core.common.config import (
    embedding_storage_names_for_cleanup,
    get_pgvector_config_for_provider,
    get_storage_config,
)


def test_native_local_vectors_are_isolated_and_api_names_are_preserved(monkeypatch):
    monkeypatch.setenv("NEWBEE_API_ONLY", "false")
    monkeypatch.delenv("QWEN3_EMBEDDING_LOCAL_API_URL", raising=False)
    monkeypatch.setenv("QWEN3_EMBEDDING_MODE", "local")
    original_pg = get_pgvector_config_for_provider("qwen3-embedding")["table_name"]
    original_es = get_storage_config()["elasticsearch"]["index_name"]
    assert embedding_storage_names_for_cleanup(original_pg) == (original_pg,)
    monkeypatch.setenv("QWEN3_EMBEDDING_LOCAL_API_URL", "http://localhost:8002/v1")
    assert get_pgvector_config_for_provider("qwen3-embedding")["table_name"] == original_pg + "_qwen3_local"
    assert get_storage_config()["elasticsearch"]["index_name"] == original_es + "_qwen3_local"
    assert embedding_storage_names_for_cleanup(original_pg + "_qwen3_local") == (original_pg, original_pg + "_qwen3_local")
    monkeypatch.setenv("QWEN3_EMBEDDING_MODE", "api")
    assert get_pgvector_config_for_provider("qwen3-embedding")["table_name"] == original_pg
    assert get_storage_config()["elasticsearch"]["index_name"] == original_es


def test_api_only_does_not_use_native_vector_namespace(monkeypatch):
    monkeypatch.setenv("NEWBEE_API_ONLY", "true")
    monkeypatch.setenv("QWEN3_EMBEDDING_MODE", "local")
    monkeypatch.setenv("QWEN3_EMBEDDING_LOCAL_API_URL", "http://localhost:8002/v1")
    assert not get_storage_config()["elasticsearch"]["index_name"].endswith("_qwen3_local")
