from dataclasses import dataclass
from typing import Optional, Sequence, Protocol


@dataclass
class ConversionResult:
    """Standardized conversion output."""

    markdown: str
    page_count: int = 1
    images: Optional[Sequence[bytes]] = None


class Converter(Protocol):
    """Protocol for document converters."""

    def can_handle(self, ext: str) -> bool: ...

    async def convert(self, file_path: str) -> ConversionResult: ...
