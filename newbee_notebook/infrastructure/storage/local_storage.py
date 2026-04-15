"""
Local file storage utilities.
"""

import os
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import unquote

from fastapi import UploadFile

from newbee_notebook.core.common.config import get_documents_directory
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _sanitize_filename(value: str) -> str:
    value = value.replace("\\", "_").replace("/", "_")
    value = "".join(ch for ch in value if ord(ch) >= 32)
    return value.strip()


def _has_cjk(value: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in value)


def _suspicious_char_count(value: str) -> int:
    # Common mojibake markers when UTF-8/GBK bytes are decoded with latin-1.
    suspicious = {
        "\u00c3",  # U+00C3
        "\u00d0",  # U+00D0
        "\u00ce",  # U+00CE
        "\u00ca",  # U+00CA
        "\u00d6",  # U+00D6
        "\u00d5",  # U+00D5
        "\u00c4",  # U+00C4
        "\u00c5",  # U+00C5
        "\u00e5",  # U+00E5
        "\u00e7",  # U+00E7
        "\u00e6",  # U+00E6
        "\u00f8",  # U+00F8
        "\ufffd",  # replacement char
    }
    return sum(1 for ch in value if ch in suspicious)


def _decode_filename(filename: str) -> str:
    """Best-effort decode for multipart filenames from mixed client encodings."""
    if not filename:
        return "upload.bin"

    raw = filename.strip().strip('"')
    candidates: list[str] = []

    def _add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    _add(raw)

    # Decode URL-escaped names, e.g. %E4%B8%AD%E6%96%87.pdf
    try:
        _add(unquote(raw, encoding="utf-8", errors="strict"))
    except Exception:
        _add(unquote(raw))

    # Handle values like UTF-8''%E4%B8%AD%E6%96%87.pdf
    if "''" in raw:
        charset, encoded = raw.split("''", 1)
        try:
            _add(unquote(encoded, encoding=charset or "utf-8", errors="strict"))
        except Exception:
            _add(unquote(encoded))

    # Recover common mojibake caused by latin-1 decoding of UTF-8/GBK bytes.
    for text in list(candidates):
        try:
            raw_bytes = text.encode("latin1")
        except UnicodeEncodeError:
            continue
        for encoding in ("utf-8", "gb18030", "gbk"):
            try:
                _add(raw_bytes.decode(encoding))
            except UnicodeDecodeError:
                continue

    sanitized = []
    for item in candidates:
        cleaned = _sanitize_filename(item)
        if cleaned:
            sanitized.append(cleaned)
    if not sanitized:
        return "upload.bin"

    # Prefer filenames that contain CJK chars (for Chinese docs),
    # then fallback to the one with fewer suspicious mojibake markers.
    cjk_candidates = [item for item in sanitized if _has_cjk(item)]
    if cjk_candidates:
        return max(cjk_candidates, key=lambda s: (sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff"), -_suspicious_char_count(s)))

    return min(sanitized, key=_suspicious_char_count)


SUPPORTED_EXTENSIONS = {
    "pdf",
    "txt",
    "md",
    "markdown",
    "csv",
    "xls",
    "xlsx",
    "doc",
    "docx",
    "pptx",
    "epub",
}


def save_upload_file(
    upload: UploadFile,
    document_id: str,
    base_root: Optional[str] = None,
) -> Tuple[str, int, str]:
    """
    Save an UploadFile under data/documents/{document_id}/original/.

    Returns:
        tuple: (relative_path, size_bytes, extension)
    """
    base_root = base_root or get_documents_directory()

    raw_name = upload.filename or "upload.bin"
    filename = _decode_filename(raw_name)
    stem, suffix = os.path.splitext(filename)
    ext = suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: .{ext}")

    dest_dir = Path(base_root) / document_id / "original"
    ensure_dir(dest_dir)

    dest_path = dest_dir / f"{stem}{suffix}"
    # Avoid overwriting existing files
    if dest_path.exists():
        dest_path = dest_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"

    with dest_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    size = dest_path.stat().st_size
    rel_path = dest_path.relative_to(Path(base_root)).as_posix()
    return rel_path, size, ext


def _guess_upload_content_type(upload: UploadFile, ext: str, filename: str) -> str:
    if upload.content_type:
        return upload.content_type
    # Prefer stable extension-specific MIME types for formats where
    # platform mime registries often return inconsistent values.
    if ext == "md" or ext == "markdown":
        return "text/markdown"
    if ext == "pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if ext == "epub":
        return "application/epub+zip"
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    # Keep a minimal safe fallback when extension-based MIME guess misses.
    return "application/octet-stream"


async def save_upload_file_with_storage(
    upload: UploadFile,
    document_id: str,
    base_root: Optional[str] = None,
) -> Tuple[str, int, str]:
    """Save upload directly to the runtime storage backend."""
    del base_root

    raw_name = upload.filename or "upload.bin"
    filename = _decode_filename(raw_name)
    stem, suffix = os.path.splitext(filename)
    ext = suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: .{ext}")

    filename = f"{stem}{suffix}"
    rel_path = f"{document_id}/original/{filename}"
    backend = get_runtime_storage_backend()
    content_type = _guess_upload_content_type(
        upload=upload,
        ext=ext,
        filename=filename,
    )

    upload.file.seek(0)
    size = upload.file.seek(0, os.SEEK_END)
    upload.file.seek(0)

    await backend.save_file(
        object_key=rel_path,
        data=upload.file,
        content_type=content_type,
    )

    # Reset to a readable state for any downstream callers/tests that inspect the stream.
    upload.file.seek(0)
    return rel_path, size, ext
