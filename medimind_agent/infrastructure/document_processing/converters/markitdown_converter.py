import asyncio
import importlib
from pathlib import Path
from typing import Set

from markitdown import MarkItDown
from markitdown import MissingDependencyException as MarkItDownMissingDependencyException

from .base import Converter, ConversionResult


class MarkItDownConverter(Converter):
    """Converter for PDF/Office/HTML/text formats using markitdown."""

    def __init__(self) -> None:
        self._md = MarkItDown()
        self._supported: Set[str] = {
            ".pdf",
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
        self._pdf_dependency_ready = self._check_pdf_dependency()

    def can_handle(self, ext: str) -> bool:
        return ext.lower() in self._supported

    @staticmethod
    def _check_pdf_dependency() -> bool:
        try:
            importlib.import_module("pdfminer")
            importlib.import_module("pdfminer.high_level")
            return True
        except Exception:
            return False

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf" and not self._pdf_dependency_ready:
            raise RuntimeError(
                "MarkItDown PDF dependency is missing (pdfminer.six). "
                "Install markitdown[pdf] or markitdown[all]."
            )

        # markitdown is synchronous; offload to thread to avoid blocking event loop
        try:
            result = await asyncio.to_thread(self._md.convert, str(path))
        except MarkItDownMissingDependencyException as exc:
            raise RuntimeError(
                f"MarkItDown dependency missing for {file_path}: {exc}"
            ) from exc
        markdown = getattr(result, "markdown", None) or str(result)

        if not markdown.strip():
            raise RuntimeError(f"MarkItDown produced empty markdown for: {file_path}")

        return ConversionResult(markdown=markdown, page_count=1)
