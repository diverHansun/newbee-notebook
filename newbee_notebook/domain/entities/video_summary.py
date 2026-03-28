"""Video summary domain entity."""

from dataclasses import dataclass, field

from newbee_notebook.domain.entities.base import Entity, generate_uuid


@dataclass
class VideoSummary(Entity):
    """Persisted summary for one platform video."""

    summary_id: str = field(default_factory=generate_uuid)
    notebook_id: str | None = None
    platform: str = "bilibili"
    video_id: str = ""
    source_url: str = ""
    title: str = ""
    cover_url: str | None = None
    duration_seconds: int = 0
    uploader_name: str = ""
    uploader_id: str = ""
    stats: dict | None = None
    transcript_source: str = ""
    transcript_path: str | None = None
    summary_content: str = ""
    status: str = "processing"
    error_message: str | None = None
    document_ids: list[str] = field(default_factory=list)
