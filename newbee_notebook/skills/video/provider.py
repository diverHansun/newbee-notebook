"""Provider for the /video runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.video_service import VideoService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.core.skills.contracts import ConfirmationMeta
from newbee_notebook.skills.video.tools import (
    build_associate_notebook_tool,
    build_delete_summary_tool,
    build_discover_videos_tool,
    build_disassociate_notebook_tool,
    build_get_video_content_tool,
    build_get_video_info_tool,
    build_list_summaries_tool,
    build_read_summary_tool,
    build_summarize_video_tool,
)


class VideoSkillProvider:
    def __init__(self, *, video_service: VideoService) -> None:
        self._video_service = video_service

    @property
    def skill_name(self) -> str:
        return "video"

    @property
    def slash_commands(self) -> list[str]:
        return ["/video"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="video",
            slash_command="/video",
            description="Bilibili video search, lookup, and summarization skill",
            system_prompt_addition=(
                "---\n"
                "Active skill: /video\n"
                "Use the available tools for video discovery, metadata lookup, content lookup, "
                "and summary management requests.\n"
                "When the user provides a URL or BV identifier, prefer get_video_info first and "
                "then use summarize_video only when a summary is requested.\n"
                "Use discover_videos with source=search for keyword search, source=hot for "
                "trending videos, source=rank for ranking lists, and source=related for "
                "recommendations based on another video.\n"
                "Use get_video_content with type=subtitle for the transcript and "
                "type=ai_conclusion for Bilibili's built-in AI summary when available.\n"
                "Use summarize_video for full AI summarization. It may take longer than metadata "
                "or discovery tools.\n"
                "---"
            ),
            tools=[
                build_discover_videos_tool(service=self._video_service),
                build_get_video_info_tool(service=self._video_service),
                build_get_video_content_tool(service=self._video_service),
                build_summarize_video_tool(service=self._video_service, notebook_id=context.notebook_id),
                build_list_summaries_tool(service=self._video_service, notebook_id=context.notebook_id),
                build_read_summary_tool(service=self._video_service),
                build_delete_summary_tool(service=self._video_service),
                build_associate_notebook_tool(
                    service=self._video_service,
                    notebook_id=context.notebook_id,
                ),
                build_disassociate_notebook_tool(service=self._video_service),
            ],
            confirmation_required=frozenset({"delete_summary", "disassociate_notebook"}),
            confirmation_meta={
                "delete_summary": ConfirmationMeta(action_type="delete", target_type="video"),
                "disassociate_notebook": ConfirmationMeta(
                    action_type="delete",
                    target_type="video",
                ),
            },
            force_first_tool_call=True,
        )
