from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from newbee_notebook.application.services.video_service import VideoSummaryNotFoundError
from newbee_notebook.core.skills import SkillContext
from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.skills.video.provider import VideoSkillProvider
from newbee_notebook.skills.video.tools import (
    build_delete_summary_tool,
    build_discover_videos_tool,
    build_get_video_content_tool,
    build_list_summaries_tool,
    build_read_summary_tool,
    build_summarize_video_tool,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def video_service():
    return AsyncMock()


def _make_summary(summary_id: str = "summary-1") -> VideoSummary:
    return VideoSummary(
        summary_id=summary_id,
        notebook_id="nb-1",
        platform="bilibili",
        video_id="BV1xx411c7mD",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        title="Video title",
        summary_content="## Summary",
        status="completed",
    )


@pytest.mark.anyio
async def test_list_summaries_tool_formats_items(video_service):
    video_service.list_by_notebook.return_value = [_make_summary()]
    tool = build_list_summaries_tool(service=video_service, notebook_id="nb-1")

    result = await tool.execute({})

    assert result.error is None
    assert "Found 1 video summar" in result.content
    assert "Video title" in result.content
    video_service.list_by_notebook.assert_awaited_once_with("nb-1", status=None)


@pytest.mark.anyio
async def test_read_and_summarize_tools_return_metadata(video_service):
    video_service.get.return_value = _make_summary("summary-2")
    video_service.summarize.return_value = _make_summary("summary-2")

    read_tool = build_read_summary_tool(service=video_service)
    summarize_tool = build_summarize_video_tool(service=video_service, notebook_id="nb-1")

    read_result = await read_tool.execute({"summary_id": "summary-2"})
    summarize_result = await summarize_tool.execute({"url_or_bvid": "BV1xx411c7mD"})

    assert read_result.error is None
    assert read_result.metadata["summary_id"] == "summary-2"
    assert summarize_result.error is None
    assert summarize_result.metadata["summary_id"] == "summary-2"
    video_service.get.assert_awaited_once_with("summary-2")
    video_service.summarize.assert_awaited_once_with("BV1xx411c7mD", notebook_id="nb-1")


@pytest.mark.anyio
async def test_delete_summary_tool_handles_not_found(video_service):
    video_service.delete.side_effect = VideoSummaryNotFoundError("missing")
    tool = build_delete_summary_tool(service=video_service)

    result = await tool.execute({"summary_id": "missing"})

    assert result.error == "video_summary_not_found"


@pytest.mark.anyio
async def test_discover_videos_tool_routes_to_source_specific_service(video_service):
    video_service.search_videos.return_value = [
        {"title": "Search Result", "video_id": "BV1search"}
    ]
    video_service.get_related_videos.return_value = [
        {"title": "Related Result", "video_id": "BV1related"}
    ]
    tool = build_discover_videos_tool(service=video_service)

    search_result = await tool.execute({"source": "search", "keyword": "macro", "page": 2})
    related_result = await tool.execute({"source": "related", "url_or_bvid": "BV1xx411c7mD"})

    assert search_result.error is None
    assert "Search Result" in search_result.content
    assert related_result.error is None
    assert "Related Result" in related_result.content
    video_service.search_videos.assert_awaited_once_with("macro", page=2)
    video_service.get_related_videos.assert_awaited_once_with("BV1xx411c7mD")


@pytest.mark.anyio
async def test_get_video_content_tool_supports_subtitle_and_ai_conclusion(video_service):
    video_service.get_video_subtitle.return_value = ("subtitle text", [{"lang": "zh"}])
    video_service.get_video_ai_conclusion.return_value = "ai conclusion text"
    tool = build_get_video_content_tool(service=video_service)

    subtitle_result = await tool.execute({"url_or_bvid": "BV1subtitle", "type": "subtitle"})
    ai_result = await tool.execute({"url_or_bvid": "BV1subtitle", "type": "ai_conclusion"})

    assert subtitle_result.error is None
    assert subtitle_result.content == "subtitle text"
    assert subtitle_result.metadata["items"] == [{"lang": "zh"}]
    assert ai_result.error is None
    assert ai_result.content == "ai conclusion text"
    video_service.get_video_subtitle.assert_awaited_once_with("BV1subtitle")
    video_service.get_video_ai_conclusion.assert_awaited_once_with("BV1subtitle")


def test_video_skill_provider_builds_manifest(video_service):
    provider = VideoSkillProvider(video_service=video_service)

    manifest = provider.build_manifest(
        SkillContext(
            notebook_id="nb-1",
            activated_command="/video",
            request_message="summarize BV1xx411c7mD",
        )
    )

    assert manifest.name == "video"
    assert manifest.slash_command == "/video"
    assert manifest.force_first_tool_call is True
    assert manifest.confirmation_required == frozenset(
        {"delete_summary", "disassociate_notebook", "update_summary"}
    )
    assert "discover_videos" in manifest.system_prompt_addition
    assert "get_video_content" in manifest.system_prompt_addition
    assert [tool.name for tool in manifest.tools] == [
        "discover_videos",
        "get_video_info",
        "get_video_content",
        "summarize_video",
        "list_summaries",
        "read_summary",
        "update_summary",
        "delete_summary",
        "associate_notebook",
        "disassociate_notebook",
    ]
