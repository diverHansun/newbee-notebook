
import asyncio
from pathlib import Path
from typing import Set

from markitdown import MarkItDown

from .base import Converter, ConversionResult


class MarkItDownConverter(Converter):
    """Converter for Office/HTML/text formats using markitdown."""

    def __init__(self) -> None:
        self._md = MarkItDown()
        self._supported: Set[str] = {
            ".docx",
            ".doc",
            ".xlsx",
            ".xls",
            ".pptx",
            ".csv",
            ".txt",
            ".md",
            ".markdown",
            ".html",
            ".htm",
        }

    def can_handle(self, ext: str) -> bool:
        return ext.lower() in self._supported

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        # markitdown is synchronous; offload to thread to avoid blocking event loop
        result = await asyncio.to_thread(self._md.convert, str(path))
        markdown = getattr(result, "markdown", None) or str(result)

        return ConversionResult(markdown=markdown, page_count=1)
