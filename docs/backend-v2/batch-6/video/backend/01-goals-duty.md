# Video 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 视频内容获取与总结

为 notebook 用户提供从 Bilibili 视频中提取和总结内容的能力。用户输入视频 URL 或 BV 号，系统自动获取视频元信息、提取字幕（或通过 ASR 转录），并调用 LLM 生成结构化总结。总结结果作为独立实体持久化，可反复查阅。

### 1.2 双通道触发，互不阻塞

Video 模块支持两条独立的触发路径：

| 通道 | 触发方式 | 执行路径 | 特征 |
|------|---------|---------|------|
| Studio 面板 | 用户在 Video 面板输入 URL/BV 号，点击按钮 | VideoService.summarize() 通过独立 SSE 端点推送进度 | 不占用 main 面板的 agent 资源 |
| Agent 对话 | 用户在 main 面板使用 /video slash 命令 | agent loop 调用 video skill 工具，内部委托 VideoService | Video 面板同步展示结果 |

两条路径共享底层的 VideoService，上层解耦。面板内总结与 agent 对话可以同时进行，互不干扰。

### 1.3 松耦合的 notebook 关联

视频总结默认独立存在，不强制绑定到任何 notebook。用户可以选择性地：

- 将总结关联到当前 notebook
- 将总结与 notebook 中的 documents 建立关联（标记视频内容与哪些文档相关）
- 随时取消关联

这种松耦合设计保证了工具的轻量易用性，同时不丧失融入 notebook 知识体系的能力。

### 1.4 平台可扩展

第一阶段仅实现 Bilibili 平台。通过 platform 字段和基础设施层的隔离设计，为后续接入 YouTube 等平台预留扩展空间，不需要修改上层的 service、skill、API 逻辑。

### 1.5 Slash 命令驱动的工具注入

与 Note、Diagram 一致，agent 默认看不到视频相关工具。只有用户使用 `/video` 前缀时，VideoSkillProvider 的工具集才被注入到当前请求的 agent 工具列表中。

## 2. 职责

### 2.1 BilibiliClient

封装 bilibili-api-python SDK，提供规范化的异步 API。负责：

- 视频元信息获取（标题、时长、封面、UP 主、统计数据）
- 字幕提取（优先中文字幕，降级到其他语言）
- 视频搜索（关键词搜索）
- 内容发现（热门视频、排行榜、相关推荐）
- B 站 AI 摘要获取
- 音频流地址获取与下载（为 ASR pipeline 服务）
- BV 号提取与格式校验
- 异常映射（将 SDK 异常统一为模块内异常层级）

### 2.2 ASR Pipeline

为没有字幕的视频提供语音转文字能力。负责：

- 音频下载（选择最低码率以减少传输量）
- 音频分段（PyAV 解码，重采样为 16kHz 单声道，按固定时长切分为 WAV 段）
- 并发调用 ASR 服务（GLM-ASR）进行转录
- 按顺序拼接各段转录文本

### 2.3 B 站认证管理

管理用户的 Bilibili 登录凭证。负责：

- QR 码登录流程（生成二维码、轮询登录状态）
- 凭证持久化与加载
- 登录状态查询

### 2.4 VideoService

核心应用服务，负责：

- 视频总结的完整 pipeline 编排（元信息获取 -> 字幕提取 -> ASR 降级 -> LLM 总结 -> 持久化）
- VideoSummary 实体的 CRUD 操作
- Notebook 和 Document 的关联与解关联
- 视频搜索和发现的代理转发（委托给 BilibiliClient）
- 总结进度的回调通知

### 2.5 VideoSkillProvider

构建 `/video` skill 的 SkillManifest。将 VideoService 的能力适配为 agent 可调用的 ToolDefinition 列表。声明哪些工具需要用户确认。

### 2.6 Video REST API

提供 HTTP 端点，服务前端 Video 面板的直接操作。负责：

- 视频总结的触发与 SSE 进度推送
- 已有总结的列表、详情、删除
- 视频信息查询（不触发总结）
- Notebook/Document 关联管理
- B 站认证相关端点

## 3. 非职责

- 不负责 agent loop 的执行控制（属于 core/engine）
- 不负责 SkillRegistry 的注册与匹配逻辑（属于 core/skills，本模块只提供 Provider 实现）
- 不负责 LLM 的配置和调用抽象（复用现有 llm_client）
- 不负责 SSE 事件的传输协议（复用现有 StreamingResponse 基础设施）
- 不负责前端 Video 面板的 UI 渲染（属于前端模块）
- 不实现 YouTube 等其他平台的接入（属于后续 batch）
- 不实现用户 B 站账号的收藏夹、关注列表、观看历史等个人数据管理功能（第一阶段不涉及）
- 不实现视频的点赞、投币、三连等社交互动操作（产品定位是笔记工具，不是 B 站客户端）
- 不负责将总结内容索引到向量数据库（如需纳入 RAG，通过关联 document 的方式由现有 document pipeline 处理）
