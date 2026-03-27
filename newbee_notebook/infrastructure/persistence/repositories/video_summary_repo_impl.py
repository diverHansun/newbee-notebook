"""SQLAlchemy implementation of the video summary repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.domain.repositories.video_summary_repository import (
    VideoSummaryRepository,
)
from newbee_notebook.infrastructure.persistence.models import VideoSummaryModel


class VideoSummaryRepositoryImpl(VideoSummaryRepository):
    """SQLAlchemy-backed video summary repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: VideoSummaryModel) -> VideoSummary:
        return VideoSummary(
            summary_id=str(model.id),
            notebook_id=str(model.notebook_id) if model.notebook_id else None,
            platform=model.platform,
            video_id=model.video_id,
            source_url=model.source_url,
            title=model.title,
            cover_url=model.cover_url,
            duration_seconds=model.duration_seconds,
            uploader_name=model.uploader_name,
            uploader_id=model.uploader_id,
            stats=model.stats,
            transcript_source=model.transcript_source,
            transcript_path=model.transcript_path,
            summary_content=model.summary_content,
            status=model.status,
            error_message=model.error_message,
            document_ids=[str(value) for value in (model.document_ids or [])],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get(self, summary_id: str) -> Optional[VideoSummary]:
        result = await self._session.execute(
            select(VideoSummaryModel).where(VideoSummaryModel.id == uuid.UUID(summary_id))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_platform_and_video_id(
        self,
        platform: str,
        video_id: str,
    ) -> Optional[VideoSummary]:
        result = await self._session.execute(
            select(VideoSummaryModel).where(
                VideoSummaryModel.platform == platform,
                VideoSummaryModel.video_id == video_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, status: str | None = None) -> list[VideoSummary]:
        query = select(VideoSummaryModel).order_by(
            VideoSummaryModel.updated_at.desc(),
            VideoSummaryModel.created_at.desc(),
        )
        if status is not None:
            query = query.where(VideoSummaryModel.status == status)
        result = await self._session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_by_notebook(
        self,
        notebook_id: str,
        status: str | None = None,
    ) -> list[VideoSummary]:
        query = (
            select(VideoSummaryModel)
            .where(VideoSummaryModel.notebook_id == uuid.UUID(notebook_id))
            .order_by(VideoSummaryModel.updated_at.desc(), VideoSummaryModel.created_at.desc())
        )
        if status is not None:
            query = query.where(VideoSummaryModel.status == status)
        result = await self._session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def create(self, summary: VideoSummary) -> VideoSummary:
        model = VideoSummaryModel(
            id=uuid.UUID(summary.summary_id),
            notebook_id=uuid.UUID(summary.notebook_id) if summary.notebook_id else None,
            platform=summary.platform,
            video_id=summary.video_id,
            source_url=summary.source_url,
            title=summary.title,
            cover_url=summary.cover_url,
            duration_seconds=summary.duration_seconds,
            uploader_name=summary.uploader_name,
            uploader_id=summary.uploader_id,
            stats=summary.stats,
            transcript_source=summary.transcript_source,
            transcript_path=summary.transcript_path,
            summary_content=summary.summary_content,
            status=summary.status,
            error_message=summary.error_message,
            document_ids=[uuid.UUID(value) for value in summary.document_ids],
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, summary: VideoSummary) -> VideoSummary:
        result = await self._session.execute(
            select(VideoSummaryModel).where(VideoSummaryModel.id == uuid.UUID(summary.summary_id))
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Video summary not found during update: {summary.summary_id}")

        model.notebook_id = uuid.UUID(summary.notebook_id) if summary.notebook_id else None
        model.platform = summary.platform
        model.video_id = summary.video_id
        model.source_url = summary.source_url
        model.title = summary.title
        model.cover_url = summary.cover_url
        model.duration_seconds = summary.duration_seconds
        model.uploader_name = summary.uploader_name
        model.uploader_id = summary.uploader_id
        model.stats = summary.stats
        model.transcript_source = summary.transcript_source
        model.transcript_path = summary.transcript_path
        model.summary_content = summary.summary_content
        model.status = summary.status
        model.error_message = summary.error_message
        model.document_ids = [uuid.UUID(value) for value in summary.document_ids]
        model.updated_at = summary.updated_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, summary_id: str) -> bool:
        result = await self._session.execute(
            delete(VideoSummaryModel).where(VideoSummaryModel.id == uuid.UUID(summary_id))
        )
        await self._session.flush()
        return result.rowcount > 0
