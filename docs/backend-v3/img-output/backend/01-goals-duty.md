# 图片生成模块 - Goals & Duties

## Design Goals

1. Agent 能够根据用户指令调用图片生成能力，生成结果以结构化事件传递给前端，而非嵌入文本流。

2. 图片生成服务与用户当前选择的 LLM provider 保持一致，使用同一份 API 配置，无需额外配置图片服务密钥。

3. 生成的图片持久化存储，按会话组织，随会话或 Notebook 删除自动清理，不留孤儿文件。

4. 工具实现不侵入 AgentLoop 的控制逻辑，通过已有扩展点接入，保持 AgentLoop 对具体工具类型无感知。

## Duties

- 封装 Zhipu（GLM-Image）和 Qwen（qwen-image-2.0-pro）的图片生成 HTTP 调用，对上层暴露统一的工具接口。

- 根据当前请求的 LLM provider，在运行时构建并注册对应的图片生成工具。

- 工具执行时，将 provider 返回的临时图片 URL 下载并持久化到 MinIO，同时在 PostgreSQL 中写入生成记录（session_id、prompt、storage_key 等元数据）。

- 工具执行成功后，将图片元数据作为 `ToolCallResult` 的结构化字段（`images`）返回，AgentLoop 检测后向 SSE 流推送 `ImageGeneratedEvent`。

- 提供 HTTP 端点供前端按 image_id 获取图片元数据与字节流（渲染与下载），以及按 session_id 列出会话内全部生成图片。

- 在 Session 或 Notebook 删除时，由应用层负责先删除对应的 MinIO 文件，再依赖数据库 CASCADE 清理 generated_images 记录。

## Non-Duties

- 不负责前端渲染：图片卡片样式、下载按钮交互由前端模块实现，本模块仅输出 event 和 HTTP 端点。

- 不负责提示词优化：prompt 由 LLM 根据用户意图决策并传入工具，本模块不做改写或增强。

- 不负责内容安全审核：图片内容合规由 provider 自身处理，本模块不做二次过滤。

- 不提供图片编辑能力：当前版本仅支持文生图，图片编辑作为后续扩展项，不在本模块职责范围内。

- 不管理并发与限流：provider 的调用频率限制由 provider 自身返回错误，本模块将错误透传至 LLM 响应，不做重试或队列管理。如未来需要限流，应在应用层或中间件层实现，而非工具层。

- 不负责图片格式转换：存储和输出均使用 provider 返回的原始格式（PNG）。