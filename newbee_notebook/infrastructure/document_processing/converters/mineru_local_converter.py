import asyncio
import io
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

import httpx
from pypdf import PdfReader

from .base import Converter, ConversionResult


class MinerULocalConverter(Converter):
    """Converter for PDFs via MinerU local HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: int = 300,
        backend: str = "pipeline",
        lang_list: str = "ch,en",
    ) -> None:
        self._base_url = (base_url or "http://mineru-api:8000").rstrip("/")
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

        url = f"{self._base_url}/file_parse"
        form_data: list[tuple[str, str]] = [
            ("backend", self._backend),
            ("return_md", "true"),
            ("return_content_list", "true"),
            ("return_model_output", "true"),
            ("return_images", "true"),
            ("response_format_zip", "true"),
        ]
        for language in self._normalize_lang_list(self._lang_list):
            form_data.append(("lang_list", language))

        read_timeout = None if self._timeout <= 0 else float(self._timeout)
        timeout = httpx.Timeout(read_timeout, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with path.open("rb") as file:
                files = {"files": (path.name, file, "application/pdf")}
                response = await client.post(url, files=files, data=form_data)
                response.raise_for_status()

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/zip" not in content_type:
            detail = ""
            try:
                detail = json.dumps(response.json(), ensure_ascii=False)
            except Exception:
                detail = response.text[:500]
            raise RuntimeError(f"MinerU local API did not return zip results: {detail}")

        markdown, image_assets, metadata_assets = self._parse_result_zip(response.content)
        page_count = _extract_page_count(metadata_assets)
        if not page_count:
            page_count = await self._count_pages(path)

        return ConversionResult(
            markdown=markdown,
            page_count=page_count or 0,
            image_assets=image_assets or None,
            metadata_assets=metadata_assets or None,
        )

    @staticmethod
    def _parse_result_zip(zip_bytes: bytes) -> tuple[str, dict[str, bytes], dict[str, bytes]]:
        image_assets: dict[str, bytes] = {}
        metadata_assets: dict[str, bytes] = {}

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
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
