#!/usr/bin/env python3
"""Upload one or more local files to MediMind document library.

This helper is designed for Windows paths and non-ASCII filenames.
By default it URL-encodes multipart filenames to keep UTF-8 names stable
across shells/tools.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import requests


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _encode_filename(name: str) -> str:
    # Keep common ASCII filename chars untouched.
    return quote(name, safe="._-()[]{} ")


def _guess_content_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _iter_files(paths: Iterable[str], encode_filename: bool):
    handles = []
    multipart = []

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        handle = path.open("rb")
        handles.append(handle)

        upload_name = path.name
        if encode_filename:
            upload_name = _encode_filename(upload_name)

        multipart.append(
            (
                "files",
                (
                    upload_name,
                    handle,
                    _guess_content_type(path),
                ),
            )
        )

    return multipart, handles


def main() -> int:
    _configure_stdout()

    parser = argparse.ArgumentParser(
        description="Upload files to MediMind Library via HTTP multipart/form-data.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Local file paths to upload (supports Windows paths).",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000/api/v1",
        help="API base URL. Default: http://localhost:8000/api/v1",
    )
    parser.add_argument(
        "--endpoint",
        default="/documents/library/upload",
        help="Upload endpoint path. Default: /documents/library/upload",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout in seconds. Default: 120",
    )
    parser.add_argument(
        "--no-encode-filename",
        action="store_true",
        help="Send raw multipart filename instead of UTF-8 URL-encoded filename.",
    )

    args = parser.parse_args()
    base = args.api_base.rstrip("/")
    endpoint = args.endpoint if args.endpoint.startswith("/") else f"/{args.endpoint}"
    url = f"{base}{endpoint}"
    encode_filename = not args.no_encode_filename

    multipart = []
    handles = []
    try:
        multipart, handles = _iter_files(args.files, encode_filename=encode_filename)
        response = requests.post(url, files=multipart, timeout=args.timeout)
    except Exception as exc:
        print(f"[ERROR] Upload request failed: {exc}")
        return 1
    finally:
        for handle in handles:
            try:
                handle.close()
            except Exception:
                pass

    print(f"[HTTP] {response.status_code} {response.reason}")
    try:
        payload = response.json()
    except Exception:
        print(response.text)
        return 1 if response.status_code >= 400 else 0

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if response.status_code >= 400:
        return 1

    total = payload.get("total")
    failed = payload.get("failed") or []
    if total is not None:
        print(f"[INFO] Uploaded documents: {total}")
    if failed:
        print(f"[WARN] Failed uploads: {len(failed)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
