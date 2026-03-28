"""Thin async client adapters around bilibili-api-python."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Awaitable, Callable

import aiohttp
from bilibili_api import hot, rank, search, video
from bilibili_api.exceptions import (
    CredentialNoBiliJctException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
)
from bilibili_api.video import AudioQuality, VideoDownloadURLDataDetecter

from newbee_notebook.infrastructure.bilibili.exceptions import (
    AuthenticationError,
    BiliError,
    InvalidBvidError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from newbee_notebook.infrastructure.bilibili.payloads import (
    normalize_ai_conclusion,
    normalize_hot_rank_list,
    normalize_search_results,
    normalize_subtitle_items,
    normalize_video_info,
)

_BVID_RE = re.compile(r"\bBV[0-9A-Za-z]{10}\b")
_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}


def extract_bvid(url_or_bvid: str) -> str:
    """Extract a BV identifier from a URL or raw string."""

    match = _BVID_RE.search(url_or_bvid or "")
    if match is None:
        raise InvalidBvidError(f"Unable to extract BV identifier: {url_or_bvid}")
    return match.group(0)


def _map_api_error(action: str, exc: Exception) -> BiliError:
    if isinstance(exc, BiliError):
        return exc
    if isinstance(exc, (CredentialNoSessdataException, CredentialNoBiliJctException)):
        return AuthenticationError(f"{action}: {exc}")
    if isinstance(exc, ResponseCodeException):
        if exc.code in {-404, 62002, 62004}:
            return NotFoundError(f"{action}: {exc}")
        if exc.code in {-412, 412}:
            return RateLimitError(f"{action}: {exc}")
        return BiliError(f"{action}: [{exc.code}] {exc}")
    if isinstance(exc, (NetworkException, aiohttp.ClientError, asyncio.TimeoutError)):
        return NetworkError(f"{action}: {exc}")
    return BiliError(f"{action}: {exc}")


class BilibiliClient:
    """Stable Bilibili client returning normalized payloads."""

    def __init__(
        self,
        *,
        credential: Any | None = None,
        video_factory: Callable[..., Any] = video.Video,
        json_fetcher: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self._credential = credential
        self._video_factory = video_factory
        self._json_fetcher = json_fetcher

    def extract_bvid(self, url_or_bvid: str) -> str:
        return extract_bvid(url_or_bvid)

    async def get_video_info(self, url_or_bvid: str) -> dict[str, Any]:
        bvid = self.extract_bvid(url_or_bvid)
        raw = await self._call_api(
            "get_video_info",
            self._video_factory(bvid=bvid, credential=self._credential).get_info(),
        )
        return normalize_video_info(raw)

    async def get_video_subtitle(
        self,
        url_or_bvid: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        bvid = self.extract_bvid(url_or_bvid)
        video_client = self._video_factory(bvid=bvid, credential=self._credential)
        pages = await self._call_api("get_pages", video_client.get_pages())
        if not pages:
            return "", []

        cid = pages[0].get("cid")
        if not cid:
            return "", []

        player_info = await self._call_api(
            "get_player_info",
            video_client.get_player_info(cid=cid),
        )
        subtitle_entries = (
            player_info.get("subtitle", {}).get("subtitles", [])
            if isinstance(player_info, dict)
            else []
        )
        if not subtitle_entries:
            return "", []

        selected_url = ""
        for subtitle in subtitle_entries:
            if "zh" in str(subtitle.get("lan", "")).lower():
                selected_url = str(subtitle.get("subtitle_url", "") or "")
                break
        if not selected_url:
            selected_url = str(subtitle_entries[0].get("subtitle_url", "") or "")
        if not selected_url:
            return "", []
        if selected_url.startswith("//"):
            selected_url = f"https:{selected_url}"

        subtitle_payload = await self._fetch_json(selected_url)
        items = normalize_subtitle_items(subtitle_payload.get("body"))
        text = "\n".join(item["content"] for item in items if item.get("content"))
        return text, items

    async def search_video(self, keyword: str, page: int = 1) -> list[dict[str, Any]]:
        raw = await self._call_api(
            "search_video",
            search.search_by_type(
                keyword,
                search_type=search.SearchObjectType.VIDEO,
                page=page,
            ),
        )
        raw_list = raw.get("result") if isinstance(raw, dict) else []
        return normalize_search_results(raw_list)

    async def get_hot_videos(self, page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
        raw = await self._call_api(
            "get_hot_videos",
            hot.get_hot_videos(pn=page, ps=page_size),
        )
        raw_list = []
        if isinstance(raw, dict):
            raw_list = raw.get("list") or raw.get("data", {}).get("list", [])
        return normalize_hot_rank_list(raw_list)

    async def get_rank_videos(self, day: int = 3) -> list[dict[str, Any]]:
        day_type = rank.RankDayType.THREE_DAY if day == 3 else rank.RankDayType.WEEK
        raw = await self._call_api(
            "get_rank_videos",
            rank.get_rank(day=day_type),
        )
        raw_list = []
        if isinstance(raw, dict):
            raw_list = raw.get("list") or raw.get("data", {}).get("list", [])
        return normalize_hot_rank_list(raw_list)

    async def get_related_videos(self, url_or_bvid: str) -> list[dict[str, Any]]:
        bvid = self.extract_bvid(url_or_bvid)
        raw = await self._call_api(
            "get_related_videos",
            self._video_factory(bvid=bvid, credential=self._credential).get_related(),
        )
        return normalize_hot_rank_list(raw if isinstance(raw, list) else [])

    async def get_video_ai_conclusion(self, url_or_bvid: str) -> str:
        bvid = self.extract_bvid(url_or_bvid)
        video_client = self._video_factory(bvid=bvid, credential=self._credential)
        pages = await self._call_api("get_pages", video_client.get_pages())
        if not pages:
            return ""

        cid = pages[0].get("cid")
        if not cid:
            return ""

        raw = await self._call_api(
            "get_video_ai_conclusion",
            video_client.get_ai_conclusion(cid=cid),
        )
        return normalize_ai_conclusion(raw if isinstance(raw, dict) else {})

    async def get_audio_url(self, url_or_bvid: str) -> str:
        bvid = self.extract_bvid(url_or_bvid)
        video_client = self._video_factory(bvid=bvid, credential=self._credential)
        download_data = await self._call_api(
            "get_audio_url",
            video_client.get_download_url(page_index=0),
        )
        detector = VideoDownloadURLDataDetecter(download_data)
        streams = detector.detect_best_streams(
            audio_max_quality=AudioQuality._64K,
            no_dolby_audio=True,
            no_hires=True,
        )

        if hasattr(detector, "check_flv_mp4_stream") and detector.check_flv_mp4_stream():
            if streams and getattr(streams[0], "url", ""):
                return str(streams[0].url)
        else:
            if len(streams) >= 2 and getattr(streams[1], "url", ""):
                return str(streams[1].url)
            for stream in streams:
                if getattr(stream, "audio_quality", None) is not None and getattr(stream, "url", ""):
                    return str(stream.url)
                if getattr(stream, "url", ""):
                    return str(stream.url)

        raise BiliError("get_audio_url: no audio stream found")

    async def download_audio(self, audio_url: str, output_path: str) -> int:
        timeout = aiohttp.ClientTimeout(total=300)
        max_retries = 3

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(audio_url, headers=_DOWNLOAD_HEADERS) as response:
                        if response.status != 200:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2)
                                continue
                            raise NetworkError(f"download_audio: HTTP {response.status}")

                        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                        total_bytes = 0
                        with open(output_path, "wb") as handle:
                            async for chunk in response.content.iter_chunked(256 * 1024):
                                if not chunk:
                                    continue
                                handle.write(chunk)
                                total_bytes += len(chunk)
                        return total_bytes
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                raise NetworkError(f"download_audio: {exc}") from exc

        raise NetworkError("download_audio: retry limit exhausted")

    async def _call_api(self, action: str, awaitable):
        try:
            return await awaitable
        except Exception as exc:  # noqa: BLE001
            raise _map_api_error(action, exc) from exc

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        if self._json_fetcher is not None:
            payload = await self._json_fetcher(url)
            return payload if isinstance(payload, dict) else {}

        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise NetworkError(f"fetch_subtitle_json: {exc}") from exc
        return payload if isinstance(payload, dict) else {}
