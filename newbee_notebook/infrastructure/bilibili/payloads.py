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


def _parse_duration_text(value: object) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    parts = [segment.strip() for segment in value.split(":") if segment.strip()]
    if not parts:
        return 0
    try:
        numbers = [int(segment) for segment in parts]
    except ValueError:
        return 0
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
        return hours * 3600 + minutes * 60 + seconds
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    return numbers[0]


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


def normalize_search_results(raw_list: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in raw_list or []:
        if not isinstance(item, dict):
            continue
        video_id = str(item.get("bvid") or "")
        url = str(item.get("arcurl") or "").strip()
        if not url and video_id:
            url = f"https://www.bilibili.com/video/{video_id}"
        results.append(
            {
                "video_id": video_id,
                "title": _strip_html(item.get("title")),
                "url": url,
                "author": str(item.get("author") or ""),
                "duration": _parse_duration_text(item.get("duration")),
                "play_count": _to_int(item.get("play"), 0),
                "description": _strip_html(item.get("description")),
            }
        )
    return results


def normalize_hot_rank_list(raw_list: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        normalize_video_info(item)
        for item in (raw_list or [])
        if isinstance(item, dict)
    ]


def normalize_ai_conclusion(raw: dict[str, Any] | None) -> str:
    if not isinstance(raw, dict):
        return ""
    model_result = raw.get("model_result")
    if isinstance(model_result, dict):
        summary = model_result.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        result = model_result.get("result")
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                nested_summary = item.get("summary")
                if isinstance(nested_summary, str) and nested_summary.strip():
                    return nested_summary.strip()
    summary = raw.get("summary")
    if isinstance(summary, str):
        return summary.strip()
    return ""
