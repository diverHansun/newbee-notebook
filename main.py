#!/usr/bin/env python3
"""Root entry for running Newbee Notebook FastAPI service.

This script starts the API app defined in ``newbee_notebook.api.main``.
Infrastructure services (PostgreSQL/Redis/Elasticsearch/Celery) should be
started separately via Docker Compose.
"""

from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Newbee Notebook API runner",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto reload")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (ignored when --reload is set)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.reload and args.workers != 1:
        parser.error("--workers cannot be used with --reload")

    uvicorn.run(
        "newbee_notebook.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
