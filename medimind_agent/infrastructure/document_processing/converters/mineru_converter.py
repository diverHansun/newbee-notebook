import os
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

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

    def can_handle(self, ext: str) -> bool:
        return ext.lower() == ".pdf"

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        url = f"{self._base_url}/file_parse"
        data: Dict[str, Any] = {
            "backend": self._backend,
            "lang_list": self._lang_list,
            "return_md": "true",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            with path.open("rb") as f:
                files = {"file": (path.name, f, "application/pdf")}
                resp = await client.post(url, files=files, data=data)
                resp.raise_for_status()
                payload = resp.json()

        markdown = (
            payload.get("md_content")
            or payload.get("markdown")
            or payload.get("content")
            or ""
        )
        if not markdown:
            raise RuntimeError("MinerU response missing markdown content")

        page_count = payload.get("page_count") or payload.get("page_num") or 0

        # Images are optional; MinerU may return URLs or base64—pass through raw
        images = payload.get("images")

        return ConversionResult(markdown=markdown, page_count=page_count or 0, images=images)
