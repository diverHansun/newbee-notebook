# Video 模块：Bilibili 基础设施层

## 1. 概述

`infrastructure/bilibili/` 是 Video 模块与 Bilibili 平台交互的唯一通道。所有 B 站 API 调用、数据规范化、异常映射、认证管理和 ASR 转录逻辑集中在此层，上层（VideoService、VideoSkillProvider）不直接依赖 bilibili-api-python SDK。

本层的代码主要从两个参考项目移植：

| 来源 | 移植内容 |
|------|---------|
| bilibili-cli/bili_cli | BilibiliClient 核心方法、payloads 规范化函数、异常层级、BV 号提取 |
| bilibili-summary | 字幕提取流程、ASR pipeline、音频下载与分段逻辑 |

## 2. BilibiliClient

封装 bilibili-api-python SDK 的异步客户端。所有方法返回经过 payloads 规范化后的稳定数据结构，而非原始 API 响应。

### 2.1 构造与凭证注入

BilibiliClient 接受外部注入的 Credential 对象，不在内部管理凭证生命周期。Credential 为 None 时，仍可使用不需要登录的 API（搜索、视频信息、字幕获取等大部分功能）。

### 2.2 方法清单

| 方法 | 用途 | 是否需要登录 | 返回结构 |
|------|------|------------|---------|
| `get_video_info(bvid)` | 获取视频元信息与统计数据 | 否 | 规范化的视频摘要 dict |
| `get_video_subtitle(bvid)` | 提取视频字幕 | 否 | `(plain_text, subtitle_items)` |
| `get_video_ai_conclusion(bvid)` | 获取 B 站 AI 生成的视频摘要 | 否 | 摘要文本 |
| `get_video_comments(bvid)` | 获取热门评论 | 否 | 规范化的评论列表 |
| `get_related_videos(bvid)` | 获取相关推荐视频 | 否 | 规范化的视频列表 |
| `search_video(keyword, page)` | 关键词搜索视频 | 否 | 规范化的搜索结果列表 |
| `get_hot_videos(page)` | 获取热门视频 | 否 | 规范化的视频列表 |
| `get_rank_videos(day)` | 获取排行榜 | 否 | 规范化的视频列表 |
| `get_audio_url(bvid)` | 获取音频流下载地址 | 否 | URL 字符串 |
| `download_audio(url, path)` | 下载音频文件 | 否 | 文件字节数 |
| `extract_bvid(url_or_bvid)` | 从 URL 或字符串中提取 BV 号 | - | BV 号字符串 |

### 2.3 字幕提取流程

移植自 bilibili-summary 的 `get_subtitle()` 实现：

1. 调用 `video.Video.get_pages()` 获取第一个分 P 的 cid
2. 调用 `video.Video.get_player_info(cid)` 获取字幕元信息
3. 从字幕列表中优先选择中文字幕（`lan` 包含 `"zh"`），无中文则取第一个
4. 通过 aiohttp 下载字幕 JSON，提取 body 数组
5. 返回纯文本（各条内容用换行拼接）和原始字幕条目列表

### 2.4 错误处理

移植 bilibili-cli 的 `_map_api_error` 模式，将 SDK 异常统一映射为模块内异常：

| SDK 异常 | 映射目标 | 场景 |
|---------|---------|------|
| CredentialNoSessdataException | AuthenticationError | 缺少登录凭证 |
| ResponseCodeException (-404, 62002, 62004) | NotFoundError | 视频/用户不存在 |
| ResponseCodeException (-412, 412) | RateLimitError | 请求频率过高 |
| NetworkException, aiohttp.ClientError | NetworkError | 网络故障 |
| 其他 | BiliError | 兜底 |

## 3. 数据规范化（payloads）

移植自 bilibili-cli 的 `payloads.py`，提供一组 `normalize_*()` 函数，将 B 站原始 API 响应转为稳定的内部结构。

### 3.1 核心规范化函数

| 函数 | 输出字段 |
|------|---------|
| `normalize_video_summary(raw)` | id, bvid, aid, title, description, duration_seconds, duration, url, owner{id, name}, stats{view, danmaku, like, coin, favorite, share} |
| `normalize_subtitle_items(raw)` | [{from, to, content}, ...] |
| `normalize_search_video(raw)` | id, bvid, title, author, play, duration |
| `normalize_comment(raw)` | id, author{id, name}, message, like, reply_count |

### 3.2 规范化原则

- HTML 标签清除：搜索结果中的 title 可能包含 `<em>` 等高亮标签，统一通过 `_strip_html()` 移除
- 时长格式化：秒数统一通过 `_format_duration()` 转为 `"MM:SS"` 或 `"H:MM:SS"` 人可读格式
- 安全取值：所有字段使用 `.get()` 带默认值，避免 KeyError
- 类型规范：数值类字段统一通过 `_to_int()` 处理，容忍字符串或浮点数输入

## 4. 异常层级

```
BiliError（基类）
  ├── InvalidBvidError      # BV 号格式错误或无法解析
  ├── NetworkError          # 网络请求失败
  ├── AuthenticationError   # 登录凭证缺失或过期
  ├── RateLimitError        # B 站限流
  └── NotFoundError         # 视频/用户/资源不存在
```

上层（VideoService）捕获这些异常并转为对应的 HTTP 状态码或 ToolCallResult 错误信息。

## 5. 认证管理（auth）

### 5.1 QR 码登录流程

1. 后端调用 bilibili-api-python 的 QrCodeLogin 生成登录二维码
2. 将二维码 URL 返回给前端，前端渲染二维码图片
3. 后端轮询登录状态（每 2 秒一次）
4. 用户扫码确认后，获取 Credential 对象
5. 将凭证信息（sessdata, bili_jct, ac_time_value 等）持久化到后端配置

### 5.2 凭证存储

凭证存储在后端的配置文件或数据库中（具体方案需结合现有 settings 模块确定）。BilibiliClient 通过依赖注入获取 Credential，不直接读取存储。

### 5.3 凭证有效性

B 站的登录凭证有时效性。当 API 调用返回 AuthenticationError 时，前端应提示用户重新登录。不做自动刷新。

## 6. ASR 转录 Pipeline

为没有字幕的视频提供语音转文字能力。移植自 bilibili-summary 的 ASR 实现。

### 6.1 Pipeline 步骤

1. **获取音频流地址** -- 使用 VideoDownloadURLDataDetecter 选择最低码率（64K）的音频流，减少下载量
2. **下载音频** -- 通过 aiohttp 流式下载，3 次重试，带 Referer 头伪装
3. **音频分段** -- 使用 PyAV 解码 m4s 文件，重采样为 16kHz 单声道 PCM s16le，按 29 秒切分为 WAV 段（ASR 服务限制 30 秒）
4. **并发转录** -- 5 路并发调用 GLM-ASR 服务（glm-asr-2512 模型），每段 3 次重试，指数退避
5. **结果拼接** -- 按段序号顺序拼接转录文本

### 6.2 ASR 服务配置

当前使用智谱 GLM-ASR 服务，端点为 `https://open.bigmodel.cn/api/paas/v4/audio/transcriptions`。API Key 复用现有的智谱配置。

### 6.3 资源清理

临时音频文件（m4s 原始文件和 WAV 分段文件）在处理完成后立即删除，不论处理成功或失败。使用 try/finally 保证清理逻辑执行。
