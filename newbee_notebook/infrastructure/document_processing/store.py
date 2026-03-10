from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlsplit, urlunsplit
import re
import mimetypes
from io import BytesIO

from newbee_notebook.core.common.config import get_documents_directory
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend


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


def _build_storage_payloads(
    document_id: str,
    markdown: str,
    *,
    image_assets: Optional[dict[str, bytes]] = None,
    metadata_assets: Optional[dict[str, bytes]] = None,
) -> tuple[str, bytes, dict[str, bytes], dict[str, bytes]]:
    image_link_map: dict[str, str] = {}
    normalized_images: dict[str, bytes] = {}
    normalized_metadata: dict[str, bytes] = {}

    if image_assets:
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

            normalized_images[rel_image_path] = bytes(image_bytes)

            markdown_target = f"/api/v1/documents/{document_id}/assets/images/{rel_image_path}"
            image_link_map[safe_source] = markdown_target
            image_link_map.setdefault(Path(safe_source).name, markdown_target)
            image_link_map.setdefault(f"images/{Path(safe_source).name}", markdown_target)

    if metadata_assets:
        for name, data in metadata_assets.items():
            if not isinstance(data, (bytes, bytearray)):
                continue
            safe_name = _safe_posix_path(name)
            if not safe_name:
                continue
            normalized_metadata[safe_name] = bytes(data)

    normalized_markdown = _rewrite_markdown_image_links(markdown, image_link_map)
    return (
        f"{document_id}/markdown/content.md",
        normalized_markdown.encode("utf-8"),
        normalized_images,
        normalized_metadata,
    )


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

    rel_path, content_bytes, normalized_images, normalized_metadata = _build_storage_payloads(
        document_id=document_id,
        markdown=markdown,
        image_assets=image_assets,
        metadata_assets=metadata_assets,
    )

    if normalized_images:
        images_dir = doc_root / "assets" / "images"
        _ensure_dir(images_dir)
        for rel_image_path, image_bytes in normalized_images.items():
            target_path = images_dir / Path(rel_image_path)
            _ensure_dir(target_path.parent)
            target_path.write_bytes(image_bytes)

    content_path = markdown_dir / "content.md"
    content_path.write_bytes(content_bytes)

    if normalized_metadata:
        meta_dir = doc_root / "assets" / "meta"
        _ensure_dir(meta_dir)
        for safe_name, data in normalized_metadata.items():
            target_path = meta_dir / Path(safe_name)
            _ensure_dir(target_path.parent)
            target_path.write_bytes(data)

    # Return POSIX-style relative path for portability
    return rel_path, len(content_bytes)


async def save_markdown_with_storage(
    document_id: str,
    markdown: str,
    *,
    image_assets: Optional[dict[str, bytes]] = None,
    metadata_assets: Optional[dict[str, bytes]] = None,
    base_root: Optional[str] = None,
) -> tuple[str, int]:
    """Persist markdown and generated artifacts directly to runtime storage."""
    del base_root

    rel_path, content_bytes, normalized_images, normalized_metadata = _build_storage_payloads(
        document_id=document_id,
        markdown=markdown,
        image_assets=image_assets,
        metadata_assets=metadata_assets,
    )
    backend = get_runtime_storage_backend()

    await backend.save_file(
        object_key=rel_path,
        data=BytesIO(content_bytes),
        content_type="text/markdown",
    )

    for rel_image_path, image_bytes in normalized_images.items():
        object_key = f"{document_id}/assets/images/{rel_image_path}"
        content_type, _ = mimetypes.guess_type(rel_image_path)
        await backend.save_file(
            object_key=object_key,
            data=BytesIO(image_bytes),
            content_type=content_type or "application/octet-stream",
        )

    for meta_name, data in normalized_metadata.items():
        object_key = f"{document_id}/assets/meta/{meta_name}"
        content_type, _ = mimetypes.guess_type(meta_name)
        await backend.save_file(
            object_key=object_key,
            data=BytesIO(data),
            content_type=content_type or "application/octet-stream",
        )

    return rel_path, len(content_bytes)
