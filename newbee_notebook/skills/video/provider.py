"""Provider for the /video runtime skill."""

from __future__ import annotations

from newbee_notebook.application.services.video_service import VideoService
from newbee_notebook.core.skills import SkillContext, SkillManifest
from newbee_notebook.core.skills.contracts import ConfirmationMeta
from newbee_notebook.skills.video.tools import (
    build_associate_notebook_tool,
    build_delete_summary_tool,
    build_disassociate_notebook_tool,
    build_get_hot_videos_tool,
    build_get_rank_videos_tool,
    build_get_related_videos_tool,
    build_get_video_info_tool,
    build_get_video_subtitle_tool,
    build_list_summaries_tool,
    build_read_summary_tool,
    build_search_video_tool,
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
                "Use the available tools for video search, metadata lookup, subtitle lookup, "
                "and summary management requests.\n"
                "When the user provides a URL or BV identifier, prefer get_video_info first and "
                "then use summarize_video only when a summary is requested.\n"
                "Use summarize_video for full AI summarization. It may take longer than metadata "
                "or search tools.\n"
                "Use get_hot_videos or get_rank_videos for discovery requests.\n"
                "---"
            ),
            tools=[
                build_search_video_tool(service=self._video_service),
                build_get_video_info_tool(service=self._video_service),
                build_get_video_subtitle_tool(service=self._video_service),
                build_summarize_video_tool(service=self._video_service, notebook_id=context.notebook_id),
                build_list_summaries_tool(service=self._video_service, notebook_id=context.notebook_id),
                build_read_summary_tool(service=self._video_service),
                build_delete_summary_tool(service=self._video_service),
                build_get_hot_videos_tool(service=self._video_service),
                build_get_rank_videos_tool(service=self._video_service),
                build_get_related_videos_tool(service=self._video_service),
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
