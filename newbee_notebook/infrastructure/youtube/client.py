"""YouTube infrastructure adapter for video metadata and transcripts."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from newbee_notebook.infrastructure.youtube.exceptions import (
    InvalidYouTubeInputError,
    InvalidYouTubeVideoIdError,
    YouTubeNetworkError,
    YouTubeVideoUnavailableError,
)
from newbee_notebook.infrastructure.youtube.parsers import (
    ensure_query_param,
    extract_caption_tracks,
    extract_initial_player_response,
    parse_json3_transcript,
    parse_srt_transcript,
    parse_vtt_transcript,
    parse_xml_transcript,
    pick_best_track,
)

_YOUTUBE_ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class YouTubeClient:
    """Fetch YouTube video metadata, subtitles, and audio."""

    def is_youtube_input(self, value: str) -> bool:
        raw = str(value or "").strip()
        if not raw:
            return False
        if _YOUTUBE_ID_RE.fullmatch(raw):
            return True
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (parsed.netloc or "").lower()
        return host in _YOUTUBE_HOSTS or host.endswith(".youtube.com")

    def extract_video_id(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise InvalidYouTubeInputError("YouTube input is empty")
        if _YOUTUBE_ID_RE.fullmatch(raw):
            return raw

        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        path = parsed.path.strip("/")

        candidate = ""
        if host == "youtu.be":
            candidate = path.split("/", 1)[0]
        elif host in _YOUTUBE_HOSTS or host.endswith(".youtube.com"):
            if path == "watch":
                candidate = parse_qs(parsed.query).get("v", [""])[0]
            elif path.startswith(("embed/", "shorts/", "live/")):
                candidate = path.split("/", 1)[1].split("/", 1)[0]

        if not _YOUTUBE_ID_RE.fullmatch(candidate or ""):
            raise InvalidYouTubeVideoIdError(f"Invalid YouTube input: {value}")
        return candidate

    async def get_video_info(self, video_id: str) -> dict[str, Any]:
        info = await self._extract_info(video_id, download=False)
        return {
            "video_id": video_id,
            "source_url": str(info.get("webpage_url") or self._build_watch_url(video_id)),
            "title": str(info.get("title") or video_id),
            "description": str(info.get("description") or ""),
            "cover_url": info.get("thumbnail"),
            "duration_seconds": int(info.get("duration") or 0),
            "uploader_name": str(info.get("channel") or info.get("uploader") or ""),
            "uploader_id": str(info.get("channel_id") or info.get("uploader_id") or ""),
            "stats": {
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "comment_count": info.get("comment_count"),
            },
        }

    async def get_transcript(
        self,
        video_id: str,
        *,
        lang_hint: str | None = None,
    ) -> tuple[str | None, str]:
        transcript = None
        try:
            transcript = await self._get_transcript_from_ytdlp(video_id, lang_hint=lang_hint)
        except YouTubeNetworkError:
            transcript = None
        if transcript:
            return transcript, "subtitle"

        try:
            transcript = await self._get_transcript_from_watch_page(video_id, lang_hint=lang_hint)
        except YouTubeNetworkError:
            transcript = None
        if transcript:
            return transcript, "caption_tracks"

        return None, "asr"

    async def download_audio(self, video_id: str) -> str:
        return await asyncio.to_thread(self._download_audio_sync, video_id)

    async def _get_transcript_from_ytdlp(self, video_id: str, *, lang_hint: str | None) -> str | None:
        info = await self._extract_info(video_id, download=False)
        candidates = self._build_subtitle_candidates(
            subtitles=info.get("subtitles"),
            automatic_captions=info.get("automatic_captions"),
            preferred_languages=self._preferred_languages(lang_hint),
        )
        for candidate in candidates:
            raw = await self._fetch_text(candidate["url"])
            transcript = self._parse_transcript_text(
                raw,
                extension=str(candidate.get("ext") or ""),
                url=candidate["url"],
            )
            if transcript:
                return transcript
        return None

    async def _get_transcript_from_watch_page(self, video_id: str, *, lang_hint: str | None) -> str | None:
        html = await self._fetch_text(self._build_watch_url(video_id))
        player_response = extract_initial_player_response(html)
        track = pick_best_track(
            extract_caption_tracks(player_response),
            preferred_languages=self._preferred_languages(lang_hint),
        )
        if track is None:
            return None

        base_url = str(track.get("baseUrl") or "")
        if not base_url:
            return None

        json3_payload = await self._fetch_text(ensure_query_param(base_url, "fmt", "json3"))
        transcript = parse_json3_transcript(json3_payload)
        if transcript:
            return transcript

        raw_payload = await self._fetch_text(base_url)
        return self._parse_transcript_text(raw_payload, extension="", url=base_url)

    async def _extract_info(self, video_id: str, *, download: bool) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._extract_info_sync, video_id, download)
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            if "private video" in message or "unavailable" in message or "sign in to confirm your age" in message:
                raise YouTubeVideoUnavailableError(f"YouTube video is unavailable: {video_id}") from exc
            raise YouTubeNetworkError(f"Failed to load YouTube video: {video_id}") from exc

    def _extract_info_sync(self, video_id: str, download: bool) -> dict[str, Any]:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("yt-dlp is required for YouTube support") from exc

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": not download,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            return downloader.extract_info(self._build_watch_url(video_id), download=download)

    def _download_audio_sync(self, video_id: str) -> str:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("yt-dlp is required for YouTube support") from exc

        workspace = tempfile.mkdtemp(prefix="video-asr-")
        output_template = os.path.join(workspace, "%(id)s.%(ext)s")
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_template,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(self._build_watch_url(video_id), download=True)
            output_path = Path(downloader.prepare_filename(info))
        if not output_path.exists():
            raise YouTubeNetworkError(f"Downloaded audio file is missing: {output_path}")
        return str(output_path)

    async def _fetch_text(self, url: str) -> str:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("httpx is required for YouTube support") from exc

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as exc:  # noqa: BLE001
            raise YouTubeNetworkError(f"Failed to fetch YouTube resource: {url}") from exc

    def _build_subtitle_candidates(
        self,
        *,
        subtitles: Any,
        automatic_captions: Any,
        preferred_languages: list[str],
    ) -> list[dict[str, str]]:
        language_rank = {language.lower(): index for index, language in enumerate(preferred_languages)}
        candidates: list[dict[str, str]] = []

        def _append(source: Any, manual: bool) -> None:
            if not isinstance(source, dict):
                return
            for language_code, entries in source.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    url = str(entry.get("url") or "").strip()
                    if not url:
                        continue
                    candidates.append(
                        {
                            "url": url,
                            "ext": str(entry.get("ext") or ""),
                            "language": str(language_code or ""),
                            "manual": "1" if manual else "0",
                        }
                    )

        _append(subtitles, True)
        _append(automatic_captions, False)

        def _sort_key(item: dict[str, str]) -> tuple[int, int, str]:
            language = item.get("language", "").lower()
            base = language.split("-", 1)[0]
            rank = language_rank.get(language, language_rank.get(base, len(language_rank) + 100))
            return (0 if item.get("manual") == "1" else 1, rank, language)

        candidates.sort(key=_sort_key)
        return candidates

    def _parse_transcript_text(self, raw: str, *, extension: str, url: str) -> str | None:
        normalized_extension = extension.lower().lstrip(".")
        url_lower = url.lower()
        if normalized_extension in {"json3", "srv3"} or "fmt=json3" in url_lower:
            return parse_json3_transcript(raw)
        if normalized_extension in {"vtt", "webvtt"}:
            return parse_vtt_transcript(raw)
        if normalized_extension == "srt":
            return parse_srt_transcript(raw)

        return (
            parse_json3_transcript(raw)
            or parse_vtt_transcript(raw)
            or parse_srt_transcript(raw)
            or parse_xml_transcript(raw)
        )

    @staticmethod
    def _build_watch_url(video_id: str) -> str:
        return f"https://www.youtube.com/watch?v={video_id}"

    @staticmethod
    def _preferred_languages(lang_hint: str | None) -> list[str]:
        if (lang_hint or "").lower() == "en":
            return ["en", "en-us", "en-gb", "zh-hans", "zh", "zh-hant"]
        return ["zh-hans", "zh", "zh-cn", "zh-hant", "en", "en-us"]
