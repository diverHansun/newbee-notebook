# BilibiliClient Missing Methods Patch

## Current State

`infrastructure/bilibili/client.py` implements 3 methods:

| Method | Status |
|--------|--------|
| `extract_bvid` | done |
| `get_video_info` | done |
| `get_video_subtitle` | done |

The following 7 methods are required by VideoService and VideoSkillProvider but missing,
causing runtime `AttributeError` on invocation.

---

## Methods to Add

All method signatures follow the existing BilibiliClient class pattern:
accept `url_or_bvid` (auto-extract BV via `self.extract_bvid`),
delegate to `bilibili-api-python` SDK, normalize via payloads module,
map exceptions via `_map_api_error`.

Reference implementation: `bilibili-cli/bili_cli/client.py`.

### 1. search_video

```python
async def search_video(self, keyword: str, page: int = 1) -> list[dict[str, Any]]:
```

- SDK: `search.search_by_type(keyword, search_type=SearchObjectType.VIDEO, page=page)`
- Returns: list of normalized video items `[{video_id, title, url, author, duration, stats}]`
- Normalize: add `normalize_search_results()` to `payloads.py`
- Note: no credential required

### 2. get_hot_videos

```python
async def get_hot_videos(self, page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
```

- SDK: `hot.get_hot_videos(pn=page, ps=page_size)`
- Returns: list of normalized video items
- Normalize: reuse `normalize_video_info()` for each item in `data.list`

### 3. get_rank_videos

```python
async def get_rank_videos(self, day: int = 3) -> list[dict[str, Any]]:
```

- SDK: `rank.get_rank(day=RankDayType.THREE_DAY | WEEK)`
- Day parameter: 3 -> THREE_DAY, 7 -> WEEK
- Returns: list of normalized video items from `data.list`

### 4. get_related_videos

```python
async def get_related_videos(self, url_or_bvid: str) -> list[dict[str, Any]]:
```

- SDK: `Video(bvid).get_related()`
- Returns: list of normalized video items
- Normalize: iterate results, apply `normalize_video_info()` to each

### 5. get_video_ai_conclusion

```python
async def get_video_ai_conclusion(self, url_or_bvid: str) -> str:
```

- SDK: `Video(bvid).get_pages()` -> get first cid -> `Video(bvid).get_ai_conclusion(cid=cid)`
- Returns: AI summary plain text extracted from response
- Response structure: `{model_result: {summary: "..."}}` or similar
- Returns empty string if no AI conclusion available
- Note: requires credential for some videos

### 6. get_audio_url

```python
async def get_audio_url(self, url_or_bvid: str) -> str:
```

- SDK: `Video(bvid).get_download_url(page_index=0)` -> `VideoDownloadURLDataDetecter`
- Strategy: detect_best_streams with lowest audio quality (64K), no Dolby, no Hi-Res
- DASH format: audio stream at index 1; FLV format: streams[0].url
- Raises BiliError if no audio stream found (e.g., premium-only video)
- Reference: `bilibili-cli/bili_cli/client.py` lines 636-661

### 7. download_audio

```python
async def download_audio(self, audio_url: str, output_path: str) -> int:
```

- Uses aiohttp with Referer header (`https://www.bilibili.com`)
- Retry: 3 attempts, 2s delay between retries
- Returns bytes written
- Timeout: 300s (audio files can be large)
- Reference: `bilibili-cli/bili_cli/client.py` lines 664-695

---

## Payload Normalization Additions

File: `infrastructure/bilibili/payloads.py`

### normalize_search_results

```python
def normalize_search_results(raw_list: list[dict]) -> list[dict[str, Any]]:
```

Input: raw search result list from SDK.
Output per item:

| Field | Source | Fallback |
|-------|--------|----------|
| video_id | `bvid` | "" |
| title | `title` (strip HTML tags) | "" |
| url | `arcurl` | build from bvid |
| author | `author` | "" |
| duration | `duration` (parse "MM:SS" string to seconds) | 0 |
| play_count | `play` | 0 |
| description | `description` (strip HTML) | "" |

### normalize_hot_rank_list

```python
def normalize_hot_rank_list(raw_list: list[dict]) -> list[dict[str, Any]]:
```

Reuse `normalize_video_info()` per item. Hot/rank responses wrap individual video info objects.

