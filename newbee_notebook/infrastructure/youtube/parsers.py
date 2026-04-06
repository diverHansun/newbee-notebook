"""Parsers for YouTube transcript payloads."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from xml.etree import ElementTree


_TIMESTAMP_RE = re.compile(
    r"^\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?"
)
_NUMERIC_LINE_RE = re.compile(r"^\d+$")


def ensure_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query[key] = [value]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def extract_initial_player_response(html: str) -> dict[str, Any] | None:
    markers = (
        "ytInitialPlayerResponse = ",
        "var ytInitialPlayerResponse = ",
        'window["ytInitialPlayerResponse"] = ',
        "window['ytInitialPlayerResponse'] = ",
    )
    for marker in markers:
        marker_index = html.find(marker)
        if marker_index == -1:
            continue
        brace_index = html.find("{", marker_index + len(marker))
        if brace_index == -1:
            continue
        raw_json = _extract_balanced_json_object(html, brace_index)
        if raw_json is None:
            continue
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            continue
    return None


def extract_innertube_api_key(html: str) -> str | None:
    match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    if match is None:
        return None
    return match.group(1).strip() or None


def extract_caption_tracks(player_response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(player_response, dict):
        return []
    renderer = (
        player_response.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
    )
    tracks = list(renderer.get("captionTracks", []) or [])

    automatic_captions = renderer.get("automaticCaptions")
    if isinstance(automatic_captions, list):
        tracks.extend(item for item in automatic_captions if isinstance(item, dict))
    elif isinstance(automatic_captions, dict):
        for value in automatic_captions.values():
            if isinstance(value, dict):
                nested = value.get("captionTracks")
                if isinstance(nested, list):
                    tracks.extend(item for item in nested if isinstance(item, dict))
            elif isinstance(value, list):
                tracks.extend(item for item in value if isinstance(item, dict))

    return tracks


def extract_streaming_formats(player_response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(player_response, dict):
        return []

    streaming_data = player_response.get("streamingData") or {}
    if not isinstance(streaming_data, dict):
        return []

    formats: list[dict[str, Any]] = []
    for key in ("adaptiveFormats", "formats"):
        values = streaming_data.get(key) or []
        if isinstance(values, list):
            formats.extend(item for item in values if isinstance(item, dict))
    return formats


def pick_best_track(
    tracks: list[dict[str, Any]],
    *,
    preferred_languages: list[str],
) -> dict[str, Any] | None:
    if not tracks:
        return None

    language_rank = {code: index for index, code in enumerate(preferred_languages)}
    deduped: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []

    for track in tracks:
        language_code = str(track.get("languageCode") or "").strip()
        base_url = str(track.get("baseUrl") or "").strip()
        if not language_code or not base_url:
            continue
        normalized_key = language_code.lower()
        candidate = {
            **track,
            "languageCode": language_code,
            "baseUrl": base_url,
        }
        existing = deduped.get(normalized_key)
        if existing is None or _track_sort_key(candidate, language_rank) < _track_sort_key(existing, language_rank):
            deduped[normalized_key] = candidate

    ordered.extend(deduped.values())
    ordered.sort(key=lambda item: _track_sort_key(item, language_rank))
    return ordered[0] if ordered else None


def parse_json3_transcript(raw: str) -> str | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    events = payload.get("events")
    if not isinstance(events, list):
        return None

    lines: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs") or []
        if not isinstance(segs, list):
            continue
        text = "".join(
            unescape(str(seg.get("utf8") or ""))
            for seg in segs
            if isinstance(seg, dict)
        ).strip()
        if text:
            lines.append(text)
    return _normalize_lines(lines)


def parse_xml_transcript(raw: str) -> str | None:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return None

    lines: list[str] = []
    for element in root.iter():
        if not str(element.tag).lower().endswith("text"):
            continue
        text = unescape("".join(element.itertext())).strip()
        if text:
            lines.append(text)
    return _normalize_lines(lines)


def parse_vtt_transcript(raw: str) -> str | None:
    lines: list[str] = []
    for row in raw.splitlines():
        line = row.strip("\ufeff").strip()
        if not line:
            continue
        upper = line.upper()
        if upper == "WEBVTT" or upper.startswith("NOTE"):
            continue
        if _TIMESTAMP_RE.match(line):
            continue
        if _NUMERIC_LINE_RE.match(line):
            continue
        lines.append(unescape(line))
    return _normalize_lines(lines)


def parse_srt_transcript(raw: str) -> str | None:
    lines: list[str] = []
    for row in raw.splitlines():
        line = row.strip()
        if not line:
            continue
        if _NUMERIC_LINE_RE.match(line):
            continue
        if _TIMESTAMP_RE.match(line):
            continue
        lines.append(unescape(line))
    return _normalize_lines(lines)


def _extract_balanced_json_object(raw: str, start_index: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start_index, len(raw)):
        ch = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start_index:index + 1]
    return None


def _track_sort_key(track: dict[str, Any], language_rank: dict[str, int]) -> tuple[int, int, str]:
    language_code = str(track.get("languageCode") or "").lower()
    preferred_rank = _resolve_language_rank(language_code, language_rank)
    is_auto = str(track.get("kind") or "").lower() == "asr"
    return (1 if is_auto else 0, preferred_rank, language_code)


def _resolve_language_rank(language_code: str, language_rank: dict[str, int]) -> int:
    if language_code in language_rank:
        return language_rank[language_code]
    base_language = language_code.split("-", 1)[0]
    return language_rank.get(base_language, len(language_rank) + 100)


def _normalize_lines(lines: list[str]) -> str | None:
    normalized: list[str] = []
    previous = ""
    for value in lines:
        collapsed = " ".join(value.split()).strip()
        if not collapsed:
            continue
        if collapsed == previous:
            continue
        normalized.append(collapsed)
        previous = collapsed
    if not normalized:
        return None
    return "\n".join(normalized)
