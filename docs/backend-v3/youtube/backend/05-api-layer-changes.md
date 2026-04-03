# API 层变更

## 1. 请求模型

### 1.1 `SummarizeRequest`

目标协议：

```python
class SummarizeRequest(BaseModel):
    url_or_id: str
    notebook_id: str | None = None
    lang: Literal["zh", "en"] = "zh"
```

兼容策略：

- 后端继续接受 `url_or_bvid`
- 后端内部统一映射到 `url_or_id`

这样前端可以逐步切到新字段，不需要和后端一次性同步发布。

## 2. SSE 事件

### 2.1 保持兼容

现有事件仍然有效：

- `start`
- `subtitle`
- `asr`
- `summarize`
- `done`
- `error`

### 2.2 YouTube 增量扩展

新增：

- `info`

并扩展：

- `subtitle.source`
- `summarize.lang`

### 2.3 事件示例

```text
event: start
data: {"video_id":"dQw4w9WgXcQ","summary_id":"...","status":"processing"}

event: info
data: {"video_id":"dQw4w9WgXcQ","title":"...","duration_seconds":212,"uploader_name":"...","cover_url":"..."}

event: subtitle
data: {"video_id":"dQw4w9WgXcQ","available":true,"source":"caption_tracks","char_count":18432}

event: summarize
data: {"video_id":"dQw4w9WgXcQ","lang":"en"}

event: done
data: {"summary_id":"...","status":"completed","reused":false}
```

## 3. 路由层变化

`POST /api/v1/videos/summarize` 继续复用，不新增端点。

路由层只负责：

- 读取兼容字段
- 透传 `lang`
- 保持现有 SSE response 包装

## 4. 现有其他端点

- `/videos/info` 在实现上扩展为支持 YouTube 输入
- `/videos/search`、`/videos/hot`、`/videos/rank`、`/videos/related` 仍以 Bilibili 为主

## 5. 错误处理

新增 YouTube 场景后，错误码仍然走统一视频 summarize 错误模型，不必为前端增加一套新的错误处理协议。前端重点识别：

- Bilibili auth error
- transcript unavailable
- generic summarize failed
