"""Repository interface for video summaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from newbee_notebook.domain.entities.video_summary import VideoSummary


class VideoSummaryRepository(ABC):
    """Repository interface for video summary persistence."""

    @abstractmethod
    async def get(self, summary_id: str) -> Optional[VideoSummary]:
        """Get one summary by ID."""

    @abstractmethod
    async def get_by_platform_and_video_id(
        self,
        platform: str,
        video_id: str,
    ) -> Optional[VideoSummary]:
        """Get one summary by platform/video key."""

    @abstractmethod
    async def list_all(self, status: str | None = None) -> list[VideoSummary]:
        """List summaries across the workspace."""

    @abstractmethod
    async def list_by_notebook(
        self,
        notebook_id: str,
        status: str | None = None,
    ) -> list[VideoSummary]:
        """List summaries associated with one notebook."""

    @abstractmethod
    async def count_by_status(self, status: str) -> int:
        """Count summaries with one status."""

    @abstractmethod
    async def create(self, summary: VideoSummary) -> VideoSummary:
        """Create a summary."""

    @abstractmethod
    async def update(self, summary: VideoSummary) -> VideoSummary:
        """Update a summary."""

    @abstractmethod
    async def delete(self, summary_id: str) -> bool:
        """Delete a summary by ID."""

    @abstractmethod
    async def commit(self) -> None:
        """Persist pending video-summary changes so other requests can observe them."""
