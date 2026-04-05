from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.infrastructure.persistence.models import VideoSummaryModel
from newbee_notebook.infrastructure.persistence.repositories.video_summary_repo_impl import (
    VideoSummaryRepositoryImpl,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_video_summary_repo_maps_model_to_entity():
    summary_id = uuid.uuid4()
    notebook_id = uuid.uuid4()
    document_id = uuid.uuid4()
    model = VideoSummaryModel(
        id=summary_id,
        notebook_id=notebook_id,
        platform="bilibili",
        video_id="BV1xx411c7mD",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        title="Demo",
        cover_url="https://example.com/cover.jpg",
        duration_seconds=120,
        uploader_name="Uploader",
        uploader_id="12345",
        stats={"view": 42},
        transcript_source="subtitle",
        transcript_path="videos/transcripts/BV1xx411c7mD.txt",
        summary_content="## Summary",
        status="completed",
        document_ids=[document_id],
    )

    entity = VideoSummaryRepositoryImpl(AsyncMock())._to_entity(model)

    assert entity.summary_id == str(summary_id)
    assert entity.notebook_id == str(notebook_id)
    assert entity.video_id == "BV1xx411c7mD"
    assert entity.summary_content == "## Summary"
    assert entity.document_ids == [str(document_id)]


@pytest.mark.anyio
async def test_video_summary_repo_create_returns_entity():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    repo = VideoSummaryRepositoryImpl(session)

    created = await repo.create(
        VideoSummary(
            notebook_id="00000000-0000-0000-0000-000000000001",
            platform="bilibili",
            video_id="BV1xx411c7mD",
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            title="Demo",
            summary_content="## Summary",
            status="completed",
        )
    )

    assert created.video_id == "BV1xx411c7mD"
    assert created.title == "Demo"
    assert created.summary_content == "## Summary"
    assert created.status == "completed"
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
