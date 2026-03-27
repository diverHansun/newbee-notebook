"""Stable payload normalizers for Bilibili API responses."""

from __future__ import annotations

import re
from typing import Any


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _strip_html(text: object) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def normalize_video_info(raw: dict[str, Any]) -> dict[str, Any]:
    owner = raw.get("owner", {}) if isinstance(raw.get("owner"), dict) else {}
    stats = raw.get("stat", {}) if isinstance(raw.get("stat"), dict) else {}
    video_id = str(raw.get("bvid") or raw.get("id") or "")
    source_url = str(raw.get("short_link_v2") or raw.get("short_link") or "").strip()
    if not source_url and video_id:
        source_url = f"https://www.bilibili.com/video/{video_id}"

    return {
        "video_id": video_id,
        "source_url": source_url,
        "title": _strip_html(raw.get("title")),
        "description": raw.get("desc", "") or raw.get("description", ""),
        "cover_url": raw.get("pic", "") or raw.get("cover", "") or raw.get("cover_url"),
        "duration_seconds": _to_int(raw.get("duration"), 0),
        "uploader_name": owner.get("name", owner.get("uname", "")),
        "uploader_id": str(owner.get("mid", owner.get("id", ""))),
        "stats": {
            "view": _to_int(stats.get("view", raw.get("play", 0)), 0),
            "danmaku": _to_int(stats.get("danmaku"), 0),
            "like": _to_int(stats.get("like"), 0),
            "coin": _to_int(stats.get("coin"), 0),
            "favorite": _to_int(stats.get("favorite"), 0),
            "share": _to_int(stats.get("share"), 0),
        },
    }


def normalize_subtitle_items(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "from": float(item.get("from", 0.0) or 0.0),
                "to": float(item.get("to", 0.0) or 0.0),
                "content": str(item.get("content", "") or ""),
            }
        )
    return items
