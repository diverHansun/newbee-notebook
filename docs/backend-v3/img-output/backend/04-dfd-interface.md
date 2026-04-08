# 图片生成模块 - Data Flow & Interface

## Context & Scope

本模块在请求处理链路中的位置：

- 上游（构建阶段）：应用层请求处理，负责构造 `ImageToolContext`，将图片工具注入 `ToolRegistry`
- 上游（执行阶段）：`AgentLoop`，负责触发工具调用、检测 `ToolCallResult.images`、构造并 yield `ImageGeneratedEvent`
- 外部依赖：Zhipu / Qwen 图片生成 HTTP API（异步调用，有网络延迟）
- 下游存储：MinIO（图片二进制）、PostgreSQL（generated_images 元数据）
- 下游消费：前端通过 SSE 流接收 `ImageGeneratedEvent`，再通过 HTTP 端点获取图片字节流

本文档范围：从用户消息到达至图片卡片可渲染的完整数据流，以及会话删除时的清理流。

本文档仅涉及 agent 和 ask 两种模式，不涉及 chat 模式。

## Data Flow Description

### 主流程：图片生成

1. 应用层从数据库读取当前 LLM provider（zhipu 或 qwen）及对应 API Key（从环境变量解析），读取当前 session_id 和 notebook_id。

2. 应用层构造 `ImageToolContext`，其中 `save_record` 是一个闭包，捕获当前请求的 `db_session`，调用时向 `generated_images` 表写入一条记录。

3. 应用层调用 `build_image_generation_tool(ctx)` 获得 `ToolDefinition`，作为 `external_tools` 传入 `ToolRegistry.get_tools(mode, external_tools=[image_tool])`，合并进 AgentLoop 的工具集合。此步骤仅在 agent 和 ask 模式下执行。

4. 用户消息进入 AgentLoop，LLM 推理阶段决策调用 `image_generate` 工具，产出参数 `{prompt: str, size?: str}`。`size` 格式为字符串（如 `"1280x1280"`），由各 Provider 层自行转换为 API 要求的格式（Zhipu 使用 `x` 分隔，Qwen 使用 `*` 分隔）。默认值由 Provider 层定义（Zhipu: `"1280x1280"`，Qwen: `"1024*1024"`）。

5. AgentLoop 调用 `tool.execute({prompt, size})`，进入工具执行阶段：

   a. 按 provider 路由：调用 `zhipu_generate_image` 或 `qwen_generate_image`，通过异步 HTTP 客户端发起请求，返回 `ImageAPIResult`（临时图片 URL、实际尺寸、模型名）。

   b. 通过异步 HTTP 客户端下载临时 URL 的图片字节。

   c. 生成 image_id（UUID），构造 storage_key：`generated-images/{notebook_id}/{session_id}/{image_id}.png`，调用 `StorageBackend.save_file(key, bytes, "image/png")`，图片持久化到 MinIO。

   d. 调用注入的 `save_record(image_id, session_id, notebook_id, prompt, provider, model, size, width, height, file_size, storage_key)`，经由闭包将记录写入 PostgreSQL `generated_images` 表。`message_id` 此时为 NULL。

   e. 返回 `ToolCallResult(content="图片已生成。描述: {prompt}", images=[ImageResult(image_id=..., storage_key=..., prompt=..., provider=..., model=..., width=..., height=...)])`。

6. AgentLoop 收到 `ToolCallResult` 后：

   a. yield `ToolResultEvent`（已有逻辑，content_preview 推送至前端）。

   b. 检测 `result.images` 非空，构造 `ImageGeneratedEvent(images=result.images, tool_call_id=..., tool_name="image_generate")` 并 yield，通过 SSE 推送至前端。

   c. 将 `ToolCallResult.content`（文字确认）加入 messages，LLM 继续推理，生成面向用户的文字回复。

7. 流结束后，assistant 最终回复消息被持久化到 `messages` 表，获得 `message_id`。应用层调用 `GeneratedImageService.backfill_message_id(image_id, message_id)`，将 `message_id` 写入对应的 `generated_images` 记录。

8. 前端收到 `ImageGeneratedEvent` 后，渲染图片卡片，卡片内图片元素的 src 指向 `GET /api/generated-images/{image_id}/data`。

9. 前端图片请求到达后端 API：从 PostgreSQL 查询 `generated_images` 记录获取 storage_key，调用 `StorageBackend.get_file(storage_key)` 从 MinIO 读取字节流，以 `image/png` Content-Type 返回，并附带 `Cache-Control: public, max-age=31536000, immutable` 和 `ETag` 响应头。

### 清理流程：Session 删除

1. 应用层收到 Session 删除请求。

2. `SessionService.delete` 调用 `GeneratedImageRepository.list_by_session(session_id)` 查出该 session 下全部图片记录，取出各自的 storage_key。

3. 对每个 storage_key 调用 `StorageBackend.delete_file(key)`，删除 MinIO 文件。

4. 执行 Session 的数据库删除，数据库 CASCADE 自动删除关联的 generated_images 行。

Notebook 删除时，逻辑相同，前缀为 `generated-images/{notebook_id}/`，可用 `StorageBackend.delete_prefix` 批量删除。

### 错误路径

- **Provider API 调用失败**（超时、Key 无效、内容拒绝）：工具返回 `ToolCallResult(error=...)`，AgentLoop 不构造 `ImageGeneratedEvent`，LLM 向用户说明失败原因。

