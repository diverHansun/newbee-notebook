import os
from pathlib import Path
from typing import Optional, List

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
from medimind_agent.infrastructure.document_processing.store import save_markdown


class DocumentProcessor:
    """Route to appropriate converter and persist markdown output."""

    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = config or get_document_processing_config()
        dp_cfg = cfg.get("document_processing", {}) if cfg else {}

        self.documents_dir = dp_cfg.get("documents_dir") or get_documents_directory()
        timeout = int(dp_cfg.get("mineru_timeout_seconds", 300))
        backend = dp_cfg.get("mineru_backend", "hybrid-auto-engine")
        lang_list = dp_cfg.get("mineru_lang_list", "en,zh")
        base_url = dp_cfg.get("mineru_api_url") or os.getenv("MINERU_API_URL")

        self._converters: List[Converter] = [
            MinerUConverter(base_url=base_url, timeout_seconds=timeout, backend=backend, lang_list=lang_list),
            MarkItDownConverter(),
        ]

    def _select_converter(self, ext: str) -> Converter:
        for converter in self._converters:
            if converter.can_handle(ext):
                return converter
        raise RuntimeError(f"Unsupported file type: {ext}")

    async def convert(self, file_path: str) -> ConversionResult:
        ext = Path(file_path).suffix.lower()
        converter = self._select_converter(ext)
        return await converter.convert(file_path)

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
