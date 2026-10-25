import asyncio
import importlib
import mimetypes
from pathlib import Path
from typing import Set

from markitdown import MarkItDown
from markitdown import MissingDependencyException as MarkItDownMissingDependencyException
from markitdown import StreamInfo

from newbee_notebook.core.common.config import is_api_only_runtime

from .base import Converter, ConversionResult


class MarkItDownConverter(Converter):
    """Converter for PDF/Office/HTML/text formats using markitdown."""

    def __init__(self) -> None:
        # MarkItDown 0.1.4 initializes Magika's local ONNX model unconditionally.
        # API-only deployments use its public format converters directly instead.
        self._md = None if is_api_only_runtime() else MarkItDown()
        self._supported: Set[str] = {
            ".pdf",
            ".docx",
            ".doc",
            ".xlsx",
            ".xls",
            ".ppt",
            ".pptx",
            ".epub",
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
    def _convert_without_models(path: Path):
        from markitdown.converters import (
            CsvConverter, DocxConverter, EpubConverter, HtmlConverter,
            PdfConverter, PlainTextConverter, PptxConverter, XlsConverter, XlsxConverter,
        )

        converters = {
            ".pdf": PdfConverter, ".docx": DocxConverter,
            ".xlsx": XlsxConverter, ".xls": XlsConverter,
            ".pptx": PptxConverter, ".epub": EpubConverter,
            ".csv": CsvConverter, ".html": HtmlConverter, ".htm": HtmlConverter,
            ".txt": PlainTextConverter, ".md": PlainTextConverter,
            ".markdown": PlainTextConverter,
        }
        converter_type = converters.get(path.suffix.lower())
        if converter_type is None:
            raise RuntimeError(f"Unsupported format in API-only mode: {path.suffix}; convert to DOCX/PPTX first.")
        info = StreamInfo(extension=path.suffix.lower(), filename=path.name,
                          local_path=str(path), mimetype=mimetypes.guess_type(str(path))[0])
        with path.open("rb") as stream:
            return converter_type().convert(stream, info)

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
            if self._md is None:
                result = await asyncio.to_thread(self._convert_without_models, path)
            else:
                result = await asyncio.to_thread(self._md.convert, str(path))
        except MarkItDownMissingDependencyException as exc:
            raise RuntimeError(
                f"MarkItDown dependency missing for {file_path}: {exc}"
            ) from exc
        markdown = getattr(result, "markdown", None) or str(result)

        if not markdown.strip():
            raise RuntimeError(f"MarkItDown produced empty markdown for: {file_path}")

        return ConversionResult(markdown=markdown, page_count=1)
