"""Application service for multi-platform video summaries."""

from __future__ import annotations

import inspect
import logging
from io import BytesIO
from typing import Any, Awaitable, Callable, Literal, Optional

from newbee_notebook.application.services.video_concurrency import (
    VideoConcurrencyController,
)
from newbee_notebook.domain.entities.video_summary import VideoSummary
from newbee_notebook.domain.repositories.reference_repository import (
    NotebookDocumentRefRepository,
)
from newbee_notebook.domain.repositories.video_summary_repository import (
    VideoSummaryRepository,
)
from newbee_notebook.infrastructure.bilibili.exceptions import AuthenticationError
from newbee_notebook.infrastructure.storage import get_runtime_storage_backend
from newbee_notebook.infrastructure.storage.base import StorageBackend
from newbee_notebook.infrastructure.storage.object_keys import build_video_transcript_key
from newbee_notebook.infrastructure.youtube.exceptions import (
    InvalidYouTubeInputError,
    InvalidYouTubeVideoIdError,
    YouTubeNetworkError,
    YouTubeVideoUnavailableError,
)

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
logger = logging.getLogger(__name__)


class VideoSummarizingInProgressError(RuntimeError):
    """Raised when a matching summary is already being generated."""


class VideoSummaryNotFoundError(RuntimeError):
    """Raised when a video summary cannot be found."""


class VideoTranscriptUnavailableError(RuntimeError):
    """Raised when neither subtitle nor ASR can provide a transcript."""


class VideoConcurrentProcessingLimitError(RuntimeError):
    """Raised when too many video summaries are already processing."""


