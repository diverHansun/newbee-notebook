"""Application service for Bilibili video summaries."""

from __future__ import annotations

import inspect
from io import BytesIO
from typing import Any, Awaitable, Callable, Optional

from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
)
from newbee_notebook.domain.repositories.video_summary_repository import (
    VideoSummaryRepository,
)
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.storage.object_keys import build_video_transcript_key

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class VideoSummarizingInProgressError(RuntimeError):
    """Raised when a matching summary is already being generated."""


class VideoSummaryNotFoundError(RuntimeError):
    """Raised when a video summary cannot be found."""


class VideoTranscriptUnavailableError(RuntimeError):
    """Raised when neither subtitle nor ASR can provide a transcript."""


class VideoService:
    """Shared video summarize pipeline for Studio and runtime slash commands."""

    def __init__(
        self,
        *,
        video_repo: VideoSummaryRepository,
        bili_client: Any,
        llm_client: Any,
        storage: Optional[StorageBackend] = None,
        ref_repo: Optional[NotebookDocumentRefRepository] = None,
        asr_pipeline: Any | None = None,
    ) -> None:
        self._video_repo = video_repo
        self._bili_client = bili_client
        self._llm_client = llm_client
        self._storage = storage or get_runtime_storage_backend()
        self._ref_repo = ref_repo
        self._asr_pipeline = asr_pipeline

    async def summarize(
        self,
        url_or_bvid: str,
        *,
        notebook_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> VideoSummary:
        bvid = await self._extract_bvid(url_or_bvid)
        existing = await self._video_repo.get_by_platform_and_video_id("bilibili", bvid)
        if existing is not None:
            if existing.status == "completed":
                await self._emit(
                    progress_callback,
                    "done",
                    {
                        "summary_id": existing.summary_id,
                        "status": "completed",
                        "reused": True,
                    },
                )
                return existing
            if existing.status == "processing":
                raise VideoSummarizingInProgressError(
                    f"Video summary is already processing: {bvid}"
                )

        await self._emit(progress_callback, "start", {"video_id": bvid})
        info = await self._bili_client.get_video_info(bvid)
        summary = await self._video_repo.create(
            VideoSummary(
                notebook_id=notebook_id,
                platform="bilibili",
                video_id=bvid,
                source_url=info.get("source_url") or url_or_bvid,
                title=info.get("title", ""),
                cover_url=info.get("cover_url"),
                duration_seconds=int(info.get("duration_seconds") or 0),
                uploader_name=info.get("uploader_name", ""),
                uploader_id=str(info.get("uploader_id", "")),
                stats=info.get("stats"),
                status="processing",
            )
        )

        try:
            transcript_text, _tracks = await self._bili_client.get_video_subtitle(bvid)
            transcript_source = "subtitle"
            if transcript_text.strip():
                await self._emit(progress_callback, "subtitle", {"video_id": bvid})
            else:
                transcript_source = "asr"
                await self._emit(progress_callback, "asr", {"video_id": bvid})
                transcript_text = await self._transcribe_with_asr(bvid, info)

            transcript_path = await self._storage.save_file(
                object_key=build_video_transcript_key(bvid),
                data=BytesIO(transcript_text.encode("utf-8")),
                content_type="text/plain; charset=utf-8",
            )
            await self._emit(progress_callback, "summarize", {"video_id": bvid})
            llm_response = await self._llm_client.chat(
                messages=self._build_summary_messages(info=info, transcript_text=transcript_text),
            )
            summary.summary_content = self._extract_summary_content(llm_response)
            summary.transcript_source = transcript_source
            summary.transcript_path = transcript_path
            summary.status = "completed"
            summary.error_message = None
            summary.touch()
            summary = await self._video_repo.update(summary)
        except Exception as exc:
            summary.status = "failed"
            summary.error_message = str(exc)
            summary.touch()
            await self._video_repo.update(summary)
            await self._emit(
                progress_callback,
                "error",
                {"video_id": bvid, "message": str(exc)},
            )
            raise

        await self._emit(
            progress_callback,
            "done",
            {
                "summary_id": summary.summary_id,
                "status": summary.status,
                "reused": False,
            },
        )
        return summary

    async def get(self, summary_id: str) -> VideoSummary:
        summary = await self._video_repo.get(summary_id)
        if summary is None:
            raise VideoSummaryNotFoundError(f"Video summary not found: {summary_id}")
        return summary

    async def list_all(self, *, status: str | None = None) -> list[VideoSummary]:
        return await self._video_repo.list_all(status=status)

    async def list_by_notebook(
        self,
        notebook_id: str,
        *,
        status: str | None = None,
    ) -> list[VideoSummary]:
        return await self._video_repo.list_by_notebook(notebook_id, status=status)

    async def delete(self, summary_id: str) -> bool:
        summary = await self.get(summary_id)
        deleted = await self._video_repo.delete(summary_id)
        if deleted and summary.transcript_path:
            try:
                await self._storage.delete_file(summary.transcript_path)
            except FileNotFoundError:
                pass
        return deleted

    async def associate_notebook(self, summary_id: str, notebook_id: str) -> VideoSummary:
        summary = await self.get(summary_id)
        summary.notebook_id = notebook_id
        summary.touch()
        return await self._video_repo.update(summary)

    async def disassociate_notebook(self, summary_id: str) -> VideoSummary:
        summary = await self.get(summary_id)
        summary.notebook_id = None
        summary.touch()
        return await self._video_repo.update(summary)

    async def add_document_tag(self, summary_id: str, document_id: str) -> VideoSummary:
        summary = await self.get(summary_id)
        if not summary.notebook_id:
            raise ValueError("Video summary is not associated with a notebook")
        if self._ref_repo is None:
            raise ValueError("Notebook document reference repository is not configured")

        ref = await self._ref_repo.get_by_notebook_and_document(summary.notebook_id, document_id)
        if ref is None:
            raise ValueError(
                f"Document {document_id} is not associated with notebook {summary.notebook_id}"
            )
        if document_id not in summary.document_ids:
            summary.document_ids.append(document_id)
            summary.touch()
        return await self._video_repo.update(summary)

    async def remove_document_tag(self, summary_id: str, document_id: str) -> VideoSummary:
        summary = await self.get(summary_id)
        summary.document_ids = [
            current_document_id
            for current_document_id in summary.document_ids
            if current_document_id != document_id
        ]
        summary.touch()
        return await self._video_repo.update(summary)

    async def fetch_video_info(self, url_or_bvid: str) -> dict[str, Any]:
        return await self._bili_client.get_video_info(url_or_bvid)

    async def search_videos(self, keyword: str, *, page: int = 1) -> list[dict[str, Any]]:
        return await self._bili_client.search_video(keyword, page=page)

    async def get_video_subtitle(
        self,
        url_or_bvid: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        return await self._bili_client.get_video_subtitle(url_or_bvid)

    async def get_hot_videos(self, *, page: int = 1) -> list[dict[str, Any]]:
        return await self._bili_client.get_hot_videos(page=page)

    async def get_rank_videos(self, *, day: int = 3) -> list[dict[str, Any]]:
        return await self._bili_client.get_rank_videos(day=day)

    async def get_related_videos(self, url_or_bvid: str) -> list[dict[str, Any]]:
        bvid = await self._extract_bvid(url_or_bvid)
        return await self._bili_client.get_related_videos(bvid)

    async def _transcribe_with_asr(self, bvid: str, info: dict[str, Any]) -> str:
        if self._asr_pipeline is None:
            raise VideoTranscriptUnavailableError(
                f"Transcript is unavailable and ASR is not configured: {bvid}"
            )
        transcript_text = await self._asr_pipeline.transcribe(
            {
                "video_id": bvid,
                "source_url": info.get("source_url"),
                "title": info.get("title", ""),
            }
        )
        if not str(transcript_text or "").strip():
            raise VideoTranscriptUnavailableError(f"ASR returned an empty transcript: {bvid}")
        return transcript_text

    async def _extract_bvid(self, value: str) -> str:
        extracted = self._bili_client.extract_bvid(value)
        if inspect.isawaitable(extracted):
            extracted = await extracted
        return str(extracted)

    @staticmethod
    def _build_summary_messages(
        *,
        info: dict[str, Any],
        transcript_text: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": "You summarize Bilibili videos into concise markdown notes.",
            },
            {
                "role": "user",
                "content": (
                    f"Title: {info.get('title', '')}\n"
                    f"Uploader: {info.get('uploader_name', '')}\n"
                    f"Duration: {info.get('duration_seconds', 0)}\n\n"
                    f"Transcript:\n{transcript_text}"
                ),
            },
        ]

    @staticmethod
    def _extract_summary_content(response: Any) -> str:
        return str(response.choices[0].message.content).strip()

    @staticmethod
    async def _emit(
        progress_callback: ProgressCallback | None,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        if progress_callback is not None:
            await progress_callback(event, payload)
