from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class ConversionResult:
    """Standardized conversion output."""

    markdown: str
    page_count: int = 1
    # Map from source markdown path (e.g. "images/abc.jpg") to image bytes.
    image_assets: Optional[dict[str, bytes]] = None
    # Optional metadata artifacts (json/text/binary) to persist under assets/meta.
    metadata_assets: Optional[dict[str, bytes]] = None


class Converter(Protocol):
    """Protocol for document converters."""

    def can_handle(self, ext: str) -> bool: ...

    async def convert(self, file_path: str) -> ConversionResult: ...
