# 图片生成模块 - Data Model

## Core Concepts

**GeneratedImage**

一次图片生成操作的完整记录。有唯一身份（UUID），有明确的生命周期（随 Session 或 Notebook 删除而销毁）。它是本模块唯一需要持久化的领域概念。

**ImageAPIResult**（不持久化）

Provider API 调用的直接返回值：临时图片 URL（有效期通常为 24 小时内）、实际输出尺寸、模型名。仅在工具执行期间使用，图片下载完成后即丢弃，不持久化。

**ImageResult**（不持久化）

工具执行完成后，通过 `ToolCallResult.images` 传递给 AgentLoop 的结构化图片信息。包含 image_id、storage_key、尺寸、prompt、provider 等元数据。在 AgentLoop 中被提取并用于构造 `ImageGeneratedEvent`，随后随 SSE 流推送至前端。

**ImageGeneratedEvent**（不持久化）

AgentLoop 检测到 `ToolCallResult.images` 非空时构造的流事件，通过 SSE 推送至前端。携带 image_id、storage_key、尺寸、prompt、provider、tool_call_id 等字段。定义在 `stream_events.py` 中，与其他流事件平级。

## Key Data Fields

**GeneratedImage 关键字段**

| 字段 | 含义 |
|---|---|
| id | 图片记录的唯一标识，同时用于构建前端访问路径 |
| session_id | 所属会话，决定图片的生命周期归属，外键级联删除 |
| notebook_id | 所属 Notebook，用于批量清理场景的前缀删除 |
| message_id | 关联的 assistant 消息 ID（nullable，流结束后回填）。用于前端定位图片在对话中的位置。工具执行时此字段为 NULL，assistant 最终回复持久化后由应用层回填 |
| tool_call_id | AgentLoop 中工具调用的唯一标识，用于前端关联 ToolCallEvent、ToolResultEvent 和 ImageGeneratedEvent |
| prompt | 生成时传入的文字描述，用于前端展示和记录溯源 |
| provider | 生成服务提供方（zhipu / qwen），用于调试和统计 |
| model | 具体模型名称，同一 provider 可能有多个模型 |
| size | 原始尺寸字符串（如 "1280x1280"），保留 LLM 请求和 Provider API 的原始格式 |
| width | 实际输出宽度像素值，由 provider 返回，可能与请求值有偏差 |
| height | 实际输出高度像素值，由 provider 返回，可能与请求值有偏差 |
| storage_key | MinIO 中的对象键，是图片二进制数据的唯一定位符 |
| file_size | 图片字节大小，用于存储占用统计 |

storage_key 格式约定：`generated-images/{notebook_id}/{session_id}/{image_id}.png`

前缀使用 `generated-images/` 而非 `images/`，为后续用户上传图片（`uploaded-images/`）、用户修改图片（`edited-images/`）等场景预留命名空间，避免键名冲突。

**ImageResult 关键字段**

| 字段 | 含义 |
|---|---|
| image_id | GeneratedImage 的 UUID |
| storage_key | 同 GeneratedImage.storage_key |
| prompt | 生成时传入的文字描述 |
| provider | 生成服务提供方 |
| model | 具体模型名称 |
| width | 实际输出宽度 |
| height | 实际输出高度 |

**ImageGeneratedEvent 关键字段**

| 字段 | 含义 |
|---|---|
| images | list[ImageResult]，可能包含多张图片 |
| tool_call_id | 关联的工具调用 ID |
| tool_name | 工具名称（"image_generate"） |

## Entity / Value Object 区分

| 概念 | 类型 | 理由 |
|---|---|---|
| GeneratedImage | Entity | 有唯一标识、有生命周期（创建→读取→级联删除） |
| ImageAPIResult | Value Object | 不可变、无身份、短期使用即丢弃 |
| ImageResult | Value Object | 不可变、无身份、用于事件传递 |
| ImageGeneratedEvent | Value Object | 不可变、无身份、单次流事件 |

## Lifecycle & Ownership

**GeneratedImage 创建**

工具 `execute` 函数在图片成功写入 MinIO 后，通过注入的 `save_record` 回调写入数据库。创建权在工具层，但实际执行通过回调委托给应用层（持有 db_session）。

`message_id` 在创建时为 NULL。流结束后（assistant 最终回复消息持久化后），由应用层通过 `GeneratedImageService.backfill_message_id(image_id, message_id)` 回填。

**读取**

前端通过两种路径获取图片数据：
1. 实时场景：SSE 流中的 `ImageGeneratedEvent` 携带 image_id，前端据此渲染图片卡片
2. 持久化场景：HTTP 端点按 image_id 获取图片字节流或元数据，按 session_id 列出全部图片

读取权在应用层 API。

**销毁**

Session 或 Notebook 删除时，应用层（SessionService / NotebookService）负责：先调用 StorageBackend 删除 MinIO 文件（Session 级按 storage_key 逐个删除，Notebook 级按前缀 `generated-images/{notebook_id}/` 批量删除），再执行数据库删除（数据库 CASCADE 自动清理 generated_images 行）。MinIO 文件的删除责任在应用层，不依赖数据库触发器。

**ImageAPIResult** 无需管理生命周期，仅存活于工具 execute 函数的调用栈内。临时 URL 在图片下载完成后不再使用。

**ImageResult / ImageGeneratedEvent** 无需持久化，随 SSE 流发送后即被消费，不存储。