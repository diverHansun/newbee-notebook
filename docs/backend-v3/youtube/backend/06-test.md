# YouTube 扩展模块：验证策略

## 1. 后端测试重点

### 1.1 `VideoService`

- `url_or_id` / `url_or_bvid` 兼容
- `lang` 透传
- YouTube 与 Bilibili 平台路由
- YouTube transcript -> ASR 兜底
- `(platform, video_id)` 去重复用

### 1.2 `YouTubeClient`

- URL / ID 提取
- `yt-dlp` 元信息提取结果规范化
- transcript tier1 成功
- transcript tier1 失败 -> tier2 成功
- transcript 两层失败 -> `(None, "asr")`
- 音频下载路径

### 1.3 `parsers.py`

- `ytInitialPlayerResponse` 提取
- `captionTracks` 排序
- `json3/xml/vtt/srt` 解析

## 2. 集成测试重点

- summarize SSE 流在 YouTube 路径下的事件顺序
- `fetch_video_info()` 支持 YouTube URL
- `get_asr_pipeline_dep()` 能按平台下载音频

## 3. 不在自动化测试范围内

- 真实联网访问 YouTube 的可用性
- `yt-dlp` 第三方内部实现
- LLM 摘要语义质量

## 4. 手动验证清单

1. YouTube URL，存在字幕
2. YouTube URL，无字幕但 ASR 可用
3. YouTube ID 直接输入
4. Bilibili 旧链路回归
5. `/video` skill 下使用 YouTube URL 做 info + summarize
