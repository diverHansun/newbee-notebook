from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from newbee_notebook.infrastructure.document_processing.converters.base import (
    ConversionResult,
)
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
)


@dataclass(frozen=True)
class CloudBatchDocument:
    document_id: str
    title: str
    local_path: Path


@dataclass(frozen=True)
class CloudBatchGroup:
    route: str
    items: list[CloudBatchDocument]


@dataclass(frozen=True)
class CloudBatchConversion:
    document_id: str
    result: ConversionResult

    @property
    def markdown(self) -> str:
        return self.result.markdown


@dataclass(frozen=True)
class CloudBatchFailure:
    document_id: str
    error: Exception


def _resolve_route(path: Path) -> str:
    return "html" if path.suffix.lower() in {".html", ".htm"} else "default"


def build_cloud_batch_groups(
    documents: list[CloudBatchDocument],
    *,
    max_batch_size: int = 50,
) -> list[CloudBatchGroup]:
    if max_batch_size <= 0:
        raise ValueError("max_batch_size must be greater than 0")

    grouped: dict[str, list[CloudBatchDocument]] = {"default": [], "html": []}
    for document in documents:
        grouped[_resolve_route(document.local_path)].append(document)

    result: list[CloudBatchGroup] = []
    for route in ("default", "html"):
        items = grouped[route]
        for start in range(0, len(items), max_batch_size):
            result.append(CloudBatchGroup(route=route, items=items[start:start + max_batch_size]))
    return result


class MinerUCloudBatchService:
    """Coordinate one MinerU cloud batch for multiple documents."""

    def __init__(self, converter: MinerUCloudConverter):
        self._converter = converter

    def convert_documents(
        self,
        documents: list[CloudBatchDocument],
    ) -> tuple[list[CloudBatchConversion], list[CloudBatchFailure]]:
        results: list[CloudBatchConversion] = []
        failures: list[CloudBatchFailure] = []

        for group in build_cloud_batch_groups(documents):
            group_results, group_failures = self._convert_group(group)
            results.extend(group_results)
            failures.extend(group_failures)

        return results, failures

    def _convert_group(
        self,
        group: CloudBatchGroup,
    ) -> tuple[list[CloudBatchConversion], list[CloudBatchFailure]]:
        batch_candidates: list[CloudBatchDocument] = []
        failures: list[CloudBatchFailure] = []
        for document in group.items:
            try:
                self._validate_document(document)
            except Exception as exc:  # noqa: BLE001
                failures.append(CloudBatchFailure(document_id=document.document_id, error=exc))
                continue
            batch_candidates.append(document)

        if not batch_candidates:
            return [], failures

        try:
            results = self._run_remote_batch(group.route, batch_candidates)
        except Exception as exc:  # noqa: BLE001
            failures.extend(
                CloudBatchFailure(document_id=document.document_id, error=exc)
                for document in batch_candidates
            )
            return [], failures

        return results, failures

    def _run_remote_batch(
        self,
        route: str,
        documents: list[CloudBatchDocument],
    ) -> list[CloudBatchConversion]:
        file_entries = [
            {
                "name": document.local_path.name,
                "data_id": document.document_id,
            }
            for document in documents
        ]
        model_version = "MinerU-HTML" if route == "html" else None
        batch_id, upload_urls = self._converter._request_upload_urls(
            file_entries,
            model_version=model_version,
        )
        if len(upload_urls) != len(documents):
            raise RuntimeError(
                "MinerU v4 file-urls/batch returned mismatched upload URL count "
                f"(expected={len(documents)}, actual={len(upload_urls)})"
            )

        for document, upload_url in zip(documents, upload_urls, strict=True):
            self._converter._upload_file(upload_url, document.local_path)

        items = self._converter._poll_until_done_items(batch_id)
        item_map = {
            str(item.get("data_id") or "").strip(): item
            for item in items
            if str(item.get("data_id") or "").strip()
        }

        results: list[CloudBatchConversion] = []
        for document in documents:
            item = item_map.get(document.document_id)
            if not item:
                raise RuntimeError(
                    "MinerU v4 batch result is missing data_id="
                    f"{document.document_id}"
                )
            full_zip_url = str(item.get("full_zip_url") or "").strip()
            if not full_zip_url:
                raise RuntimeError(
                    "MinerU v4 task finished but full_zip_url is missing "
                    f"for data_id={document.document_id}"
                )
            zip_bytes = self._converter._download_zip(full_zip_url)
            markdown, image_assets, metadata_assets, page_count = self._converter._parse_result_zip(zip_bytes)
            results.append(
                CloudBatchConversion(
                    document_id=document.document_id,
                    result=ConversionResult(
                        markdown=markdown,
                        page_count=page_count or 0,
                        image_assets=image_assets or None,
                        metadata_assets=metadata_assets or None,
                    ),
                )
            )

        return results

    def _validate_document(self, document: CloudBatchDocument) -> None:
        path = document.local_path
        page_count = self._count_pdf_pages(path) if path.suffix.lower() == ".pdf" else None
        self._converter._validate_cloud_limits(path, page_count)

    @staticmethod
    def _count_pdf_pages(path: Path) -> int | None:
        try:
            with path.open("rb") as file:
                return len(PdfReader(file).pages)
        except Exception:
            return None
