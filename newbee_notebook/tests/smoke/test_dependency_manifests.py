from pathlib import Path


def test_python_dependency_manifests_do_not_reference_faiss():
    repo_root = Path(__file__).resolve().parents[3]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (repo_root / "requirements.txt").read_text(encoding="utf-8")

    assert "faiss-cpu" not in pyproject
    assert "llama-index-vector-stores-faiss" not in pyproject
    assert "faiss-cpu" not in requirements
    assert "llama-index-vector-stores-faiss" not in requirements
