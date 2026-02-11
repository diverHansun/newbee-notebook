from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlsplit, urlunsplit
import re

from newbee_notebook.core.common.config import get_documents_directory


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


_MD_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(([^)]+)\)")
_HTML_IMAGE_PATTERN = re.compile(r'(<img[^>]*\ssrc=["\'])([^"\']+)(["\'])', re.IGNORECASE)


def _normalize_ref(value: str) -> str:
    ref = (value or "").strip()
    if ref.startswith("<") and ref.endswith(">"):
        ref = ref[1:-1].strip()
    return ref.replace("\\", "/")


def _safe_posix_path(value: str) -> str:
    parts = []
    for part in PurePosixPath(value).parts:
        if part in {"", ".", ".."}:
            continue
        parts.append(part)
    return "/".join(parts)


def _rewrite_markdown_image_links(markdown: str, image_map: dict[str, str]) -> str:
    if not image_map or not markdown:
        return markdown

    def _resolve(raw_target: str) -> Optional[str]:
        target = _normalize_ref(raw_target)
        parsed = urlsplit(target)
        if parsed.scheme in {"http", "https", "data"}:
            return None

        norm_path = _safe_posix_path(parsed.path)
        if not norm_path:
            return None

        candidates = [norm_path]
        if norm_path.startswith("images/"):
            candidates.append(norm_path[len("images/"):])
        candidates.append(PurePosixPath(norm_path).name)

        for candidate in candidates:
            replacement = image_map.get(candidate)
            if replacement:
                parsed = parsed._replace(path=replacement)
                return urlunsplit(parsed)
        return None

    def _replace_md(match: re.Match[str]) -> str:
        original = match.group(1)
        replacement = _resolve(original)
        if not replacement:
            return match.group(0)
        return match.group(0).replace(original, replacement, 1)

    markdown = _MD_IMAGE_PATTERN.sub(_replace_md, markdown)

    def _replace_html(match: re.Match[str]) -> str:
        original = match.group(2)
        replacement = _resolve(original)
        if not replacement:
            return match.group(0)
        return f"{match.group(1)}{replacement}{match.group(3)}"

    markdown = _HTML_IMAGE_PATTERN.sub(_replace_html, markdown)
    return markdown


def save_markdown(
    document_id: str,
    markdown: str,
    *,
    image_assets: Optional[dict[str, bytes]] = None,
    metadata_assets: Optional[dict[str, bytes]] = None,
    base_root: Optional[str] = None,
) -> tuple[str, int]:
    """
    Persist markdown and conversion artifacts under data/documents/{document_id}/.

    Returns:
        (relative_content_path, content_size_bytes)
    """
    root = Path(base_root or get_documents_directory())
    doc_root = root / document_id
    markdown_dir = root / document_id / "markdown"
    _ensure_dir(markdown_dir)

    image_link_map: dict[str, str] = {}
    if image_assets:
        images_dir = doc_root / "assets" / "images"
        _ensure_dir(images_dir)
        for source_ref, image_bytes in image_assets.items():
            if not isinstance(image_bytes, (bytes, bytearray)):
                continue

            source_norm = _normalize_ref(source_ref)
            safe_source = _safe_posix_path(source_norm)
            if not safe_source:
                continue

            if safe_source.startswith("images/"):
                rel_image_path = safe_source[len("images/"):]
            else:
                rel_image_path = safe_source
            rel_image_path = _safe_posix_path(rel_image_path)
            if not rel_image_path:
                continue

            target_path = images_dir / Path(rel_image_path)
            _ensure_dir(target_path.parent)
            target_path.write_bytes(bytes(image_bytes))

            rel_image_posix = rel_image_path.replace("\\", "/")
            markdown_target = f"/api/v1/documents/{document_id}/assets/images/{rel_image_posix}"
            image_link_map[safe_source] = markdown_target
            image_link_map.setdefault(Path(safe_source).name, markdown_target)
            image_link_map.setdefault(f"images/{Path(safe_source).name}", markdown_target)

    normalized_markdown = _rewrite_markdown_image_links(markdown, image_link_map)

    content_path = markdown_dir / "content.md"
    content_bytes = normalized_markdown.encode("utf-8")
    content_path.write_bytes(content_bytes)

    if metadata_assets:
        meta_dir = doc_root / "assets" / "meta"
        _ensure_dir(meta_dir)
        for name, data in metadata_assets.items():
            if not isinstance(data, (bytes, bytearray)):
                continue
            safe_name = _safe_posix_path(name)
            if not safe_name:
                continue
            target_path = meta_dir / Path(safe_name)
            _ensure_dir(target_path.parent)
            target_path.write_bytes(bytes(data))

    # Return POSIX-style relative path for portability
    rel_path = content_path.relative_to(root).as_posix()
    return rel_path, len(content_bytes)
