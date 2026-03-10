"""Helpers for normalizing legacy storage object keys."""

from pathlib import Path


def build_storage_key_candidates(
    raw_path: str | None,
    default_key: str | None = None,
    documents_root: str | None = None,
) -> list[str]:
    """Build candidate object keys from legacy DB paths.

    Supports:
    - current relative keys: ``doc-id/original/file.pdf``
    - legacy prefixed keys: ``documents/doc-id/...``
    - legacy absolute local paths under ``documents_root``
    """

    candidates: list[str] = []
    documents_dir = Path(documents_root).resolve() if documents_root else None

    def _append(value: str | None) -> None:
        if not value:
            return
        normalized = value.strip().replace("\\", "/").lstrip("/")
        if not normalized:
            return
        if normalized not in candidates:
            candidates.append(normalized)
        if normalized.startswith("documents/"):
            trimmed = normalized[len("documents/"):]
            if trimmed and trimmed not in candidates:
                candidates.append(trimmed)

    _append(raw_path)
    if raw_path and documents_dir:
        maybe_abs = Path(raw_path)
        if maybe_abs.is_absolute():
            try:
                rel = maybe_abs.resolve().relative_to(documents_dir).as_posix()
                _append(rel)
            except Exception:
                pass

    _append(default_key)
    return candidates
