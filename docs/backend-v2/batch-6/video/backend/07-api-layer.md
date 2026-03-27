# Video 模块：REST API 与 SSE 端点

## 1. 路由注册

两个 router 注册在 `/api/v1` 前缀下：

```python
app.include_router(videos.router, prefix="/api/v1", tags=["Videos"])
app.include_router(bilibili_auth.router, prefix="/api/v1", tags=["Bilibili Auth"])
```

## 2. Video Router（videos.py）

### 2.1 总结操作

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/videos/summarize` | 触发视频总结，SSE 流式返回进度 | SummarizeRequest | SSE EventStream |
| GET | `/videos` | 列出总结 | Query: notebook_id?, status? | VideoSummaryListResponse |
| GET | `/videos/{summary_id}` | 获取总结详情 | - | VideoSummaryResponse |
| DELETE | `/videos/{summary_id}` | 删除总结 | - | 204 |

### 2.2 视频信息查询（不触发总结）

| 方法 | 路径 | 说明 | 请求体/参数 | 响应 |
|------|------|------|-----------|------|
| GET | `/videos/info` | 查询视频元信息 | Query: url_or_bvid | VideoInfoResponse |
| GET | `/videos/search` | 搜索视频 | Query: keyword, page? | VideoSearchResponse |
| GET | `/videos/hot` | 热门视频 | Query: page? | VideoListResponse |
| GET | `/videos/rank` | 排行榜 | Query: day? | VideoListResponse |

### 2.3 关联管理

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/videos/{summary_id}/notebook` | 关联到 notebook | AssociateNotebookRequest | 204 |
| DELETE | `/videos/{summary_id}/notebook` | 取消 notebook 关联 | - | 204 |
| POST | `/videos/{summary_id}/documents` | 添加 document 关联 | TagDocumentRequest | 204 |
| DELETE | `/videos/{summary_id}/documents/{document_id}` | 移除 document 关联 | - | 204 |

## 3. Bilibili Auth Router（bilibili_auth.py）

| 方法 | 路径 | 说明 | 响应 |
|------|------|------|------|
| GET | `/bilibili/auth/qr` | 生成 QR 码登录，SSE 流式返回状态 | SSE EventStream |
| POST | `/bilibili/auth/logout` | 清除登录凭证 | 204 |
| GET | `/bilibili/auth/status` | 查询登录状态 | AuthStatusResponse |

## 4. SSE 端点设计

### 4.1 总结进度端点

`POST /api/v1/videos/summarize` 返回 `text/event-stream`，事件序列如下：

| 事件 event | data 字段 | 触发时机 |
|-----------|----------|---------|
| info | {title, duration, author_name, cover_url} | 获取到视频元信息 |
| subtitle | {available, char_count} | 字幕提取完成 |
| asr | {step, message} | ASR pipeline 各阶段进度 |
| summarize | {model} | 开始调用 LLM 生成总结 |
| done | {summary_id, duration_sec} | 总结完成 |
| error | {message} | 任何阶段的错误 |

SSE 格式遵循标准规范：

```
event: info
data: {"title": "视频标题", "duration": 600, "author_name": "UP主", "cover_url": "..."}

event: subtitle
data: {"available": true, "char_count": 12500}

event: summarize
data: {"model": "glm-4-flashx"}

event: done
data: {"summary_id": "uuid-...", "duration_sec": 45.2}
```

### 4.2 QR 码登录端点

`GET /api/v1/bilibili/auth/qr` 返回 `text/event-stream`，事件序列如下：

| 事件 event | data 字段 | 触发时机 |
|-----------|----------|---------|
| qr_generated | {qr_url} | 二维码 URL 生成，前端据此渲染二维码图片 |
| scanned | {} | 用户已扫码，等待确认 |
| done | {} | 登录成功，凭证已保存 |
| timeout | {} | 二维码过期 |
| error | {message} | 登录过程出错 |

## 5. 请求/响应模型

### 5.1 请求模型

```python
class SummarizeRequest(BaseModel):
    url_or_bvid: str
    notebook_id: str | None = None

class AssociateNotebookRequest(BaseModel):
    notebook_id: str

class TagDocumentRequest(BaseModel):
    document_id: str
```

### 5.2 响应模型

```python
class VideoSummaryResponse(BaseModel):
    summary_id: str
    notebook_id: str | None
    platform: str
    video_id: str
    url: str
    title: str
    cover_url: str
    duration: int
    author_name: str
    author_id: str
    summary_content: str
    summary_type: str
    status: str
    error_message: str
    document_ids: list[str]
    tags: list[str]
    stats: dict
    created_at: str
    updated_at: str

class VideoSummaryListItem(BaseModel):
    summary_id: str
    notebook_id: str | None
    platform: str
    video_id: str
    title: str
    cover_url: str
    duration: int
    author_name: str
    status: str
    summary_type: str
    created_at: str
    updated_at: str

class VideoSummaryListResponse(BaseModel):
    summaries: list[VideoSummaryListItem]
    total: int

class VideoInfoResponse(BaseModel):
    bvid: str
    title: str
    description: str
    duration: int
    duration_formatted: str
    url: str
    cover_url: str
    owner: dict          # {id, name}
    stats: dict          # {view, danmaku, like, coin, favorite, share}

class VideoSearchItem(BaseModel):
    bvid: str
    title: str
    author: str
    play: int
    duration: str

class VideoSearchResponse(BaseModel):
    results: list[VideoSearchItem]
    total: int

class AuthStatusResponse(BaseModel):
    logged_in: bool
    username: str | None = None
```

### 5.3 列表项与详情的字段差异

VideoSummaryListItem 不包含 summary_content、error_message、tags、stats 等大字段，减少列表查询的数据传输量。详情查询通过单独的 GET 端点获取完整信息。

## 6. 错误码映射

| 异常 | HTTP 状态码 | 场景 |
|------|-----------|------|
| VideoSummaryNotFoundError | 404 | 查询不存在的总结 |
| VideoAlreadyExistsError | 409 | 同一视频重复提交 |
| InvalidBvidError | 400 | BV 号格式错误 |
| AuthenticationError | 401 | B 站登录凭证缺失或过期 |
| NotFoundError | 404 | B 站视频不存在 |
| RateLimitError | 429 | B 站 API 限流 |
| NetworkError | 502 | B 站 API 网络故障 |
