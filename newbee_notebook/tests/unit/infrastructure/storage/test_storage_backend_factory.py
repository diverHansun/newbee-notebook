from newbee_notebook.infrastructure.storage import get_storage_backend, reset_storage_backend
from newbee_notebook.infrastructure.storage.local_storage_backend import LocalStorageBackend


def test_get_storage_backend_returns_local_backend_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("DOCUMENTS_DIR", str(tmp_path))
    reset_storage_backend()

    backend = get_storage_backend()

    assert isinstance(backend, LocalStorageBackend)


def test_get_storage_backend_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "unknown")
    reset_storage_backend()

    try:
        get_storage_backend()
    except ValueError as exc:
        assert "Unsupported STORAGE_BACKEND" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported backend")
