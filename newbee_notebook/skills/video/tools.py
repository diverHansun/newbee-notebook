"""Tool factories for the /video runtime skill."""

from __future__ import annotations

from typing import Any

from newbee_notebook.application.services.video_service import (
    VideoService,
    VideoSummaryNotFoundError,
)
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.domain.entities.video_summary import VideoSummary


def _safe_error_result(message: str, error: str) -> ToolCallResult:
    return ToolCallResult(content=message, error=error)


def _format_summary_item(index: int, summary: VideoSummary) -> str:
    return (
        f"{index}. [{summary.title}] - summary ID: {summary.summary_id} - "
        f"video: {summary.video_id} - status: {summary.status}"
    )


def _format_video_result_lines(results: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        lines.append(
            f"{index}. {item.get('title', '')} ({item.get('video_id') or item.get('bvid', '')})"
        )
    return lines


def build_discover_videos_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        source = str(args.get("source") or "").strip().lower()

        try:
            if source == "search":
                keyword = str(args.get("keyword") or "").strip()
                if not keyword:
                    return _safe_error_result(
                        "discover_videos requires keyword when source=search",
                        "video_discover_missing_keyword",
                    )
                results = await service.search_videos(
                    keyword,
                    page=int(args.get("page") or 1),
                )
            elif source == "hot":
                results = await service.get_hot_videos(page=int(args.get("page") or 1))
            elif source == "rank":
                results = await service.get_rank_videos(day=int(args.get("day") or 3))
            elif source == "related":
                url_or_bvid = str(args.get("url_or_bvid") or "").strip()
                if not url_or_bvid:
                    return _safe_error_result(
                        "discover_videos requires url_or_bvid when source=related",
                        "video_discover_missing_video_id",
                    )
                results = await service.get_related_videos(url_or_bvid)
            else:
                return _safe_error_result(
                    "discover_videos source must be one of: search, hot, rank, related",
                    "video_discover_invalid_source",
                )
        except Exception as exc:
            return _safe_error_result(f"Failed to discover videos: {exc}", "video_discover_failed")

        if not results:
            return ToolCallResult(content="No videos found.", metadata={"source": source, "results": []})

        lines = [f"Found {len(results)} video result(s) from {source}:"]
        lines.extend(_format_video_result_lines(results))
        return ToolCallResult(content="\n".join(lines), metadata={"source": source, "results": results})

    return ToolDefinition(
        name="discover_videos",
        description="Discover Bilibili videos from search, hot, ranking, or related recommendations.",
        parameters={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["search", "hot", "rank", "related"],
                    "description": "Discovery source",
                },
                "keyword": {"type": "string", "description": "Search keyword when source=search"},
                "url_or_bvid": {
                    "type": "string",
                    "description": "Video URL or BV identifier when source=related",
                },
                "page": {"type": "integer", "description": "Result page for search or hot"},
                "day": {"type": "integer", "description": "Ranking day window when source=rank"},
            },
            "required": ["source"],
        },
        execute=execute,
    )



