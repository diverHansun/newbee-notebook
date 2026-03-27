"""Thin async client adapters around bilibili-api-python."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

import aiohttp
from bilibili_api import video
from bilibili_api.exceptions import (
    CredentialNoBiliJctException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
)

from newbee_notebook.infrastructure.bilibili.exceptions import (
    AuthenticationError,
    BiliError,
    InvalidBvidError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from newbee_notebook.infrastructure.bilibili.payloads import (
    normalize_subtitle_items,
    normalize_video_info,
)

_BVID_RE = re.compile(r"\bBV[0-9A-Za-z]{10}\b")


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