### normalize_ai_conclusion

```python
def normalize_ai_conclusion(raw: dict) -> str:
```

Extract plain text summary from the AI conclusion response.
The response structure from `get_ai_conclusion` typically has:
`model_result.summary` or `model_result.result[0].summary`.
Return empty string if structure is unexpected.

---

## VideoSkillProvider Tool Restructure (12 -> 9)

### Before (12 tools)

1. search_video
2. get_video_info
3. get_video_subtitle
4. summarize_video
5. list_summaries
6. read_summary
7. delete_summary
8. get_hot_videos
9. get_rank_videos
10. get_related_videos
11. associate_notebook
12. disassociate_notebook

### After (9 tools)

| # | Tool | Parameters | Merges |
|---|------|-----------|--------|
| 1 | `discover_videos` | `source: "search"\|"hot"\|"rank"\|"related"`, `keyword?`, `bvid?`, `page?`, `day?` | search + hot + rank + related |
| 2 | `get_video_info` | `url_or_bvid` | unchanged |
| 3 | `get_video_content` | `url_or_bvid`, `type: "subtitle"\|"ai_conclusion"` | subtitle + ai_conclusion(new) |
| 4 | `summarize_video` | `url_or_bvid` | unchanged |
| 5 | `list_summaries` | `status?` | unchanged |
| 6 | `read_summary` | `summary_id` | unchanged |
| 7 | `delete_summary` | `summary_id` | unchanged (requires confirmation) |
| 8 | `associate_notebook` | `summary_id` | unchanged |
| 9 | `disassociate_notebook` | `summary_id` | unchanged (requires confirmation) |

### Tool Implementation Details

**discover_videos**

```python
async def execute(args):
    source = args["source"]
    if source == "search":
        results = await service.search_videos(args["keyword"], page=args.get("page", 1))
    elif source == "hot":
        results = await service.get_hot_videos(page=args.get("page", 1))
    elif source == "rank":
        results = await service.get_rank_videos(day=args.get("day", 3))
    elif source == "related":
        results = await service.get_related_videos(args["bvid"])
    # format and return
```

Parameter validation: `source` is required. `keyword` is required when `source == "search"`.
`bvid` is required when `source == "related"`.

**get_video_content**

```python
async def execute(args):
    url_or_bvid = args["url_or_bvid"]
    content_type = args.get("type", "subtitle")
    if content_type == "subtitle":
        text = await service.get_video_subtitle(url_or_bvid)
        return ToolCallResult(content=text or "No subtitle available.")
    elif content_type == "ai_conclusion":
        text = await service.get_video_ai_conclusion(url_or_bvid)
        return ToolCallResult(content=text or "No AI conclusion available for this video.")
```

### System Prompt Update

The VideoSkillProvider system prompt should be updated to reflect the merged tools:

- `discover_videos`: use `source="search"` for keyword search, `source="hot"` for trending,
  `source="rank"` for rankings, `source="related"` for recommendations
- `get_video_content`: use `type="ai_conclusion"` to quickly understand a video without
  full summarization; use `type="subtitle"` when you need the full transcript text
- `summarize_video`: only invoke for full AI summarization (slow, 30-90s)

---

## VideoService Proxy Methods

VideoService needs to add proxy methods for the new BilibiliClient methods:

```python
async def get_hot_videos(self, page: int = 1) -> list[dict]:
    return await self._bili_client.get_hot_videos(page=page)

async def get_rank_videos(self, day: int = 3) -> list[dict]:
    return await self._bili_client.get_rank_videos(day=day)

async def get_related_videos(self, url_or_bvid: str) -> list[dict]:
    return await self._bili_client.get_related_videos(url_or_bvid)

async def get_video_ai_conclusion(self, url_or_bvid: str) -> str:
    return await self._bili_client.get_video_ai_conclusion(url_or_bvid)
```

`search_videos` already exists in VideoService but delegates to a missing client method.

---

## SDK Import Additions

The following `bilibili-api-python` modules need to be imported in client.py:

```python
from bilibili_api import hot, rank, search
from bilibili_api.video import AudioQuality, VideoDownloadURLDataDetecter
```

`bilibili-api-python` is already a project dependency (used by existing client).

---

## Constants

Add to client.py:

```python
_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}
```

Used by `download_audio` for bypassing hotlink protection.
