from pathlib import Path
from typing import Optional, Sequence

from medimind_agent.core.common.config import get_documents_directory


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_markdown(
    document_id: str,
    markdown: str,
    *,
    images: Optional[Sequence[bytes]] = None,
    base_root: Optional[str] = None,
) -> tuple[str, int]:
    """
    Persist markdown (and optional images) under data/documents/{document_id}/.

    Returns:
        (relative_content_path, content_size_bytes)
    """
    root = Path(base_root or get_documents_directory())
    doc_dir = root / document_id
    _ensure_dir(doc_dir)

    content_path = doc_dir / "content.md"
    content_bytes = markdown.encode("utf-8")
    content_path.write_bytes(content_bytes)

    if images:
        images_dir = doc_dir / "images"
        _ensure_dir(images_dir)
        for idx, image_bytes in enumerate(images):
            data = None
            if isinstance(image_bytes, (bytes, bytearray)):
                data = bytes(image_bytes)
            if data is None:
                continue
            (images_dir / f"{idx:03d}.bin").write_bytes(data)

    # Return POSIX-style relative path for portability
    rel_path = content_path.relative_to(root).as_posix()
    return rel_path, len(content_bytes)
