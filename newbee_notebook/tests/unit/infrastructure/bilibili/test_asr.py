from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_asr_pipeline_concatenates_results_in_order():
    from newbee_notebook.infrastructure.bilibili.asr import AsrPipeline

    pipeline = AsrPipeline()

    result = await pipeline._merge_results(["one", "", "two", "three"])

    assert result == "one two three"
