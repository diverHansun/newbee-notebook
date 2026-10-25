from fastapi.testclient import TestClient
import importlib.util
import sys
from pathlib import Path

script = Path(__file__).resolve().parents[4] / "scripts" / "local_embedding_server.py"
spec = importlib.util.spec_from_file_location("local_embedding_server", script)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
create_app = module.create_app


class Embedding:
    dimensions = 2

    def get_text_embedding_batch(self, texts):
        return [[float(len(text)), 1.0] for text in texts]


def test_native_embedding_server_preserves_order_and_model_contract():
    with TestClient(create_app(Embedding().get_text_embedding_batch, "test-model", 2)) as client:
        response = client.post("/v1/embeddings", json={
            "model": "test-model", "input": ["ab", "c"], "dimensions": 2,
        })
        assert response.status_code == 200
        assert [item["embedding"] for item in response.json()["data"]] == [[2.0, 1.0], [1.0, 1.0]]
        assert client.get("/health").json()["dimensions"] == 2


def test_native_embedding_server_rejects_incompatible_or_unbounded_requests():
    with TestClient(create_app(Embedding().get_text_embedding_batch, "test-model", 2)) as client:
        for override in ({"model": "wrong"}, {"dimensions": 3}, {"input": []}, {"input": ["x"] * 33}):
            payload = {"model": "test-model", "input": "hello", "dimensions": 2, **override}
            assert client.post("/v1/embeddings", json=payload).status_code == 400
