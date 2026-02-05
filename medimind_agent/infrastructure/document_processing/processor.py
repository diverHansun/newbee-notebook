import logging
import os
import time
from pathlib import Path
from typing import Optional, List

import httpx

from medimind_agent.core.common.config import (
    get_documents_directory,
    get_document_processing_config,
)
from medimind_agent.infrastructure.document_processing.converters.base import (
    Converter,
    ConversionResult,
)
from medimind_agent.infrastructure.document_processing.converters.markitdown_converter import (
    MarkItDownConverter,
)
from medimind_agent.infrastructure.document_processing.converters.mineru_converter import (
    MinerUConverter,
)
from medimind_agent.infrastructure.document_processing.converters.pypdf_converter import (
    PyPdfConverter,
)
from medimind_agent.infrastructure.document_processing.store import save_markdown

logger = logging.getLogger(__name__)


def _parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off", ""}:
            return False
    return default


class DocumentProcessor:
    """Route to appropriate converter and persist markdown output."""

    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = config or get_document_processing_config()
        dp_cfg = cfg.get("document_processing", {}) if cfg else {}

        self.documents_dir = dp_cfg.get("documents_dir") or get_documents_directory()
        mineru_enabled = _parse_bool(dp_cfg.get("mineru_enabled"), True)
        timeout = int(dp_cfg.get("mineru_timeout_seconds", 300))
        mineru_unavailable_cooldown = float(dp_cfg.get("mineru_unavailable_cooldown_seconds", 300))
        backend = dp_cfg.get("mineru_backend", "hybrid-auto-engine")
        lang_list = dp_cfg.get("mineru_lang_list", "en,zh")
        base_url = dp_cfg.get("mineru_api_url") or os.getenv("MINERU_API_URL")

        # PDF converters: MinerU (with OCR) -> PyPdf (text PDFs only)
        # Other formats: MarkItDown
        converters: List[Converter] = []
        if mineru_enabled:
            converters.append(
                MinerUConverter(base_url=base_url, timeout_seconds=timeout, backend=backend, lang_list=lang_list)
            )
        converters.extend([PyPdfConverter(), MarkItDownConverter()])
        self._converters = converters

        # Circuit breaker: if MinerU is unreachable, avoid paying connect timeouts on every PDF.
        self._mineru_unavailable_until: float = 0.0
        self._mineru_unavailable_cooldown = mineru_unavailable_cooldown

    def _get_converters_for_ext(self, ext: str) -> List[Converter]:
        """Get all converters that can handle the given extension."""
        return [c for c in self._converters if c.can_handle(ext)]

    async def convert(self, file_path: str) -> ConversionResult:
        """Convert file with fallback support.

        For PDF files, tries MinerU first (with OCR support), then falls back
        to PyPdf for text-based PDFs if MinerU is unavailable.
        For other formats, uses MarkItDown.
        """
        ext = Path(file_path).suffix.lower()
        converters = self._get_converters_for_ext(ext)

        if not converters:
            raise RuntimeError(f"Unsupported file type: {ext}")

        last_error: Optional[Exception] = None
        for converter in converters:
            if isinstance(converter, MinerUConverter) and time.monotonic() < self._mineru_unavailable_until:
                continue
            try:
                return await converter.convert(file_path)
            except Exception as e:
                converter_name = type(converter).__name__

                # MinerU is an external HTTP service; if it's unreachable, back off for a while.
                if isinstance(converter, MinerUConverter) and isinstance(e, httpx.RequestError):
                    self._mineru_unavailable_until = time.monotonic() + self._mineru_unavailable_cooldown
                    logger.warning(
                        "MinerU service appears unavailable (%s) for %s. "
                        "Disabling MinerU attempts for %.0fs and falling back.",
                        str(e),
                        file_path,
                        self._mineru_unavailable_cooldown,
                    )
                    last_error = e
                    continue

                logger.warning(
                    f"{converter_name} failed for {file_path}: {e}. "
                    f"Trying next converter..."
                )
                last_error = e
                continue

        raise RuntimeError(
            f"All converters failed for {file_path}. Last error: {last_error}"
        )

    async def process_and_save(
        self,
        document_id: str,
        file_path: str,
    ) -> tuple[ConversionResult, str, int]:
        """
        Convert file to markdown and persist to documents directory.

        Returns:
            (conversion_result, relative_content_path, content_size_bytes)
        """
        result = await self.convert(file_path)
        content_path, content_size = save_markdown(
            document_id=document_id,
            markdown=result.markdown,
            images=result.images,
            base_root=self.documents_dir,
        )
        return result, content_path, content_size
