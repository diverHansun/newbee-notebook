import asyncio
import io
import json
import logging
import os
import shutil
import socket
import subprocess
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

from .base import Converter, ConversionResult


logger = logging.getLogger(__name__)


class MinerUCloudTransientError(RuntimeError):
    """Transient MinerU cloud error that should trigger fallback/cooldown."""


class MinerUCloudConverter(Converter):
    """Converter for PDF files via MinerU v4 Smart Parsing API."""

    DONE_STATES = {"done"}
    RUNNING_STATES = {"waiting-file", "pending", "running", "converting"}

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://mineru.net",
        timeout_seconds: int = 60,
        poll_interval: int = 5,
        max_wait_seconds: int = 1800,
        enable_curl_fallback: bool = True,
        curl_binary: str = "curl",
        curl_insecure: bool = False,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ValueError("api_key is required for MinerU cloud mode")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        if max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be greater than 0")

        self._api_key = key
        self._api_base = api_base.rstrip("/")
        self._timeout_seconds = int(timeout_seconds)
        self._poll_interval = int(poll_interval)
        self._max_wait_seconds = int(max_wait_seconds)
        self._connect_timeout_seconds = 5
        self._enable_curl_fallback = bool(enable_curl_fallback)
        self._curl_binary = (curl_binary or "curl").strip() or "curl"
        self._curl_insecure = bool(curl_insecure)

    def can_handle(self, ext: str) -> bool:
        return ext.lower() == ".pdf"

    async def convert(self, file_path: str) -> ConversionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        batch_id, upload_url = await asyncio.to_thread(self._request_upload_url, path.name)
        await asyncio.to_thread(self._upload_file, upload_url, path)
        result_item = await asyncio.to_thread(self._poll_until_done, batch_id)

        full_zip_url = str(result_item.get("full_zip_url") or "").strip()
        if not full_zip_url:
            raise RuntimeError(f"MinerU v4 task finished but full_zip_url is missing: {result_item}")

        zip_bytes = await asyncio.to_thread(self._download_zip, full_zip_url)
        markdown, image_assets, metadata_assets, page_count = self._parse_result_zip(zip_bytes)

        if not page_count:
            page_count = await self._count_pages(path)

        return ConversionResult(
            markdown=markdown,
            page_count=page_count or 0,
            image_assets=image_assets or None,
            metadata_assets=metadata_assets or None,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _api_timeout(self) -> tuple[int, int]:
        """Short connect timeout + configurable read timeout for API calls."""
        return self._connect_timeout_seconds, self._timeout_seconds

    def _transfer_timeout(self) -> tuple[int, int]:
        """Longer read timeout for large upload/download transfers."""
        return self._connect_timeout_seconds, max(self._timeout_seconds, 300)

    def _request_upload_url(self, file_name: str) -> tuple[str, str]:
        url = f"{self._api_base}/api/v4/file-urls/batch"
        payload = {"files": [{"name": file_name}]}
        headers = self._headers()
        headers["Content-Type"] = "application/json"

        response = requests.post(url, headers=headers, json=payload, timeout=self._api_timeout())
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(f"MinerU v4 file-urls/batch failed: {json.dumps(body, ensure_ascii=False)}")

        data = body.get("data") or {}
        batch_id = str(data.get("batch_id") or "").strip()
        file_urls = data.get("file_urls") or []
        upload_url = str(file_urls[0]) if file_urls else ""
        if not batch_id or not upload_url:
            raise RuntimeError(
                f"MinerU v4 file-urls/batch missing batch_id/file_urls: {json.dumps(body, ensure_ascii=False)}"
            )
        return batch_id, upload_url

    def _upload_file(self, upload_url: str, file_path: Path) -> None:
        with file_path.open("rb") as handle:
            response = requests.put(upload_url, data=handle, timeout=self._transfer_timeout())
        response.raise_for_status()

    def _poll_until_done(self, batch_id: str) -> dict[str, Any]:
        start = time.monotonic()
        while True:
            item = self._fetch_batch_state(batch_id)
            state = str(item.get("state") or "").strip().lower()

            if state in self.DONE_STATES:
                return item
            if state == "failed":
                err_msg = item.get("err_msg") or "Unknown error"
                raise RuntimeError(f"MinerU v4 task failed: {err_msg}")

            elapsed = time.monotonic() - start
            if elapsed >= self._max_wait_seconds:
                raise TimeoutError(
                    f"MinerU v4 polling timed out after {self._max_wait_seconds}s (last_state={state or 'unknown'})"
                )

            time.sleep(self._poll_interval)

    def _fetch_batch_state(self, batch_id: str) -> dict[str, Any]:
        url = f"{self._api_base}/api/v4/extract-results/batch/{batch_id}"
        response = requests.get(url, headers=self._headers(), timeout=self._api_timeout())
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(
                f"MinerU v4 extract-results failed: {json.dumps(body, ensure_ascii=False)}"
            )

        data = body.get("data") or {}
        result = data.get("extract_result")
        if isinstance(result, list) and result:
            return result[0] or {}
        if isinstance(result, dict):
            return result
        return {}

    def _download_zip(self, full_zip_url: str, max_retries: int = 3) -> bytes:
        """Download result zip with retry on transient SSL/connection errors."""
        last_exc: Exception | None = None
        host = urlparse(full_zip_url).hostname or ""
        resolved_ips = self._resolve_host_ips(host)
        if resolved_ips:
            logger.info("MinerU CDN download target host=%s resolved_ips=%s", host, ",".join(resolved_ips))

        for attempt in range(1, max_retries + 1):
            try:
                with requests.get(full_zip_url, stream=True, timeout=self._transfer_timeout()) as response:
                    response.raise_for_status()
                    chunks = []
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            chunks.append(chunk)
                return b"".join(chunks)
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                wait = 2 ** attempt  # 2s, 4s, 8s
                logger.warning(
                    "MinerU CDN download attempt %d/%d failed host=%s ips=%s (%s), retrying in %ds...",
                    attempt,
                    max_retries,
                    host or "unknown",
                    ",".join(resolved_ips) if resolved_ips else "unknown",
                    type(exc).__name__,
                    wait,
                )
                time.sleep(wait)

        if self._enable_curl_fallback:
            try:
                logger.warning(
                    "MinerU CDN requests download failed; attempting curl fallback host=%s",
                    host or "unknown",
                )
                return self._download_zip_with_curl(full_zip_url, max_retries=max_retries)
            except Exception as curl_exc:  # noqa: BLE001
                raise MinerUCloudTransientError(
                    "MinerU CDN download failed in both requests and curl fallback "
                    f"(host={host or 'unknown'}, "
                    f"ips={','.join(resolved_ips) if resolved_ips else 'unknown'}). "
                    f"requests_error={last_exc}; curl_error={curl_exc}"
                ) from curl_exc

        raise MinerUCloudTransientError(
            "MinerU CDN download failed after "
            f"{max_retries} retries (host={host or 'unknown'}, "
            f"ips={','.join(resolved_ips) if resolved_ips else 'unknown'}): {last_exc}"
        ) from last_exc

    def _download_zip_with_curl(self, full_zip_url: str, max_retries: int = 3) -> bytes:
        """Fallback download via system curl for environments with non-OpenSSL TLS stacks."""
        curl_exec = self._resolve_curl_binary()
        if not curl_exec:
            raise RuntimeError("curl fallback is enabled but curl executable was not found")

        connect_timeout, read_timeout = self._transfer_timeout()
        # Give curl enough total time for large ZIP transfers.
        max_time = max(connect_timeout + read_timeout + 30, 60)

        cmd = [
            curl_exec,
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--connect-timeout",
            str(connect_timeout),
            "--max-time",
            str(max_time),
            "--retry",
            str(max_retries),
            "--retry-delay",
            "1",
            "--retry-all-errors",
            "--output",
            "-",
            full_zip_url,
        ]
        if self._curl_insecure:
            cmd.insert(1, "--insecure")

        completed = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"curl exited with code {completed.returncode}: {stderr or 'no stderr'}")
        if not completed.stdout:
            raise RuntimeError("curl succeeded but returned empty response body")

        return completed.stdout

    def _resolve_curl_binary(self) -> str | None:
        """Resolve configured curl executable path."""
        candidate = self._curl_binary
        if not candidate:
            return None
        if Path(candidate).exists():
            return candidate
        return shutil.which(candidate)

    @staticmethod
    def _resolve_host_ips(host: str) -> list[str]:
        """Resolve DNS for diagnostics; never raise."""
        if not host:
            return []
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except Exception:
            return []
        ips = sorted({str(info[4][0]) for info in infos if info and info[4]})
        return ips

    @staticmethod
    def _parse_result_zip(zip_bytes: bytes) -> tuple[str, dict[str, bytes], dict[str, bytes], int]:
        image_assets: dict[str, bytes] = {}
        metadata_assets: dict[str, bytes] = {}
        page_count = 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names:
                raise RuntimeError("MinerU v4 zip is empty")

            md_candidates = [name for name in names if name.lower().endswith(".md")]
            if not md_candidates:
                raise RuntimeError("MinerU v4 zip has no markdown file")

            markdown_path = next((n for n in md_candidates if n.lower().endswith("/full.md")), md_candidates[0])
            markdown = archive.read(markdown_path).decode("utf-8", errors="replace")

            root_prefix = str(PurePosixPath(markdown_path).parent)
            if root_prefix in {"", "."}:
                root_prefix = ""
            prefix = f"{root_prefix}/" if root_prefix else ""

            for name in names:
                rel = name[len(prefix):] if prefix and name.startswith(prefix) else name
                rel = rel.replace("\\", "/")
                if rel == markdown_path or rel.endswith(".md"):
                    continue

                if rel.startswith("images/"):
                    image_assets[rel] = archive.read(name)
                elif rel.lower().endswith(".json"):
                    metadata_assets[rel] = archive.read(name)

            page_count = _extract_page_count(metadata_assets)

        if "images/" in markdown and not image_assets:
            raise RuntimeError("MinerU v4 markdown references images but no image assets were found")

        return markdown, image_assets, metadata_assets, page_count

    @staticmethod
    async def _count_pages(path: Path) -> int:
        def _count() -> int:
            with path.open("rb") as file:
                return len(PdfReader(file).pages)

        try:
            return await asyncio.to_thread(_count)
        except Exception:
            return 0


def _extract_page_count(metadata_assets: dict[str, bytes]) -> int:
    layout_key = next((name for name in metadata_assets if name.lower().endswith("layout.json")), None)
    if not layout_key:
        return 0
    try:
        payload = json.loads(metadata_assets[layout_key].decode("utf-8"))
    except Exception:
        return 0

    pdf_info = payload.get("pdf_info")
    if isinstance(pdf_info, list):
        return len(pdf_info)
    return 0
