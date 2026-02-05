"""Document format converters.

This module provides converters to transform various document formats
to unified Markdown:
    - MinerUConverter: PDF -> Markdown (via MinerU API)
    - MarkItDownConverter: Office/HTML/text -> Markdown (local processing)
"""

from .base import Converter, ConversionResult
from .markitdown_converter import MarkItDownConverter
from .mineru_converter import MinerUConverter

__all__ = [
    "Converter",
    "ConversionResult",
    "MarkItDownConverter",
    "MinerUConverter",
]