class VideoService:
    """Shared video summarize pipeline for Studio and runtime slash commands."""

    def __init__(
        self,
        *,
        video_repo: VideoSummaryRepository,
        bili_client: Any,
        llm_client: Any,
        youtube_client: Any | None = None,
        storage: Optional[StorageBackend] = None,
        ref_repo: Optional[NotebookDocumentRefRepository] = None,
        asr_pipeline: Any | None = None,
        concurrency_controller: VideoConcurrencyController | None = None,
    ) -> None:
        self._video_repo = video_repo
        self._bili_client = bili_client
        self._youtube_client = youtube_client
        self._llm_client = llm_client
        self._storage = storage or get_runtime_storage_backend()
        self._ref_repo = ref_repo
        self._asr_pipeline = asr_pipeline
        self._concurrency_controller = concurrency_controller or VideoConcurrencyController()

    async def summarize(
        self,
        url_or_id: str,
        *,
        notebook_id: str | None = None,
        lang: Literal["zh", "en"] = "zh",
        progress_callback: ProgressCallback | None = None,
    ) -> VideoSummary:
        normalized_lang: Literal["zh", "en"] = "en" if lang == "en" else "zh"
        platform = self._detect_platform(url_or_id)
        if platform == "youtube":
            return await self._summarize_youtube(
                url_or_id,
                notebook_id=notebook_id,
                lang=normalized_lang,
                progress_callback=progress_callback,
            )
        return await self._summarize_bilibili(
            url_or_id,
            notebook_id=notebook_id,
            lang=normalized_lang,
            progress_callback=progress_callback,
        )

    async def _summarize_bilibili(
        self,
        url_or_id: str,
        *,
        notebook_id: str | None,
        lang: Literal["zh", "en"],
        progress_callback: ProgressCallback | None,
    ) -> VideoSummary:
        bvid = await self._extract_bvid(url_or_id)
        summary, reused = await self._prepare_processing_summary(
            platform="bilibili",
            video_id=bvid,
            source_url=url_or_id,
            notebook_id=notebook_id,
        )
        if reused:
            await self._emit(
                progress_callback,
                "done",
                {
                    "summary_id": summary.summary_id,
                    "status": "completed",
                    "reused": True,
                },
            )
            return summary

        await self._emit(
            progress_callback,
            "start",
            {
                "video_id": bvid,
                "summary_id": summary.summary_id,
                "status": "processing",
            },
        )

        try:
            info = await self._bili_client.get_video_info(bvid)
            self._apply_info(summary, info, fallback_source_url=url_or_id)
            summary = await self._video_repo.update(summary)
            await self._emit_summary_info(progress_callback, summary, video_id=bvid)

            transcript_text, _tracks = await self._bili_client.get_video_subtitle(bvid)
            transcript_source = "subtitle"
            if transcript_text.strip():
                await self._emit(progress_callback, "subtitle", {"video_id": bvid})
            else:
                transcript_source = "asr"
                await self._emit(progress_callback, "asr", {"video_id": bvid, "step": "transcribe"})
                transcript_text = await self._transcribe_with_asr("bilibili", bvid, info)

            transcript_path = await self._persist_transcript(summary.platform, bvid, transcript_text)
            await self._emit(progress_callback, "summarize", {"video_id": bvid, "lang": lang})
            summary.summary_content = await self._generate_summary_content(
                info=info,
                transcript_text=transcript_text,
                lang=lang,
            )
            summary.transcript_source = transcript_source
            summary.transcript_path = transcript_path
            summary.status = "completed"
            summary.error_message = None
            summary.touch()
            summary = await self._video_repo.update(summary)
            await self._video_repo.commit()
        except Exception as exc:
            await self._handle_failure(summary, bvid, exc, progress_callback)
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

    async def _summarize_youtube(
        self,
        url_or_id: str,
        *,
        notebook_id: str | None,
        lang: Literal["zh", "en"],
        progress_callback: ProgressCallback | None,
    ) -> VideoSummary:
        if self._youtube_client is None:
            raise RuntimeError("YouTube client is not configured")

        video_id = self._youtube_client.extract_video_id(url_or_id)
        summary, reused = await self._prepare_processing_summary(
            platform="youtube",
            video_id=video_id,
            source_url=url_or_id,
            notebook_id=notebook_id,
        )
        if reused:
            await self._emit(
                progress_callback,
                "done",
                {
                    "summary_id": summary.summary_id,
                    "status": "completed",
                    "reused": True,
                },
            )
            return summary

        await self._emit(
            progress_callback,
            "start",
            {
                "video_id": video_id,
                "summary_id": summary.summary_id,
                "status": "processing",
            },
        )

        try:
            try:
                info = await self._youtube_client.get_video_info(video_id)
            except YouTubeVideoUnavailableError:
                raise
            except Exception as info_exc:
                logger.warning("get_video_info failed for %s, using minimal info: %s", video_id, info_exc)
                info = {
                    "video_id": video_id,
                    "source_url": url_or_id,
                    "title": video_id,
                    "description": "",
                    "cover_url": None,
                    "duration_seconds": 0,
                    "uploader_name": "",
                    "uploader_id": "",
                    "stats": {},
                }
            metadata_ready = self._is_metadata_ready(
                video_id,
                title=str(info.get("title") or ""),
                duration_seconds=int(info.get("duration_seconds") or 0),
                uploader_name=str(info.get("uploader_name") or ""),
            )
            self._apply_info(summary, info, fallback_source_url=url_or_id)
            summary = await self._video_repo.update(summary)
            if metadata_ready:
                await self._emit(
                    progress_callback,
                    "info",
                    {
                        "video_id": video_id,
                        "title": summary.title,
                        "duration_seconds": summary.duration_seconds,
                        "uploader_name": summary.uploader_name,
                        "cover_url": summary.cover_url,
                    },
                )

            transcript_text, transcript_source = await self._youtube_client.get_transcript(
                video_id,
                lang_hint=lang,
            )
            if str(transcript_text or "").strip():
                await self._emit(
                    progress_callback,
                    "subtitle",
                    {
                        "video_id": video_id,
                        "available": True,
                        "source": transcript_source,
                        "char_count": len(str(transcript_text)),
                    },
                )
            else:
                await self._emit(
                    progress_callback,
                    "asr",
                    {
                        "video_id": video_id,
                        "step": "transcribe",
                        "message": "Falling back to ASR",
                    },
                )
                transcript_text = await self._transcribe_with_asr("youtube", video_id, info)
                transcript_source = "asr"
                await self._emit(
                    progress_callback,
                    "subtitle",
                    {
                        "video_id": video_id,
                        "available": True,
                        "source": transcript_source,
                        "char_count": len(str(transcript_text)),
                    },
                )

            transcript_path = await self._persist_transcript(summary.platform, video_id, transcript_text)
            await self._emit(progress_callback, "summarize", {"video_id": video_id, "lang": lang})
            summary.summary_content = await self._generate_summary_content(
                info=info,
                transcript_text=transcript_text,
                lang=lang,
            )
            summary.transcript_source = transcript_source
            summary.transcript_path = transcript_path
            summary.status = "completed"
            summary.error_message = None
            summary.touch()
            summary = await self._video_repo.update(summary)
            await self._video_repo.commit()
        except Exception as exc:
            await self._handle_failure(summary, video_id, exc, progress_callback)
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
        summaries = await self._video_repo.list_all(status=status)
        return [summary for summary in summaries if self._should_expose_in_list(summary)]

    async def list_by_notebook(
        self,
        notebook_id: str,
        *,
        status: str | None = None,
    ) -> list[VideoSummary]:
        summaries = await self._video_repo.list_by_notebook(notebook_id, status=status)
        return [summary for summary in summaries if self._should_expose_in_list(summary)]

    async def delete(self, summary_id: str) -> bool:
        summary = await self.get(summary_id)
        deleted = await self._video_repo.delete(summary_id)
        if deleted and summary.transcript_path:
            try:
                await self._storage.delete_file(summary.transcript_path)
            except FileNotFoundError:
                pass
        return deleted

    async def update_summary_content(self, summary_id: str, content: str) -> VideoSummary:
        """Replace the markdown summary content of a completed video summary."""
        summary = await self.get(summary_id)
        if summary.status != "completed":
            raise ValueError(
                f"Cannot update summary in status '{summary.status}', expected 'completed'"
            )
        summary.summary_content = content
        summary.touch()
        summary = await self._video_repo.update(summary)
        await self._video_repo.commit()
        return summary

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

    async def fetch_video_info(self, url_or_id: str) -> dict[str, Any]:
        if self._detect_platform(url_or_id) == "youtube":
            if self._youtube_client is None:
                raise RuntimeError("YouTube client is not configured")
            video_id = self._youtube_client.extract_video_id(url_or_id)
            return await self._youtube_client.get_video_info(video_id)
        return await self._bili_client.get_video_info(url_or_id)

    async def search_videos(self, keyword: str, *, page: int = 1) -> list[dict[str, Any]]:
        return await self._bili_client.search_video(keyword, page=page)

    async def get_video_subtitle(
        self,
        url_or_id: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        if self._detect_platform(url_or_id) == "youtube":
            if self._youtube_client is None:
                raise RuntimeError("YouTube client is not configured")
            video_id = self._youtube_client.extract_video_id(url_or_id)
            text, source = await self._youtube_client.get_transcript(video_id)
            if not text:
                return "", []
            return text, [{"source": source}]
        return await self._bili_client.get_video_subtitle(url_or_id)

    async def get_hot_videos(self, *, page: int = 1) -> list[dict[str, Any]]:
        return await self._bili_client.get_hot_videos(page=page)

    async def get_rank_videos(self, *, day: int = 3) -> list[dict[str, Any]]:
        return await self._bili_client.get_rank_videos(day=day)

    async def get_related_videos(self, url_or_id: str) -> list[dict[str, Any]]:
        bvid = await self._extract_bvid(url_or_id)
        return await self._bili_client.get_related_videos(bvid)

    async def get_video_ai_conclusion(self, url_or_id: str) -> str:
        if self._detect_platform(url_or_id) == "youtube":
            raise ValueError("YouTube does not provide built-in AI conclusions")
        return await self._bili_client.get_video_ai_conclusion(url_or_id)

    async def _prepare_processing_summary(
        self,
        *,
        platform: str,
        video_id: str,
        source_url: str,
        notebook_id: str | None,
    ) -> tuple[VideoSummary, bool]:
        async with self._concurrency_controller.admission():
            existing = await self._video_repo.get_by_platform_and_video_id(platform, video_id)
            if existing is not None:
                if existing.status == "completed":
                    return existing, True
                if existing.status == "processing":
                    raise VideoSummarizingInProgressError(
                        f"Video summary is already processing: {video_id}"
                    )

            processing_count = await self._video_repo.count_by_status("processing")
            if processing_count >= self._concurrency_controller.max_processing_videos:
                raise VideoConcurrentProcessingLimitError(
                    "At most 5 videos can be processed at the same time. Please try again later."
                )

            if existing is not None:
                summary = existing
                summary.notebook_id = notebook_id or summary.notebook_id
                summary.status = "processing"
                summary.error_message = None
                summary.summary_content = ""
                summary.transcript_source = ""
                summary.transcript_path = None
                summary.touch()
                summary = await self._video_repo.update(summary)
            else:
                summary = await self._video_repo.create(
                    VideoSummary(
                        notebook_id=notebook_id,
                        platform=platform,
                        video_id=video_id,
                        source_url=source_url,
                        title=video_id,
                        cover_url=None,
                        duration_seconds=0,
                        uploader_name="",
                        uploader_id="",
                        stats=None,
                        status="processing",
                    )
                )
            await self._video_repo.commit()
            return summary, False

    async def _persist_transcript(self, platform: str, video_id: str, transcript_text: str) -> str:
        return await self._storage.save_file(
            object_key=build_video_transcript_key(f"{platform}-{video_id}"),
            data=BytesIO(transcript_text.encode("utf-8")),
            content_type="text/plain; charset=utf-8",
        )

    async def _handle_failure(
        self,
        summary: VideoSummary,
        video_id: str,
        exc: Exception,
        progress_callback: ProgressCallback | None,
    ) -> None:
        safe_error = self.build_stream_error_payload(exc)
        logger.exception("Video summarize failed for %s", video_id)
        summary.status = "failed"
        summary.error_message = safe_error["message"]
        summary.touch()
        await self._video_repo.update(summary)
        await self._video_repo.commit()
        await self._emit(
            progress_callback,
            "error",
            {"video_id": video_id, **safe_error},
        )

    def _detect_platform(self, value: str) -> Literal["bilibili", "youtube"]:
        if self._youtube_client is not None and self._youtube_client.is_youtube_input(value):
            return "youtube"
        return "bilibili"

    @classmethod
    def is_summary_metadata_ready(cls, summary: VideoSummary) -> bool:
        return cls._is_metadata_ready(
            summary.video_id,
            title=summary.title,
            duration_seconds=summary.duration_seconds,
            uploader_name=summary.uploader_name,
        )

    @staticmethod
    def _apply_info(
        summary: VideoSummary,
        info: dict[str, Any],
        *,
        fallback_source_url: str,
    ) -> None:
        summary.source_url = str(info.get("source_url") or fallback_source_url)
        summary.title = str(info.get("title") or summary.title)
        summary.cover_url = info.get("cover_url")
        summary.duration_seconds = int(info.get("duration_seconds") or 0)
        summary.uploader_name = str(info.get("uploader_name") or "")
        summary.uploader_id = str(info.get("uploader_id") or "")
        summary.stats = info.get("stats")
        summary.touch()

    @staticmethod
    def _is_metadata_ready(
        video_id: str,
        *,
        title: str,
        duration_seconds: int,
        uploader_name: str,
    ) -> bool:
        normalized_title = str(title or "").strip()
        normalized_uploader = str(uploader_name or "").strip()
        return bool(
            (normalized_title and normalized_title != video_id)
            or duration_seconds > 0
            or normalized_uploader
        )

    @staticmethod
    def _should_expose_in_list(summary: VideoSummary) -> bool:
        if summary.status == "processing":
            return False
        return True

    async def _emit_summary_info(
        self,
        progress_callback: ProgressCallback | None,
        summary: VideoSummary,
        *,
        video_id: str,
    ) -> None:
        await self._emit(
            progress_callback,
            "info",
            {
                "video_id": video_id,
                "title": summary.title,
                "duration_seconds": summary.duration_seconds,
                "uploader_name": summary.uploader_name,
                "cover_url": summary.cover_url,
            },
        )

    async def _generate_summary_content(
        self,
        *,
        info: dict[str, Any],
        transcript_text: str,
        lang: Literal["zh", "en"],
    ) -> str:
        async with self._concurrency_controller.llm_slot():
            llm_response = await self._llm_client.chat(
                messages=self._build_summary_messages(
                    info=info,
                    transcript_text=transcript_text,
                    lang=lang,
                ),
            )
        return self._extract_summary_content(llm_response)

    async def _transcribe_with_asr(
        self,
        platform: str,
        video_id: str,
        info: dict[str, Any],
    ) -> str:
        if self._asr_pipeline is None:
            raise VideoTranscriptUnavailableError(
                f"Transcript is unavailable because subtitles are missing and ASR is disabled: {video_id}"
            )
        async with self._concurrency_controller.asr_slot():
            transcript_text = await self._asr_pipeline.transcribe(
                {
                    "platform": platform,
                    "video_id": video_id,
                    "source_url": info.get("source_url"),
                    "title": info.get("title", ""),
                }
            )
        if not str(transcript_text or "").strip():
            raise VideoTranscriptUnavailableError(f"ASR returned an empty transcript: {video_id}")
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
        lang: Literal["zh", "en"] = "zh",
    ) -> list[dict[str, str]]:
        if lang == "en":
            system_message = (
                "You are a video summarization assistant. Based on the provided video metadata "
                "and transcript, generate a structured Markdown summary.\n\n"
                "Output requirements:\n"
                "- Write in English\n"
                "- Use level-2 headings (##) as section titles\n"
                "- Include sections: overview, key topics (grouped by theme), takeaways\n"
                "- Bold important terms and key concepts\n"
                "- Use unordered lists for bullet points\n"
                "- Keep it concise and avoid redundant repetition"
            )
        else:
            system_message = (
                "You are a video summarization assistant. Based on the provided video metadata "
                "and transcript, generate a structured Markdown summary.\n\n"
                "Output requirements:\n"
                "- Write in Chinese\n"
                "- Use level-2 headings (##) as section titles\n"
                "- Include sections: overview, key topics (grouped by theme), takeaways\n"
                "- Bold important terms and key concepts\n"
                "- Use unordered lists for bullet points\n"
                "- Keep it concise and avoid redundant repetition"
            )
        return [
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": (
                    f"Title: {info.get('title', '')}\n"
                    f"Uploader: {info.get('uploader_name', '')}\n"
                    f"Duration: {info.get('duration_seconds', 0)}s\n\n"
                    f"Transcript:\n{transcript_text}"
                ),
            },
        ]

    @staticmethod
    def _extract_summary_content(response: Any) -> str:
        return str(response.choices[0].message.content).strip()

    @staticmethod
    def build_stream_error_payload(exc: Exception) -> dict[str, str]:
        if isinstance(exc, AuthenticationError):
            return {
                "error_code": "E_BILIBILI_AUTH",
                "message": "Bilibili session expired or not logged in. Please login and try again.",
            }
        if isinstance(exc, (InvalidYouTubeInputError, InvalidYouTubeVideoIdError)):
            return {
                "error_code": "E_YOUTUBE_INVALID_INPUT",
                "message": "Invalid YouTube URL or video id.",
            }
        if isinstance(exc, YouTubeVideoUnavailableError):
            return {
                "error_code": "E_YOUTUBE_VIDEO_UNAVAILABLE",
                "message": "YouTube video is unavailable.",
            }
        if isinstance(exc, YouTubeNetworkError):
            return {
                "error_code": "E_YOUTUBE_NETWORK",
                "message": "Failed to load YouTube video resources. Please retry.",
            }
        if isinstance(exc, VideoSummarizingInProgressError):
            return {
                "error_code": "E_VIDEO_SUMMARIZE_IN_PROGRESS",
                "message": str(exc),
            }
        if isinstance(exc, VideoConcurrentProcessingLimitError):
            return {
                "error_code": "E_VIDEO_MAX_CONCURRENT_LIMIT",
                "message": str(exc),
            }
        if isinstance(exc, VideoTranscriptUnavailableError):
            return {
                "error_code": "E_VIDEO_TRANSCRIPT_UNAVAILABLE",
                "message": str(exc),
            }
        return {
            "error_code": "E_VIDEO_SUMMARIZE_FAILED",
            "message": "Video summarization failed. Please retry.",
        }

    @staticmethod
    async def _emit(
        progress_callback: ProgressCallback | None,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        if progress_callback is not None:
            await progress_callback(event, payload)
