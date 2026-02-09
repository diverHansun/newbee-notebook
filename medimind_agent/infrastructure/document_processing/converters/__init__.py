"""Document format converters.

This module provides converters to transform various document formats
to unified Markdown:
    - MinerUCloudConverter: PDF -> Markdown (via MinerU v4 cloud API)
    - MinerULocalConverter: PDF -> Markdown (via local MinerU API)
    - PyPdfConverter: PDF -> Markdown (local, text PDFs only)
    - MarkItDownConverter: Office/HTML/text -> Markdown (local processing)
"""

from .base import Converter, ConversionResult
from .markitdown_converter import MarkItDownConverter
from .mineru_cloud_converter import MinerUCloudConverter
from .mineru_local_converter import MinerULocalConverter
from .pypdf_converter import PyPdfConverter

__all__ = [
    "Converter",
    "ConversionResult",
    "MarkItDownConverter",
    "MinerUCloudConverter",
    "MinerULocalConverter",
    "PyPdfConverter",
]
