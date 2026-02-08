import asyncio
from pathlib import Path

from mineru_kie_sdk import MineruKIEClient
from pypdf import PdfReader

from .base import Converter, ConversionResult


class MinerUCloudConverter(Converter):
    """Converter for PDF files via MinerU cloud service SDK."""

    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
    MAX_PDF_PAGES = 10

    def __init__(
        self,
        pipeline_id: str,
        base_url: str = "https://mineru.net/api/kie",
        timeout_seconds: int = 300,
        poll_interval: int = 5,
        request_timeout_seconds: int = 30,
    ) -> None:
        pipeline_id = (pipeline_id or "").strip()
        if not pipeline_id:
            raise ValueError("pipeline_id is required for MinerU cloud mode")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than 0")

        self.client = MineruKIEClient(
            pipeline_id=pipeline_id,
            base_url=base_url,
            timeout=request_timeout_seconds,
        )
        self.processing_timeout = int(timeout_seconds)
        self.poll_interval = int(poll_interval)

    def can_handle(self, ext: str) -> bool:
        # MinerU is only used for PDF in this project.
        return ext.lower() == ".pdf"

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        await self._check_limits(path)

        file_ids = await asyncio.to_thread(self.client.upload_file, path)
        results = await asyncio.to_thread(
            self.client.get_result,
            file_ids=file_ids,
            timeout=self.processing_timeout,
            poll_interval=self.poll_interval,
        )

        parse_result = results.get("parse") or {}
        markdown = (
            parse_result.get("md_content")
            or parse_result.get("markdown")
            or parse_result.get("content")
            or ""
        )
        if not markdown:
            raise RuntimeError("MinerU cloud service returned empty markdown")

        page_count = parse_result.get("page_count") or parse_result.get("page_num") or 0
        if not page_count:
            page_count = await self._count_pages(path)

        return ConversionResult(
            markdown=markdown,
            page_count=page_count or 1,
            images=None,
        )

    async def _check_limits(self, path: Path) -> None:
        size = path.stat().st_size
        if size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too large for MinerU cloud ({size / 1024 / 1024:.1f}MB > 100MB)"
            )

        if path.suffix.lower() == ".pdf":
            page_count = await self._count_pages(path)
            if page_count > self.MAX_PDF_PAGES:
                raise ValueError(
                    f"PDF has too many pages for MinerU cloud ({page_count} > 10)"
                )

    @staticmethod
    async def _count_pages(path: Path) -> int:
        def _count() -> int:
            with path.open("rb") as f:
                return len(PdfReader(f).pages)

        try:
            return await asyncio.to_thread(_count)
        except Exception:
            return 0
