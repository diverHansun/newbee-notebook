"""PDF converter using pypdf for text extraction.

This converter handles PDFs with embedded text layers.
For scanned/image PDFs, use a MinerU converter (requires OCR capabilities).
"""

import asyncio
from pathlib import Path

from pypdf import PdfReader

from .base import Converter, ConversionResult


class PyPdfConverter(Converter):
    """Converter for PDFs with embedded text using pypdf.

    Note: This converter can only extract text from PDFs that have
    embedded text layers. Scanned/image PDFs will return empty content.
    For such PDFs, use MinerU which has OCR capabilities.
    """

    def can_handle(self, ext: str) -> bool:
        return ext.lower() == ".pdf"

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        def _extract() -> tuple[str, int]:
            # Pass an explicit file handle so it's closed promptly after extraction.
            with path.open("rb") as f:
                reader = PdfReader(f)
                text_parts: list[str] = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                page_count = len(reader.pages)
            return "\n\n".join(text_parts), page_count

        markdown, page_count = await asyncio.to_thread(_extract)

        # If there's no embedded text layer, treat this PDF as image/scanned and fail fast.
        if not markdown.strip():
            raise RuntimeError(
                "PDF has no extractable text. It may be scanned/image-based. "
                f"Use MinerU or an OCR service for: {file_path}"
            )

        return ConversionResult(markdown=markdown, page_count=page_count)
