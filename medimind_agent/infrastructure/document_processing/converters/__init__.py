"""Document format converters.

This module provides converters to transform various document formats
to unified Markdown:
    - MinerUConverter: PDF -> Markdown (via MinerU API, supports OCR)
    - PyPdfConverter: PDF -> Markdown (local, text PDFs only)
    - MarkItDownConverter: Office/HTML/text -> Markdown (local processing)
"""

from .base import Converter, ConversionResult
from .markitdown_converter import MarkItDownConverter
from .mineru_converter import MinerUConverter
from .pypdf_converter import PyPdfConverter

__all__ = [
    "Converter",
    "ConversionResult",
    "MarkItDownConverter",
    "MinerUConverter",
    "PyPdfConverter",
]
