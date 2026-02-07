import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
from pypdf import PdfReader

from .base import Converter, ConversionResult


class MinerUConverter(Converter):
    """Converter for PDFs via MinerU HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: int = 300,
        backend: str = "hybrid-auto-engine",
        lang_list: str = "en,zh",
    ) -> None:
        self._base_url = (base_url or os.getenv("MINERU_API_URL") or "http://mineru-api:8000").rstrip("/")
        self._timeout = timeout_seconds
        self._backend = backend
        self._lang_list = lang_list

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
            with path.open("rb") as f:
                return len(PdfReader(f).pages)

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

        url = f"{self._base_url}/file_parse"
        # Build form data as dict (httpx requires dict when used with files parameter)
        # Note: backend must be sent per-request, NOT via MinerU CLI --backend flag,
        # which causes "multiple values for keyword argument 'backend'" error.
        data: Dict[str, Any] = {
            "backend": self._backend,
            "return_md": "true",
        }
        lang_list = self._normalize_lang_list(self._lang_list)
        if lang_list:
            # For multiple values with same key, httpx accepts list
            data["lang_list"] = lang_list

        # Fail fast if the service is unreachable (5s connect), but wait indefinitely
        # for conversion (large scanned PDFs can take 60+ minutes on CPU).
        read_timeout = None if self._timeout <= 0 else float(self._timeout)
        timeout = httpx.Timeout(read_timeout, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with path.open("rb") as f:
                # MinerU FastAPI expects the multipart field name `files` (List[UploadFile]).
                files = {"files": (path.name, f, "application/pdf")}
                resp = await client.post(url, files=files, data=data)
                resp.raise_for_status()
                payload = resp.json()

        markdown = payload.get("md_content") or payload.get("markdown") or payload.get("content") or ""
        images = payload.get("images")
        page_count = payload.get("page_count") or payload.get("page_num") or 0

        # Newer MinerU API responses wrap per-file results under `results`.
        if not markdown and isinstance(payload.get("results"), dict):
            results: Dict[str, Any] = payload["results"]
            file_result: object = results.get(path.stem)
            if not isinstance(file_result, dict):
                # Fall back to the first entry (single file uploads are most common here).
                file_result = next(iter(results.values()), {})
            if isinstance(file_result, dict):
                markdown = (
                    file_result.get("md_content")
                    or file_result.get("markdown")
                    or file_result.get("content")
                    or ""
                )
                images = file_result.get("images") or images
                page_count = file_result.get("page_count") or file_result.get("page_num") or page_count

        if not markdown:
            raise RuntimeError("MinerU response missing markdown content")

        if not page_count:
            page_count = await self._count_pages(path)

        # Images are optional; MinerU may return URLs/base64. Store layer currently persists bytes only.
        # We pass through raw and let downstream decide what to do with it.

        return ConversionResult(markdown=markdown, page_count=page_count or 0, images=images)