def build_get_video_content_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        url_or_bvid = str(args.get("url_or_bvid") or "").strip()
        content_type = str(args.get("type") or "subtitle").strip().lower()
        try:
            if content_type == "subtitle":
                text, items = await service.get_video_subtitle(url_or_bvid)
                if not text:
                    return ToolCallResult(content="No subtitles available for this video.", metadata={"items": items})
                return ToolCallResult(content=text, metadata={"items": items})
            if content_type == "ai_conclusion":
                text = await service.get_video_ai_conclusion(url_or_bvid)
                if not text:
                    return ToolCallResult(content="No AI conclusion available for this video.")
                return ToolCallResult(content=text, metadata={"type": "ai_conclusion"})
            return _safe_error_result(
                "get_video_content type must be one of: subtitle, ai_conclusion",
                "video_content_invalid_type",
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to fetch video content: {exc}", "video_content_failed")

    return ToolDefinition(
        name="get_video_content",
        description="Get either subtitles or Bilibili AI conclusion for a video.",
        parameters={
            "type": "object",
            "properties": {
                "url_or_bvid": {"type": "string", "description": "Video URL or BV identifier"},
                "type": {
                    "type": "string",
                    "enum": ["subtitle", "ai_conclusion"],
                    "description": "Content type to fetch",
                },
            },
            "required": ["url_or_bvid"],
        },
        execute=execute,
    )


def build_get_video_info_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        url_or_id = str(args.get("url_or_id") or args.get("url_or_bvid") or "")
        try:
            info = await service.fetch_video_info(url_or_id)
        except Exception as exc:
            return _safe_error_result(f"Failed to fetch video info: {exc}", "video_info_failed")
        return ToolCallResult(
            content=(
                f"Title: {info.get('title', '')}\n"
                f"Video ID: {info.get('video_id', '')}\n"
                f"Uploader: {info.get('uploader_name', '')}\n"
                f"Duration: {info.get('duration_seconds', 0)}"
            ),
            metadata=info,
        )

    return ToolDefinition(
        name="get_video_info",
        description="Get video metadata by URL or platform-specific identifier.",
        parameters={
            "type": "object",
            "properties": {
                "url_or_id": {
                    "type": "string",
                    "description": "Video URL or platform-specific identifier",
                },
            },
            "required": ["url_or_id"],
        },
        execute=execute,
    )



def build_summarize_video_tool(service: VideoService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        url_or_id = str(args.get("url_or_id") or args.get("url_or_bvid") or "")
        try:
            summary = await service.summarize(
                url_or_id,
                notebook_id=notebook_id,
            )
        except Exception as exc:
            return _safe_error_result(f"Failed to summarize video: {exc}", "video_summarize_failed")
        return ToolCallResult(
            content=f"Video summary completed: {summary.title}\n\n{summary.summary_content}",
            metadata={"summary_id": summary.summary_id},
        )

    return ToolDefinition(
        name="summarize_video",
        description="Generate or reuse an AI summary for a Bilibili or YouTube video.",
        parameters={
            "type": "object",
            "properties": {
                "url_or_id": {
                    "type": "string",
                    "description": "Video URL or platform-specific identifier",
                },
            },
            "required": ["url_or_id"],
        },
        execute=execute,
    )


def build_list_summaries_tool(service: VideoService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            summaries = await service.list_by_notebook(notebook_id, status=args.get("status"))
        except Exception as exc:
            return _safe_error_result(f"Failed to list summaries: {exc}", "video_list_failed")

        if not summaries:
            return ToolCallResult(content="No video summaries found in the current notebook.")

        lines = [f"Found {len(summaries)} video summary item(s):"]
        lines.extend(_format_summary_item(index, summary) for index, summary in enumerate(summaries, start=1))
        return ToolCallResult(content="\n".join(lines))

    return ToolDefinition(
        name="list_summaries",
        description="List video summaries in the current notebook.",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Optional status filter"},
            },
            "required": [],
        },
        execute=execute,
    )


def build_read_summary_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            summary = await service.get(str(args.get("summary_id") or ""))
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        return ToolCallResult(content=summary.summary_content, metadata={"summary_id": summary.summary_id})

    return ToolDefinition(
        name="read_summary",
        description="Read one saved video summary by summary ID.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {"type": "string", "description": "Summary ID"},
            },
            "required": ["summary_id"],
        },
        execute=execute,
    )


def build_update_summary_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        summary_id = str(args.get("summary_id") or "").strip()
        content = str(args.get("content") or "").strip()
        if not content:
            return _safe_error_result(
                "update_summary requires non-empty content",
                "video_update_empty_content",
            )
        try:
            summary = await service.update_summary_content(summary_id, content)
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        except ValueError as exc:
            return _safe_error_result(str(exc), "video_update_invalid_status")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to update summary: {exc}",
                "video_update_failed",
            )
        return ToolCallResult(
            content=f"Video summary updated: {summary.title}",
            metadata={"summary_id": summary.summary_id},
        )

    return ToolDefinition(
        name="update_summary",
        description="Update the markdown content of a saved video summary.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {
                    "type": "string",
                    "description": "Summary ID of the video summary to update",
                },
                "content": {
                    "type": "string",
                    "description": "New markdown content for the summary",
                },
            },
            "required": ["summary_id", "content"],
        },
        execute=execute,
    )


def build_delete_summary_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        summary_id = str(args.get("summary_id") or "")
        try:
            await service.delete(summary_id)
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        except Exception as exc:
            return _safe_error_result(f"Failed to delete summary: {exc}", "video_delete_failed")
        return ToolCallResult(content=f"Video summary deleted: {summary_id}")

    return ToolDefinition(
        name="delete_summary",
        description="Delete one saved video summary by summary ID.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {"type": "string", "description": "Summary ID"},
            },
            "required": ["summary_id"],
        },
        execute=execute,
    )



def build_associate_notebook_tool(service: VideoService, notebook_id: str) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            summary = await service.associate_notebook(str(args.get("summary_id") or ""), notebook_id)
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to associate notebook: {exc}",
                "video_associate_notebook_failed",
            )
        return ToolCallResult(
            content=f"Video summary associated with notebook: {summary.title}",
            metadata={"summary_id": summary.summary_id},
        )

    return ToolDefinition(
        name="associate_notebook",
        description="Associate a saved summary with the current notebook.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {"type": "string", "description": "Summary ID"},
            },
            "required": ["summary_id"],
        },
        execute=execute,
    )


def build_disassociate_notebook_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            summary = await service.disassociate_notebook(str(args.get("summary_id") or ""))
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to disassociate notebook: {exc}",
                "video_disassociate_notebook_failed",
            )
        return ToolCallResult(
            content=f"Video summary removed from notebook: {summary.title}",
            metadata={"summary_id": summary.summary_id},
        )

    return ToolDefinition(
        name="disassociate_notebook",
        description="Remove notebook association from a saved summary.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {"type": "string", "description": "Summary ID"},
            },
            "required": ["summary_id"],
        },
        execute=execute,
    )
