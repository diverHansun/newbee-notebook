from __future__ import annotations

import os
import asyncio
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import (
    MinerULocalConverter,
)
from newbee_notebook.infrastructure.document_processing.mineru_title_aided import (
    prepare_mineru_title_aided_runtime,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.requires_api]


def _require_enabled_e2e() -> None:
    if os.getenv("RUN_MINERU_TITLE_AIDED_E2E") != "1":
        pytest.skip("Set RUN_MINERU_TITLE_AIDED_E2E=1 to run real MinerU + LLM PDF parsing")


def _default_pdf_path() -> Path:
    configured = os.getenv("MINERU_TITLE_AIDED_E2E_PDF")
    if configured:
        return Path(configured)
    return Path(r"C:\Users\Hansun2026\Downloads\数字电子技术基础简明教程_11695986.pdf")


def _resolve_llm_for_e2e() -> SimpleNamespace:
    provider = os.getenv("MINERU_TITLE_AIDED_E2E_PROVIDER", "zhipu").strip().lower()
    if provider == "zhipu":
        return SimpleNamespace(
            provider="zhipu",
            model=os.getenv("MINERU_TITLE_AIDED_E2E_MODEL", "glm-5v-turbo"),
            api_key=os.getenv("ZHIPU_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
            base_url=os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4"),
        )
    if provider == "qwen":
        return SimpleNamespace(
            provider="qwen",
            model=os.getenv("MINERU_TITLE_AIDED_E2E_MODEL", "qwen3.5-plus"),
            api_key=(
                os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("QWEN_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or ""
            ),
            base_url=os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
    pytest.skip(f"Unsupported E2E provider: {provider}")


def _iter_text_levels(payload):
    if isinstance(payload, dict):
        level = payload.get("text_level")
        if isinstance(level, int):
            yield level
        for value in payload.values():
            yield from _iter_text_levels(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_text_levels(item)


def _extract_levels(result) -> list[int]:
    import json

    levels: list[int] = []
    for raw in (result.metadata_assets or {}).values():
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        levels.extend(_iter_text_levels(payload))
    return levels


def test_real_local_mineru_title_aided_improves_title_level_distribution(monkeypatch):
    _require_enabled_e2e()
    pdf_path = _default_pdf_path()
    if not pdf_path.exists():
        pytest.skip(f"E2E PDF does not exist: {pdf_path}")

    llm_runtime = _resolve_llm_for_e2e()
    if not llm_runtime.api_key:
        pytest.skip("No LLM API key configured for MinerU title aided E2E")

    base_url = os.getenv("MINERU_TITLE_AIDED_E2E_API_URL", "http://localhost:8001").rstrip("/")
    try:
        requests.get(f"{base_url}/docs", timeout=5).raise_for_status()
    except Exception as exc:
        pytest.skip(f"Local mineru-api is not reachable at {base_url}: {exc}")

    runtime_path = Path(os.getenv("MINERU_TITLE_AIDED_CONFIG_PATH", "data/mineru/mineru-runtime.json"))
    monkeypatch.setenv("MINERU_TITLE_AIDED_CONFIG_PATH", str(runtime_path))

    converter = MinerULocalConverter(
        base_url=base_url,
        backend=os.getenv("MINERU_TITLE_AIDED_E2E_BACKEND", "hybrid-auto-engine"),
        timeout_seconds=0,
        max_pages_per_batch=25,
        request_retry_attempts=0,
    )

    prepare_mineru_title_aided_runtime(
        {"mode": "local", "title_aided_enabled": False},
        llm_runtime_config=None,
    )
    baseline = asyncio.run(
        converter._convert_range_with_retry(
            pdf_path,
            start_page=15,
            end_page=35,
            total_pages=36,
        )
    )

    prepare_mineru_title_aided_runtime(
        {"mode": "local", "title_aided_enabled": True},
        llm_runtime_config=llm_runtime,
    )
    aided = asyncio.run(
        converter._convert_range_with_retry(
            pdf_path,
            start_page=15,
            end_page=35,
            total_pages=36,
        )
    )

    baseline_levels = _extract_levels(baseline)
    aided_levels = _extract_levels(aided)

    assert aided_levels
    assert any(level > 1 for level in aided_levels)
    assert len(Counter(aided_levels)) >= len(Counter(baseline_levels))