- **MinIO 写入失败**：工具返回 error，不调用 `save_record`，不产生孤儿数据库记录。Provider API 已消耗调用配额但图片未持久化，属于可接受的损失。

- **DB 写入失败**（save_record 回调抛出异常）：MinIO 文件已写入但记录未创建，形成孤儿文件。工具捕获异常并返回 error。该情况概率低，可通过定期存储清理任务处理，不在本模块职责范围内做事务补偿。

- **message_id 回填失败**：`generated_images` 记录已创建，但流结束后回填 `message_id` 失败。图片仍可通过 session_id 关联查询，不影响核心功能。可由定期补偿任务修复。

- **Provider 返回多张图片**：当前 Zhipu 和 Qwen MVP 均只请求单张，但 `images` 字段为 list 设计，支持未来扩展。若 Provider 返回多张，工具逐张下载、存储、写入记录，全部图片放入 `ToolCallResult.images` 列表。

## Interface Definition

**工具层对外暴露（通过 ToolDefinition）**

| 接口 | 输入 | 输出 | 性质 |
|---|---|---|---|
| `tool.execute` | `{prompt: str, size?: str}` | `ToolCallResult`（含 `images: list[ImageResult]`） | 异步，耗时 15-40s |

`size` 参数为字符串格式（如 `"1280x1280"`），由各 Provider 层自行转换为 API 要求的格式。LLM 生成单个字符串比生成两个独立整数更自然。Zhipu API 使用 `x` 分隔（`"1280x1280"`），Qwen API 使用 `*` 分隔（`"1024*1024"`），转换在 Provider API 层完成。

**工具层依赖的上游接口**

| 接口 | 提供方 | 说明 |
|---|---|---|
| `zhipu_generate_image(api_key, prompt, size)` | zhipu_image.py | 异步，返回 ImageAPIResult |
| `qwen_generate_image(api_key, prompt, size)` | qwen_image.py | 异步，返回 ImageAPIResult |
| `StorageBackend.save_file(key, data, content_type)` | infrastructure/storage | 异步，写入 MinIO |
| `StorageBackend.get_file(key)` | infrastructure/storage | 异步，从 MinIO 读取字节流 |
| `StorageBackend.delete_file(key)` | infrastructure/storage | 异步，删除单个 MinIO 对象 |
| `StorageBackend.delete_prefix(prefix)` | infrastructure/storage | 异步，按前缀批量删除 MinIO 对象 |
| `ctx.save_record(**kwargs)` | 注入回调（应用层） | 异步，写入 PostgreSQL |

**HTTP 端点（API 层对外）**

| 端点 | 方法 | 输入 | 输出 | 说明 |
|---|---|---|---|---|
| `/api/generated-images/{image_id}` | GET | path: image_id | JSON 元数据 | 返回 GeneratedImage 全部字段（不含字节流） |
| `/api/generated-images/{image_id}/data` | GET | path: image_id | 图片字节流，Content-Type: image/png，Cache-Control: public, max-age=31536000, immutable | 用于渲染，浏览器/CDN 会缓存 |
| `/api/generated-images/{image_id}/data?download=1` | GET | path: image_id, query: download | 图片字节流，Content-Disposition: attachment | 用于下载 |
| `/api/sessions/{session_id}/generated-images` | GET | path: session_id | JSON 数组 | 列出会话内全部生成图片的元数据 |

**SSE 事件（流式推送）**

| 事件类型 | 字段 | 说明 |
|---|---|---|
| `image_generated` | images: list[ImageResult], tool_call_id: str, tool_name: str | AgentLoop 检测 result.images 后构造，前端收到后渲染图片卡片 |

**ToolCallResult 扩展**

| 字段 | 类型 | 说明 |
|---|---|---|
| `images` | `list[ImageResult]` | 新增字段，默认空列表，向后兼容。图片工具返回时非空 |

**ImageResult 数据类**

| 字段 | 类型 | 说明 |
|---|---|---|
| image_id | str | UUID，GeneratedImage 主键 |
| storage_key | str | MinIO 对象键 |
| prompt | str | 生成时的文字描述 |
| provider | str | "zhipu" 或 "qwen" |
| model | str | 具体模型名 |
| width | int \| None | 实际输出宽度 |
| height | int \| None | 实际输出高度 |

**ImageGeneratedEvent 数据类**

| 字段 | 类型 | 说明 |
|---|---|---|
| images | list[ImageResult] | 生成的图片列表 |
| tool_call_id | str | 关联的工具调用 ID |
| tool_name | str | 工具名称（"image_generate"） |

## Data Ownership & Responsibility

| 数据 | 创建责任 | 销毁责任 | 说明 |
|---|---|---|---|
| MinIO 图片文件 | 工具层（execute 函数内） | 应用层（SessionService / NotebookService delete） | 工具层写入，应用层清理 |
| generated_images 数据库记录 | 工具层（通过 save_record 回调） | 数据库 CASCADE（由应用层触发 Session/Notebook 删除） | DB 记录跟随 Session 生命周期 |
| message_id 回填 | 应用层（流结束后回填） | 不适用 | 后续补偿，失败不影响核心功能 |
| ImageAPIResult 临时 URL | Provider API | 工具层在下载完成后自动丢弃 | 不持久化，仅存活于调用栈 |
| ImageResult | 工具层（execute 函数构造） | AgentLoop 构造 ImageGeneratedEvent 后即不再引用 | 不持久化 |
| ImageGeneratedEvent | AgentLoop（检测 result.images 后构造） | 前端消费后无需清理 | 单次流事件，无持久化 |