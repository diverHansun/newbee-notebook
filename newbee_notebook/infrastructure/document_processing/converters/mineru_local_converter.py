import asyncio
import gc
import io
import json
import logging
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

import requests
from pypdf import PdfReader

from .base import Converter, ConversionResult

logger = logging.getLogger(__name__)

# Large PDFs (hundreds of pages) are split into batches to avoid OOM in the
# MinerU worker process pool.  Each batch is sent as a separate API request
# with ``start_page_id`` / ``end_page_id``; results are merged afterwards.
#
# 50 pages at 200 DPI ~= 533 MB image RAM per batch. Combined with model
# weights (~4 GB) and overhead, this leaves more headroom for vLLM restarts
# provided inter-batch memory cleanup is performed (gc.collect between
# batches on the client side, MINERU_VIRTUAL_VRAM_SIZE=8 on the server side).
_DEFAULT_MAX_PAGES_PER_BATCH = 50
_DEFAULT_REQUEST_RETRY_ATTEMPTS = 2
_DEFAULT_RETRY_BACKOFF_SECONDS = 10.0


class MinerULocalConverter(Converter):
    """Converter for PDFs via MinerU local HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: int = 300,
        backend: str = "pipeline",
        lang_list: str = "ch,en",
        return_images: bool = True,
        return_content_list: bool = True,
        return_model_output: bool = True,
        max_pages_per_batch: int = _DEFAULT_MAX_PAGES_PER_BATCH,
        request_retry_attempts: int = _DEFAULT_REQUEST_RETRY_ATTEMPTS,
        retry_backoff_seconds: float = _DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._base_url = (base_url or "http://mineru-api:8000").rstrip("/")
        self._timeout = timeout_seconds
        self._backend = backend
        self._lang_list = lang_list
        self._return_images = return_images
        self._return_content_list = return_content_list
        self._return_model_output = return_model_output
        self._max_pages_per_batch = max(1, max_pages_per_batch)
        self._request_retry_attempts = max(0, request_retry_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    @staticmethod
    def _normalize_lang_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [s.strip() for s in value.replace(";", ",").split(",")]
            return [s for s in items if s]
        try:
            return [str(s).strip() for s in value if str(s).strip()]  # type: ignore[arg-type]
        except TypeError:
            text = str(value).strip()
            return [text] if text else []

    @staticmethod
    async def _count_pages(path: Path) -> int:
        def _count() -> int:
            with path.open("rb") as file:
                return len(PdfReader(file).pages)

        try:
            return await asyncio.to_thread(_count)
        except Exception:
            return 0

    def can_handle(self, ext: str) -> bool:
        return ext.lower() == ".pdf"

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        total_pages = await self._count_pages(path)
        if total_pages <= 0:
            total_pages = 1  # fallback: let MinerU decide

        if total_pages <= self._max_pages_per_batch:
            # Small PDF – single request, no batching.
            return await self._convert_range_with_retry(
                path,
                start_page=0,
                end_page=total_pages - 1,
                total_pages=total_pages,
            )

        # ---- Large PDF: split into batches ----
        logger.info(
            "PDF has %d pages (> %d); processing in batches of %d",
            total_pages, self._max_pages_per_batch, self._max_pages_per_batch,
        )
        all_markdown: list[str] = []
        all_images: dict[str, bytes] = {}
        all_metadata: dict[str, bytes] = {}
        accumulated_page_count = 0
        num_batches = (total_pages + self._max_pages_per_batch - 1) // self._max_pages_per_batch

        for batch_start in range(0, total_pages, self._max_pages_per_batch):
            batch_end = min(batch_start + self._max_pages_per_batch - 1, total_pages - 1)
            batch_num = batch_start // self._max_pages_per_batch + 1
            logger.info(
                "  Batch %d/%d: pages %d–%d (%d pages)",
                batch_num, num_batches, batch_start, batch_end, batch_end - batch_start + 1,
            )
            result = await self._convert_range_with_retry(
                path,
                start_page=batch_start,
                end_page=batch_end,
                total_pages=total_pages,
            )

            all_markdown.append(result.markdown)
            accumulated_page_count += result.page_count

            # Merge image assets with batch-prefixed keys to avoid collisions.
            if result.image_assets:
                for key, data in result.image_assets.items():
                    prefixed_key = f"batch{batch_num}/{key}" if key in all_images else key
                    all_images[prefixed_key] = data

            if result.metadata_assets:
                for key, data in result.metadata_assets.items():
                    prefixed_key = f"batch{batch_num}_{key}"
                    all_metadata[prefixed_key] = data

            # --- Inter-batch memory cleanup ---
            # Release the batch result reference so the large zip_bytes,
            # markdown, and image dicts can be reclaimed.
            del result

            if batch_num < num_batches:
                # Trigger Python GC to free accumulated objects from this
                # batch (ZIP data, decoded images, response bytes).  MinerU
                # container-side cleanup is handled by MINERU_VIRTUAL_VRAM_SIZE
                # env var which makes its built-in clean_vram() trigger after
                # each inference stage.
                gc.collect()
                logger.info("  Batch %d/%d done, local gc completed", batch_num, num_batches)

        merged_markdown = "\n\n".join(all_markdown)
        return ConversionResult(
            markdown=merged_markdown,
            page_count=accumulated_page_count or total_pages,
            image_assets=all_images or None,
            metadata_assets=all_metadata or None,
        )

    @staticmethod
    def _should_retry_request(error: Exception) -> bool:
        if isinstance(error, requests.Timeout):
            return True
        if isinstance(error, requests.ConnectionError):
            return True
        if isinstance(error, requests.HTTPError):
            response = getattr(error, "response", None)
            return response is None or response.status_code >= 500
        return False

    def _retry_delay_seconds(self, attempt: int) -> float:
        if self._retry_backoff_seconds <= 0:
            return 0.0
        return self._retry_backoff_seconds * (2 ** max(0, attempt - 1))

    async def _convert_range_with_retry(
        self,
        path: Path,
        *,
        start_page: int,
        end_page: int,
        total_pages: int,
    ) -> ConversionResult:
        attempts = self._request_retry_attempts + 1
        for attempt in range(1, attempts + 1):
            try:
                return await self._convert_range(
                    path,
                    start_page=start_page,
                    end_page=end_page,
                    total_pages=total_pages,
                )
            except Exception as exc:
                if attempt >= attempts or not self._should_retry_request(exc):
                    raise
                delay = self._retry_delay_seconds(attempt)
                logger.warning(
                    "MinerU local batch pages %d-%d failed attempt %d/%d for %s: %s. Retrying in %.1fs",
                    start_page,
                    end_page,
                    attempt,
                    attempts,
                    path,
                    exc,
                    delay,
                )
                gc.collect()
                if delay > 0:
                    await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Internal: convert a page range via MinerU API
    # ------------------------------------------------------------------

    async def _convert_range(
        self,
        path: Path,
        *,
        start_page: int,
        end_page: int,
        total_pages: int,
    ) -> ConversionResult:
        """Send a single request to MinerU covering *start_page* .. *end_page*."""
        url = f"{self._base_url}/file_parse"

        form_data: list[tuple[str, str]] = [
            ("backend", self._backend),
            ("return_md", "true"),
            ("return_content_list", "true" if self._return_content_list else "false"),
            ("return_model_output", "true" if self._return_model_output else "false"),
            ("return_images", "true" if self._return_images else "false"),
            ("response_format_zip", "true"),
            ("start_page_id", str(start_page)),
            ("end_page_id", str(end_page)),
        ]
        for language in self._normalize_lang_list(self._lang_list):
            form_data.append(("lang_list", language))

        read_timeout = None if self._timeout <= 0 else float(self._timeout)

        def _sync_upload() -> tuple[str, str]:
            zip_path = ""
            with path.open("rb") as file:
                files = {"files": (path.name, file, "application/pdf")}
                with requests.post(
                    url,
                    files=files,
                    data=form_data,
                    timeout=(5.0, read_timeout),
                    stream=True,
                ) as resp:
                    resp.raise_for_status()
                    content_type = (resp.headers.get("content-type") or "").lower()
                    if "application/zip" not in content_type:
                        detail = ""
                        try:
                            detail = json.dumps(resp.json(), ensure_ascii=False)
                        except Exception:
                            detail = (resp.text or "")[:500]
                        raise RuntimeError(f"MinerU local API did not return zip results: {detail}")

                    with tempfile.NamedTemporaryFile(prefix="mineru_local_", suffix=".zip", delete=False) as tmp:
                        zip_path = tmp.name
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                tmp.write(chunk)
                    return content_type, zip_path

        _, zip_path = await asyncio.to_thread(_sync_upload)
        try:
            markdown, image_assets, metadata_assets = self._parse_result_zip(zip_path)
        finally:
            try:
                Path(zip_path).unlink(missing_ok=True)
            except Exception:
                pass
        page_count = _extract_page_count(metadata_assets)
        if not page_count:
            page_count = end_page - start_page + 1

        return ConversionResult(
            markdown=markdown,
            page_count=page_count,
            image_assets=image_assets or None,
            metadata_assets=metadata_assets or None,
        )

    @staticmethod
    def _parse_result_zip(zip_source: bytes | str | Path) -> tuple[str, dict[str, bytes], dict[str, bytes]]:
        image_assets: dict[str, bytes] = {}
        metadata_assets: dict[str, bytes] = {}
        archive_source = io.BytesIO(zip_source) if isinstance(zip_source, (bytes, bytearray)) else zip_source

        with zipfile.ZipFile(archive_source, "r") as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names:
                raise RuntimeError("MinerU local zip is empty")

            md_candidates = [name for name in names if name.lower().endswith(".md")]
            if not md_candidates:
                raise RuntimeError("MinerU local zip has no markdown file")

            markdown_path = md_candidates[0]
            markdown = archive.read(markdown_path).decode("utf-8", errors="replace")

            root_prefix = str(PurePosixPath(markdown_path).parent)
            if root_prefix in {"", "."}:
                root_prefix = ""
            prefix = f"{root_prefix}/" if root_prefix else ""

            for name in names:
                rel = name[len(prefix):] if prefix and name.startswith(prefix) else name
                rel = rel.replace("\\", "/")
                if rel == markdown_path or rel.endswith(".md"):
                    continue
                if rel.startswith("images/"):
                    image_assets[rel] = archive.read(name)
                elif rel.lower().endswith(".json"):
                    metadata_assets[rel] = archive.read(name)

        if "images/" in markdown and not image_assets:
            raise RuntimeError("MinerU local markdown references images but no image assets were found")

        return markdown, image_assets, metadata_assets


def _extract_page_count(metadata_assets: dict[str, bytes]) -> int:
    for name, raw in metadata_assets.items():
        lower_name = name.lower()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            continue

        if lower_name.endswith("content_list_v2.json") and isinstance(payload, list):
            return len(payload)
        if lower_name.endswith("layout.json") and isinstance(payload, dict):
            pdf_info = payload.get("pdf_info")
            if isinstance(pdf_info, list):
                return len(pdf_info)
    return 0
