# 修复方案

与 [problem-analysis.md](problem-analysis.md) 配合阅读，本文档专注于具体变更内容，
不重复已在问题分析中展开的根因说明。

---

## 一、方案概述

本轮修复包含三处独立变更，按层级自底向上排列：

| 编号 | 层级 | 变更文件 | 变更内容 |
|------|------|---------|---------|
| Fix-1 | 基础设施层 | `infrastructure/bilibili/client.py` | 新增 `has_credentials()` |
| Fix-2 | 应用服务层 | `application/services/video_service.py` | 日志分级；入口前置检查 |
| Fix-3 | API 路由层 | `api/routers/videos.py` | `/videos/info` 异常转换 |

三处变更相互独立，可以分开实施。

---

## 二、Fix-1：新增 `has_credentials()`

**文件**：`newbee_notebook/infrastructure/bilibili/client.py`  
**位置**：`BilibiliClient` 类内，现有 `extract_bvid` 方法之后

```python
def has_credentials(self) -> bool:
    """Return True if a non-empty sessdata credential is configured."""
    return bool(
        self._credential is not None
        and getattr(self._credential, "sessdata", None)
    )
```

**说明**：

- 只检查本地对象状态，不发起网络请求。sessdata 存在且非空即视为具备凭据。
- 凭据存在不等于凭据有效（过期的 sessdata 在运行时仍会失败），
  本方法仅用于快速失败，不替代运行时的 `AuthenticationError` 捕获。

---

## 三、Fix-2：应用服务层两处变更

**文件**：`newbee_notebook/application/services/video_service.py`

### 3.1 日志分级

**位置**：`_handle_failure()` 方法

当前：
```python
async def _handle_failure(self, summary, video_id, exc, progress_callback):
    safe_error = self.build_stream_error_payload(exc)
    logger.exception("Video summarize failed for %s", video_id)
    ...
```

修改为：
```python
_EXPECTED_USER_ERRORS = (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    InvalidBvidError,
    VideoTranscriptUnavailableError,
    VideoSummarizingInProgressError,
    VideoConcurrentProcessingLimitError,
    InvalidYouTubeInputError,
    InvalidYouTubeVideoIdError,
    YouTubeVideoUnavailableError,
    YouTubeNetworkError,
)

async def _handle_failure(self, summary, video_id, exc, progress_callback):
    safe_error = self.build_stream_error_payload(exc)
    if isinstance(exc, _EXPECTED_USER_ERRORS):
        logger.warning("Video summarize expected failure for %s: %s", video_id, exc)
    else:
        logger.exception("Video summarize failed for %s", video_id)
    ...
```

`_EXPECTED_USER_ERRORS` 的成员与 `build_stream_error_payload` 中有具体 `error_code` 映射的异常保持一致，
两者互为参照，作为同一"预期错误"集合的两种表达形式。

**导入侧需同步补充**（如果尚未引入）：
```python
from newbee_notebook.infrastructure.bilibili.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    InvalidBvidError,
)
```

### 3.2 `_summarize_bilibili` 入口前置检查

**位置**：`_summarize_bilibili()` 方法内，`_prepare_processing_summary` 调用之后，`try` 块之前

当前（简化展示）：
```python
async def _summarize_bilibili(self, url_or_id, *, notebook_id, lang, progress_callback):
    bvid = await self._extract_bvid(url_or_id)
    summary, reused = await self._prepare_processing_summary(...)
    if reused:
        ...
        return summary

    await self._emit(progress_callback, "start", {...})

    try:
        info = await self._bili_client.get_video_info(bvid)   # <-- 此时才发现认证失败
        ...
        transcript_text, _tracks = await self._bili_client.get_video_subtitle(bvid)
        ...
```

修改：在 `emit("start", ...)` 之前插入前置检查：

```python
    await self._emit(progress_callback, "start", {...})

    if not self._bili_client.has_credentials():
        raise AuthenticationError(
            "Bilibili session required. Please log in first."
        )

    try:
        info = await self._bili_client.get_video_info(bvid)
        ...
```

**说明**：

- 放在 `emit("start", ...)` 之后，保证前端能收到 `start` 事件，知道请求已被接受，
  再通过后续的 `error` 事件获知失败原因。
- 放在 `try` 块之外，异常会在 `_summarize_bilibili` 内部向上传播，
  由调用链的 `except Exception as exc` 捕获，走统一的 `_handle_failure` 路径。
- 由于是 `AuthenticationError`，`_handle_failure` 改造后会以 `warning` 级别记录，
  不产生 traceback。

---

## 四、Fix-3：`/videos/info` 端点异常转换

**文件**：`newbee_notebook/api/routers/videos.py`

当前：
```python
@router.get("/videos/info", response_model=VideoInfoResponse)
async def get_video_info(
    url_or_id: Optional[str] = Query(None, min_length=1),
    url_or_bvid: Optional[str] = Query(None, min_length=1),
    service: VideoService = Depends(get_video_service),
):
    value = url_or_id or url_or_bvid
    if not value:
        raise HTTPException(status_code=422, detail="url_or_id is required")
    return VideoInfoResponse(**(await service.fetch_video_info(value)))
```

修改：
```python
from newbee_notebook.infrastructure.bilibili.exceptions import (
    AuthenticationError as BiliAuthError,
    BiliError,
)

@router.get("/videos/info", response_model=VideoInfoResponse)
async def get_video_info(
    url_or_id: Optional[str] = Query(None, min_length=1),
    url_or_bvid: Optional[str] = Query(None, min_length=1),
    service: VideoService = Depends(get_video_service),
):
    value = url_or_id or url_or_bvid
    if not value:
        raise HTTPException(status_code=422, detail="url_or_id is required")
    try:
        return VideoInfoResponse(**(await service.fetch_video_info(value)))
    except BiliAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except BiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

**说明**：

- `BiliAuthError`（即 `AuthenticationError`）映射为 `401 Unauthorized`，
  与 REST 语义一致，前端可据此引导登录。
- `BiliError` 基类捕获其余基础设施层错误（网络、限流、资源不存在等），
  映射为 `502 Bad Gateway`，表示上游服务异常，避免暴露为 500。
- 引入时使用别名 `BiliAuthError` 避免与其他可能同名的变量冲突，
  也便于在 import 层面区分来源。

---

## 五、变更后的行为对比

| 场景 | 变更前 | 变更后 |
|------|--------|--------|
| 未登录发起总结 | 完成 `get_video_info` 后在 `get_player_info` 失败，日志输出完整 traceback | 在入口处直接失败，日志输出 `WARNING` 一行，无 traceback |
| 前端 SSE error 事件 | 正常下发 `E_BILIBILI_AUTH` | 不变，保持 `E_BILIBILI_AUTH` |
| 未登录调用 `/videos/info` | 500 Internal Server Error（假设 Bilibili 改为需要认证） | 401 Unauthorized |
| 系统级错误（数据库、网络异常等） | `logger.exception`，输出 traceback | 不变，仍输出 traceback |
