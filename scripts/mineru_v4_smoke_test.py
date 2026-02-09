#!/usr/bin/env python3
"""Smoke test MinerU v4 Smart Parsing with a local PDF.

Flow:
1) Read MINERU_API_KEY from .env / environment.
2) Request an upload URL via /api/v4/file-urls/batch.
3) Upload local PDF with HTTP PUT.
4) Poll /api/v4/extract-results/batch/{batch_id} until done.
5) Download output zip, extract it, and locate markdown output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv


DONE_STATES = {"done"}
RUNNING_STATES = {"waiting-file", "pending", "running", "converting"}


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _headers(api_key: str, user_token: Optional[str] = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if user_token:
        headers["token"] = user_token
    return headers


def _request_upload_url(
    api_base: str,
    api_key: str,
    user_token: Optional[str],
    file_name: str,
    model_version: str,
    data_id: Optional[str],
    timeout: float,
) -> tuple[str, str]:
    url = f"{api_base.rstrip('/')}/api/v4/file-urls/batch"
    payload: dict[str, Any] = {
        "files": [{"name": file_name}],
        "model_version": model_version,
    }
    if data_id:
        payload["files"][0]["data_id"] = data_id

    headers = _headers(api_key, user_token)
    headers["Content-Type"] = "application/json"

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if body.get("code") != 0:
        raise RuntimeError(f"file-urls/batch failed: {json.dumps(body, ensure_ascii=False)}")

    data = body.get("data") or {}
    batch_id = data.get("batch_id")
    file_urls = data.get("file_urls") or []
    if not batch_id or not file_urls:
        raise RuntimeError(
            f"Missing batch_id or file_urls in response: {json.dumps(body, ensure_ascii=False)}"
        )
    return str(batch_id), str(file_urls[0])


def _upload_file(upload_url: str, file_path: Path, timeout: float) -> None:
    with file_path.open("rb") as handle:
        response = requests.put(upload_url, data=handle, timeout=timeout)
    response.raise_for_status()


def _fetch_batch_state(
    api_base: str,
    api_key: str,
    user_token: Optional[str],
    batch_id: str,
    timeout: float,
) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/api/v4/extract-results/batch/{batch_id}"
    response = requests.get(url, headers=_headers(api_key, user_token), timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(
            f"extract-results/batch failed: {json.dumps(body, ensure_ascii=False)}"
        )
    return body


def _first_extract_result(body: dict[str, Any]) -> dict[str, Any]:
    data = body.get("data") or {}
    result = data.get("extract_result")
    if isinstance(result, list) and result:
        return result[0] or {}
    if isinstance(result, dict):
        return result
    return {}


def _poll_until_done(
    api_base: str,
    api_key: str,
    user_token: Optional[str],
    batch_id: str,
    timeout: float,
    poll_interval: float,
    max_wait_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        body = _fetch_batch_state(
            api_base=api_base,
            api_key=api_key,
            user_token=user_token,
            batch_id=batch_id,
            timeout=timeout,
        )
        item = _first_extract_result(body)
        state = str(item.get("state", "")).strip().lower()
        err_msg = item.get("err_msg") or ""

        if state in DONE_STATES:
            return item
        if state == "failed":
            raise RuntimeError(f"MinerU task failed: {err_msg or json.dumps(item, ensure_ascii=False)}")
        if state and state not in RUNNING_STATES:
            print(f"[WARN] Unexpected state: {state}. Keep polling...")

        elapsed = time.monotonic() - started
        if elapsed > max_wait_seconds:
            raise TimeoutError(
                f"Polling timed out after {max_wait_seconds:.0f}s. Last state: {state or 'unknown'}"
            )

        progress = item.get("extract_progress") or {}
        extracted_pages = progress.get("extracted_pages")
        total_pages = progress.get("total_pages")
        if extracted_pages is not None and total_pages is not None:
            print(f"[INFO] State={state} progress={extracted_pages}/{total_pages}")
        else:
            print(f"[INFO] State={state or 'unknown'}")
        time.sleep(poll_interval)


def _download_file(url: str, target_path: Path, timeout: float) -> None:
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with target_path.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)


def _extract_zip(zip_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(output_dir)
    return output_dir


def _find_markdown(extracted_dir: Path) -> list[Path]:
    return sorted(p for p in extracted_dir.rglob("*.md") if p.is_file())


def _default_data_id(file_path: Path) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"smoke_{file_path.stem}_{ts}".replace(" ", "_")


def main() -> int:
    _configure_stdout()
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Smoke test MinerU v4 Smart Parsing for local PDF -> Markdown.",
    )
    parser.add_argument("pdf_path", help="Local PDF path to test.")
    parser.add_argument(
        "--api-base",
        default=os.getenv("MINERU_V4_API_BASE", "https://mineru.net"),
        help="MinerU API base URL (default from MINERU_V4_API_BASE or https://mineru.net).",
    )
    parser.add_argument(
        "--model-version",
        default=os.getenv("MINERU_V4_MODEL_VERSION", "vlm"),
        help="Model version: pipeline | vlm | MinerU-HTML (default: vlm).",
    )
    parser.add_argument(
        "--user-token",
        default=os.getenv("MINERU_USER_TOKEN", ""),
        help="Optional token header value (user unique id).",
    )
    parser.add_argument(
        "--data-id",
        default="",
        help="Optional custom data_id. If empty, auto-generate one.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Polling interval in seconds (default: 5).",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=float,
        default=1800.0,
        help="Maximum wait time for parsing result in seconds (default: 1800).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/mineru_v4_smoke",
        help="Directory to store downloaded/extracted results.",
    )
    args = parser.parse_args()

    api_key = (os.getenv("MINERU_API_KEY") or os.getenv("mineru_api_key") or "").strip()
    if not api_key:
        print("[ERROR] MINERU_API_KEY (or mineru_api_key) is empty. Please set it in .env first.")
        return 1

    pdf_path = Path(args.pdf_path).expanduser()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"[ERROR] File not found: {pdf_path}")
        return 1
    if pdf_path.suffix.lower() != ".pdf":
        print(f"[ERROR] Only PDF is supported in this smoke test: {pdf_path.name}")
        return 1

    data_id = args.data_id.strip() or _default_data_id(pdf_path)
    user_token = args.user_token.strip() or None

    output_root = Path(args.output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] PDF: {pdf_path}")
    print(f"[INFO] API base: {args.api_base}")
    print(f"[INFO] Model version: {args.model_version}")
    print(f"[INFO] data_id: {data_id}")
    if user_token:
        print("[INFO] token header: enabled")
    else:
        print("[INFO] token header: disabled (MINERU_USER_TOKEN not set)")

    try:
        batch_id, upload_url = _request_upload_url(
            api_base=args.api_base,
            api_key=api_key,
            user_token=user_token,
            file_name=pdf_path.name,
            model_version=args.model_version,
            data_id=data_id,
            timeout=args.timeout,
        )
        print(f"[INFO] batch_id: {batch_id}")
        print("[INFO] Uploading file...")
        _upload_file(upload_url=upload_url, file_path=pdf_path, timeout=args.timeout)
        print("[INFO] Upload finished.")

        print("[INFO] Polling parsing result...")
        result_item = _poll_until_done(
            api_base=args.api_base,
            api_key=api_key,
            user_token=user_token,
            batch_id=batch_id,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            max_wait_seconds=args.max_wait_seconds,
        )

        full_zip_url = result_item.get("full_zip_url")
        if not full_zip_url:
            raise RuntimeError(
                f"Task done but full_zip_url missing: {json.dumps(result_item, ensure_ascii=False)}"
            )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = output_root / f"{pdf_path.stem}_{stamp}_{batch_id}.zip"
        extract_dir = output_root / f"{pdf_path.stem}_{stamp}_{batch_id}"

        print(f"[INFO] Downloading result zip to: {zip_path}")
        _download_file(str(full_zip_url), zip_path, timeout=max(args.timeout, 120.0))
        _extract_zip(zip_path, extract_dir)

        markdown_files = _find_markdown(extract_dir)
        if not markdown_files:
            raise RuntimeError(f"No markdown file found in extracted directory: {extract_dir}")

        print("[SUCCESS] MinerU v4 smoke test passed.")
        print(f"[OUTPUT] batch_id: {batch_id}")
        print(f"[OUTPUT] zip: {zip_path}")
        print(f"[OUTPUT] extracted_dir: {extract_dir}")
        for idx, md_file in enumerate(markdown_files, start=1):
            print(f"[OUTPUT] markdown_{idx}: {md_file}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Smoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
