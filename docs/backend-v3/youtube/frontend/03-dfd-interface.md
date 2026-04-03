# 数据流与接口定义

## 1. summarize 请求

前端向 `/api/v1/videos/summarize` 提交：

```json
{
  "url_or_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "notebook_id": "nb-1",
  "lang": "en"
}
```

说明：

- `lang` 直接取当前 `useLang()`
- 当前后端兼容 `url_or_bvid`，但前端新代码统一发送 `url_or_id`

## 2. 平台检测数据流

```text
input change
   |
   v
detectPlatform()
   |
   +--> bilibili
   +--> youtube
   +--> unknown
   +--> null
```

## 3. SSE 事件处理

### 3.1 事件映射

前端 API 层需要支持：

- `start`
- `info`
- `subtitle`
- `asr`
- `summarize`
- `done`
- `error`

并且对未知事件安全忽略，而不是直接 throw。

### 3.2 `info` 用途

`info` 事件建议用于：

- 更新标题
- 更新作者 / 频道
- 更新封面
- 更新时长

不一定必须强制新增一个大步骤条节点。

### 3.3 `subtitle.source`

前端根据后端返回的 `subtitle.source` 显示：

- `subtitle`
- `caption_tracks`
- `asr`

后续如需要可以映射成更友好的 UI 文案。

## 4. 列表过滤数据流

```text
activeQuery = videoFilterMode === "all" ? allVideosQuery : notebookVideosQuery
filteredSummaries = activeQuery.data.summaries.filter(byPlatform)
```

## 5. 文案策略

Video 文案从“Bilibili 专属”升级为：

- 通用入口文案
- Bilibili 登录文案
- YouTube 无需登录文案
- 通用错误文案
