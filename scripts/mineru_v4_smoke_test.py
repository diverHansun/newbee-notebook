#!/usr/bin/env python3
"""Smoke test MinerU v4 Smart Parsing with local files.

Flow:
1) Read MINERU_API_KEY from .env / environment.
2) Group local files into official MinerU cloud batches.
3) Request upload URLs via /api/v4/file-urls/batch.
4) Upload local files with HTTP PUT.
5) Poll /api/v4/extract-results/batch/{batch_id} until every item is done.
6) Download each output zip, extract it, and locate markdown output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv


DONE_STATES = {"done"}
RUNNING_STATES = {"waiting-file", "pending", "running", "converting"}
HTML_EXTENSIONS = {".html", ".htm"}
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".jp2",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class SmokeFile:
    path: Path
    data_id: str


@dataclass(frozen=True)
class SmokeGroup:
    route: str
    files: list[SmokeFile]


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _parse_optional_bool(value: str) -> bool | None:
    normalized = (value or "").strip().lower()
    if normalized in {"", "auto", "none"}:
        return None
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Unsupported bool value: {value}")


def _headers(api_key: str, user_token: Optional[str] = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if user_token:
        headers["token"] = user_token
    return headers


def _request_upload_urls(
    api_base: str,
    api_key: str,
    user_token: Optional[str],
    *,
    file_entries: list[dict[str, Any]],
    timeout: float,
    model_version: str | None,
    enable_formula: bool,
    enable_table: bool,
    language: str,
    is_ocr: bool | None,
) -> tuple[str, list[str]]:
    url = f"{api_base.rstrip('/')}/api/v4/file-urls/batch"
    payload_entries: list[dict[str, Any]] = []
    for entry in file_entries:
        payload_entry = {
            "name": str(entry["name"]),
            "data_id": str(entry["data_id"]),
        }
        if is_ocr is not None:
            payload_entry["is_ocr"] = is_ocr
        payload_entries.append(payload_entry)

    payload: dict[str, Any] = {
        "files": payload_entries,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "language": language,
    }
    if model_version:
        payload["model_version"] = model_version

    headers = _headers(api_key, user_token)
    headers["Content-Type"] = "application/json"

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()

    if body.get("code") != 0:
        raise RuntimeError(f"file-urls/batch failed: {json.dumps(body, ensure_ascii=False)}")

    data = body.get("data") or {}
    batch_id = str(data.get("batch_id") or "").strip()
    file_urls = [str(item) for item in (data.get("file_urls") or []) if str(item).strip()]
    if not batch_id or not file_urls:
        raise RuntimeError(
            f"Missing batch_id or file_urls in response: {json.dumps(body, ensure_ascii=False)}"
        )
    return batch_id, file_urls


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


def _extract_result_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data") or {}
    result = data.get("extract_result")
    if isinstance(result, list):
        return [item or {} for item in result]
    if isinstance(result, dict):
        return [result]
    return []


def _poll_until_done_items(
    api_base: str,
    api_key: str,
    user_token: Optional[str],
    batch_id: str,
    timeout: float,
    poll_interval: float,
    max_wait_seconds: float,
) -> list[dict[str, Any]]:
    started = time.monotonic()
    while True:
        body = _fetch_batch_state(
            api_base=api_base,
            api_key=api_key,
            user_token=user_token,
            batch_id=batch_id,
            timeout=timeout,
        )
        items = _extract_result_items(body)
        states = [str(item.get("state", "")).strip().lower() for item in items]

        failures = [item for item, state in zip(items, states) if state == "failed"]
        if failures:
            failed = failures[0]
            data_id = str(failed.get("data_id") or "").strip()
            err_msg = failed.get("err_msg") or json.dumps(failed, ensure_ascii=False)
            raise RuntimeError(f"MinerU task failed for {data_id or 'unknown'}: {err_msg}")

        if states and all(state in DONE_STATES for state in states):
            return items

        unexpected = sorted({state for state in states if state and state not in RUNNING_STATES})
        if unexpected:
            print(f"[WARN] Unexpected states: {', '.join(unexpected)}. Keep polling...")

        elapsed = time.monotonic() - started
        if elapsed > max_wait_seconds:
            state_text = ",".join(sorted(set(states))) or "unknown"
            raise TimeoutError(
                f"Polling timed out after {max_wait_seconds:.0f}s. Last states: {state_text}"
            )

        print(f"[INFO] batch_id={batch_id} states={','.join(states) or 'unknown'}")
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


def _default_data_id(prefix: str, file_path: Path, index: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{index:02d}_{file_path.stem}_{ts}".replace(" ", "_")


def _validate_files(paths: list[Path]) -> list[Path]:
    validated: list[Path] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type for MinerU cloud smoke test: {path.name}"
            )
        validated.append(path)
    return validated


def _build_groups(files: list[SmokeFile], max_batch_size: int) -> list[SmokeGroup]:
    grouped: dict[str, list[SmokeFile]] = {"default": [], "html": []}
    for file in files:
        route = "html" if file.path.suffix.lower() in HTML_EXTENSIONS else "default"
        grouped[route].append(file)

    groups: list[SmokeGroup] = []
    for route in ("default", "html"):
        items = grouped[route]
        for start in range(0, len(items), max_batch_size):
            groups.append(SmokeGroup(route=route, files=items[start:start + max_batch_size]))
    return groups


def main() -> int:
    _configure_stdout()
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Smoke test MinerU v4 Smart Parsing for local files -> Markdown.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more local files to test (pdf/doc/docx/ppt/pptx/html/images).",
    )
    parser.add_argument(
        "--api-base",
        default=os.getenv("MINERU_V4_API_BASE", "https://mineru.net"),
        help="MinerU API base URL (default from MINERU_V4_API_BASE or https://mineru.net).",
    )
    parser.add_argument(
        "--model-version",
        default=os.getenv("MINERU_V4_MODEL_VERSION", "vlm"),
        help="Model version for non-HTML files: pipeline | vlm (default: vlm).",
    )
    parser.add_argument(
        "--user-token",
        default=os.getenv("MINERU_USER_TOKEN", ""),
        help="Optional token header value (user unique id).",
    )
    parser.add_argument(
        "--data-id-prefix",
        default="smoke",
        help="Prefix used to generate per-file data_id values.",
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
        "--max-batch-size",
        type=int,
        default=50,
        help="Maximum files per MinerU batch request (default: 50).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/mineru_v4_smoke",
        help="Directory to store downloaded/extracted results.",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("MINERU_V4_LANGUAGE", "ch"),
        help="MinerU language parameter (default: ch).",
    )
    parser.add_argument(
        "--is-ocr",
        default=os.getenv("MINERU_V4_IS_OCR", "auto"),
        help="OCR flag: auto | true | false (default: auto).",
    )
    parser.add_argument(
        "--enable-formula",
        dest="enable_formula",
        action="store_true",
        help="Enable formula parsing.",
    )
    parser.add_argument(
        "--disable-formula",
        dest="enable_formula",
        action="store_false",
        help="Disable formula parsing.",
    )
    parser.add_argument(
        "--enable-table",
        dest="enable_table",
        action="store_true",
        help="Enable table parsing.",
    )
    parser.add_argument(
        "--disable-table",
        dest="enable_table",
        action="store_false",
        help="Disable table parsing.",
    )
    parser.set_defaults(
        enable_formula=(os.getenv("MINERU_V4_ENABLE_FORMULA", "true").strip().lower() not in {"0", "false", "no", "off"}),
        enable_table=(os.getenv("MINERU_V4_ENABLE_TABLE", "true").strip().lower() not in {"0", "false", "no", "off"}),
    )
    args = parser.parse_args()

    api_key = (os.getenv("MINERU_API_KEY") or os.getenv("mineru_api_key") or "").strip()
    if not api_key:
        print("[ERROR] MINERU_API_KEY (or mineru_api_key) is empty. Please set it in .env first.")
        return 1

    try:
        is_ocr = _parse_optional_bool(args.is_ocr)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if args.max_batch_size <= 0:
        print("[ERROR] --max-batch-size must be greater than 0.")
        return 1

    try:
        input_paths = _validate_files([Path(value).expanduser() for value in args.files])
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    smoke_files = [
        SmokeFile(
            path=path,
            data_id=_default_data_id(args.data_id_prefix, path, index),
        )
        for index, path in enumerate(input_paths, start=1)
    ]
    groups = _build_groups(smoke_files, max_batch_size=args.max_batch_size)

    output_root = Path(args.output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Files: {len(smoke_files)}")
    print(f"[INFO] API base: {args.api_base}")
    print(f"[INFO] Default model version: {args.model_version}")
    print(f"[INFO] enable_formula={args.enable_formula} enable_table={args.enable_table}")
    print(f"[INFO] language={args.language} is_ocr={args.is_ocr}")

    user_token = args.user_token.strip() or None
    if user_token:
        print("[INFO] token header: enabled")
    else:
        print("[INFO] token header: disabled (MINERU_USER_TOKEN not set)")

    downloaded_outputs: list[tuple[SmokeFile, str, Path, Path, list[Path]]] = []

    try:
        for group in groups:
            file_entries = [
                {
                    "name": smoke_file.path.name,
                    "data_id": smoke_file.data_id,
                }
                for smoke_file in group.files
            ]
            route_model_version = "MinerU-HTML" if group.route == "html" else args.model_version
            print(
                f"[INFO] Requesting batch route={group.route} "
                f"files={len(group.files)} model_version={route_model_version}"
            )
            batch_id, upload_urls = _request_upload_urls(
                api_base=args.api_base,
                api_key=api_key,
                user_token=user_token,
                file_entries=file_entries,
                timeout=args.timeout,
                model_version=route_model_version,
                enable_formula=args.enable_formula,
                enable_table=args.enable_table,
                language=args.language,
                is_ocr=is_ocr,
            )

            if len(upload_urls) != len(group.files):
                raise RuntimeError(
                    f"Upload URL count mismatch for batch {batch_id}: "
                    f"expected={len(group.files)} actual={len(upload_urls)}"
                )

            print(f"[INFO] batch_id: {batch_id}")
            for smoke_file, upload_url in zip(group.files, upload_urls, strict=True):
                print(f"[INFO] Uploading: {smoke_file.path.name}")
                _upload_file(upload_url=upload_url, file_path=smoke_file.path, timeout=args.timeout)

            print(f"[INFO] Polling parsing result for batch {batch_id}...")
            items = _poll_until_done_items(
                api_base=args.api_base,
                api_key=api_key,
                user_token=user_token,
                batch_id=batch_id,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                max_wait_seconds=args.max_wait_seconds,
            )
            item_map = {
                str(item.get("data_id") or "").strip(): item
                for item in items
                if str(item.get("data_id") or "").strip()
            }

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            for smoke_file in group.files:
                result_item = item_map.get(smoke_file.data_id)
                if not result_item:
                    raise RuntimeError(f"Result is missing data_id={smoke_file.data_id}")

                full_zip_url = str(result_item.get("full_zip_url") or "").strip()
                if not full_zip_url:
                    raise RuntimeError(
                        "Task done but full_zip_url missing: "
                        f"{json.dumps(result_item, ensure_ascii=False)}"
                    )

                zip_path = output_root / f"{smoke_file.path.stem}_{stamp}_{batch_id}_{smoke_file.data_id}.zip"
                extract_dir = output_root / f"{smoke_file.path.stem}_{stamp}_{batch_id}_{smoke_file.data_id}"
                print(f"[INFO] Downloading result zip for {smoke_file.path.name} -> {zip_path}")
                _download_file(str(full_zip_url), zip_path, timeout=max(args.timeout, 120.0))
                _extract_zip(zip_path, extract_dir)

                markdown_files = _find_markdown(extract_dir)
                if not markdown_files:
                    raise RuntimeError(f"No markdown file found in extracted directory: {extract_dir}")

                downloaded_outputs.append((smoke_file, batch_id, zip_path, extract_dir, markdown_files))

        print("[SUCCESS] MinerU v4 smoke test passed.")
        for smoke_file, batch_id, zip_path, extract_dir, markdown_files in downloaded_outputs:
            print(f"[OUTPUT] file={smoke_file.path}")
            print(f"[OUTPUT] data_id={smoke_file.data_id}")
            print(f"[OUTPUT] batch_id={batch_id}")
            print(f"[OUTPUT] zip={zip_path}")
            print(f"[OUTPUT] extracted_dir={extract_dir}")
            for index, markdown in enumerate(markdown_files, start=1):
                print(f"[OUTPUT] markdown_{index}={markdown}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Smoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
