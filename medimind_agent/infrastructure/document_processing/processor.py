import logging
import time
from pathlib import Path
from typing import Optional, List

import httpx
import requests

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
from medimind_agent.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
)
from medimind_agent.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
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


def _parse_int(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class DocumentProcessor:
    """Route to appropriate converter and persist markdown output."""

    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = config or get_document_processing_config()
        dp_cfg = cfg.get("document_processing", {}) if cfg else {}

        self.documents_dir = dp_cfg.get("documents_dir") or get_documents_directory()
        mineru_enabled = _parse_bool(dp_cfg.get("mineru_enabled"), True)
        mode = str(dp_cfg.get("mineru_mode", "cloud")).strip().lower()
        mineru_unavailable_cooldown = _parse_float(
            dp_cfg.get("unavailable_cooldown_seconds"),
            300.0,
        )

        # PDF converters: MinerU (with OCR) -> PyPdf (text PDFs only)
        # Other formats: MarkItDown
        converters: List[Converter] = []
        if mineru_enabled:
            if mode == "cloud":
                cloud_cfg = dp_cfg.get("mineru_cloud", {}) or {}
                api_key = str(cloud_cfg.get("api_key", "") or "").strip()
                if api_key:
                    try:
                        converters.append(
                            MinerUCloudConverter(
                                api_key=api_key,
                                api_base=str(cloud_cfg.get("api_base", "https://mineru.net")),
                                timeout_seconds=_parse_int(cloud_cfg.get("timeout_seconds"), 60),
                                poll_interval=_parse_int(cloud_cfg.get("poll_interval"), 5),
                                max_wait_seconds=_parse_int(cloud_cfg.get("max_wait_seconds"), 1800),
                            )
                        )
                    except ValueError as exc:
                        logger.warning(
                            "Failed to initialize MinerU cloud converter: %s",
                            exc,
                        )
                else:
                    logger.warning(
                        "MINERU_MODE=cloud but MINERU_API_KEY is empty. "
                        "MinerU cloud converter disabled; fallback converters will be used."
                    )
            elif mode == "local":
                local_cfg = dp_cfg.get("mineru_local", {}) or {}
                converters.append(
                    MinerULocalConverter(
                        base_url=str(local_cfg.get("api_url", "http://mineru-api:8000")),
                        timeout_seconds=_parse_int(local_cfg.get("timeout_seconds"), 0),
                        backend=str(local_cfg.get("backend", "pipeline")),
                        lang_list=str(local_cfg.get("lang_list", "ch,en")),
                    )
                )
            else:
                logger.warning(
                    "Invalid MINERU_MODE=%s. Expected 'cloud' or 'local'. "
                    "MinerU converter disabled; fallback converters will be used.",
                    mode,
                )
        converters.extend([PyPdfConverter(), MarkItDownConverter()])
        self._converters = converters

        # Circuit breaker: if MinerU is unreachable, avoid paying connect timeouts on every PDF.
        self._mineru_unavailable_until: float = 0.0
        self._mineru_unavailable_cooldown = mineru_unavailable_cooldown

    @staticmethod
    def _is_mineru_converter(converter: Converter) -> bool:
        return isinstance(converter, (MinerUCloudConverter, MinerULocalConverter))

    @staticmethod
    def _should_trip_circuit_breaker(converter: Converter, error: Exception) -> bool:
        if isinstance(converter, MinerUCloudConverter):
            return isinstance(error, (requests.RequestException, TimeoutError))
        if isinstance(converter, MinerULocalConverter):
            return isinstance(error, httpx.RequestError)
        return False

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
            if self._is_mineru_converter(converter) and time.monotonic() < self._mineru_unavailable_until:
                logger.info("MinerU converter is in cooldown window; skipping attempt for %s", file_path)
                continue
            try:
                return await converter.convert(file_path)
            except Exception as e:
                converter_name = type(converter).__name__

                if isinstance(converter, MinerUCloudConverter) and isinstance(e, ValueError):
                    logger.warning(
                        "MinerU cloud request configuration is invalid for %s: %s. Falling back.",
                        file_path,
                        e,
                    )

                # MinerU is an external service; if unreachable, back off for a while.
                if self._should_trip_circuit_breaker(converter, e):
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

                logger.warning("%s failed for %s: %s. Trying next converter...", converter_name, file_path, e)
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
            image_assets=result.image_assets,
            metadata_assets=result.metadata_assets,
            base_root=self.documents_dir,
        )
        return result, content_path, content_size
