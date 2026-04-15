# 图片生成模块 - Architecture

## Architecture Overview

本模块横跨 core/tools 层、core/engine 层、domain 层、infrastructure 层和 API 层，各层各司其职。

**Provider API 层**（`zhipu_image.py`、`qwen_image.py`）

各自封装单一 provider 的异步 HTTP 调用，统一返回 `ImageAPIResult`（临时图片 URL、实际尺寸、模型名）。两个模块职责完全对称，互不依赖。

**工具构建层**（`image_tool.py`）

接受 `ImageToolContext`（运行时依赖上下文），构建完整的 `ToolDefinition`（含 `execute` 函数）。内部根据 provider 路由至对应的 Provider API 层。`execute` 负责端到端执行：API 调用、下载、存储、持久化，最终返回 `ToolCallResult`，其中 `images` 字段携带结构化图片元数据。

**AgentLoop 扩展点**（`agent_loop.py`、`stream_events.py`）

`AgentLoop` 在每次工具执行后，若 `ToolCallResult.images` 非空，则构造 `ImageGeneratedEvent` 并 yield。AgentLoop 不知道图片工具的存在，仅检查 `ToolCallResult` 上的结构化字段——与检查 `sources` 字段的模式一致。`ImageGeneratedEvent` 定义在 `stream_events.py` 中，与其他流事件平级。

**领域层**（`domain/entities/generated_image.py`、`domain/repositories/generated_image_repository.py`）

定义 `GeneratedImage` 实体与仓储接口，描述领域概念和生命周期，不依赖任何基础设施实现。

**基础设施层**（`infrastructure/persistence/models.py`、`repositories/generated_image_repo_impl.py`）

ORM 映射、SQL 迁移脚本（`batch7_generated_images.sql`）、仓储实现。MinIO 存储键管理复用已有 `StorageBackend` 接口。

**应用层**（`application/services/generated_image_service.py`，以及对 `session_service.py`、`notebook_service.py` 的改动）

提供图片查询接口，构造注入给工具层的 `save_record` 回调（闭包捕获请求级 db_session）。在 Session/Notebook 删除逻辑中扩展 MinIO 文件清理步骤。

**API 层**（新增路由）

`GET /api/generated-images/{image_id}`：返回图片 JSON 元数据。
`GET /api/generated-images/{image_id}/data`：从 MinIO 读取并返回图片字节流（带 Cache-Control 和 ETag）。
`GET /api/sessions/{session_id}/generated-images`：列出会话内生成图片的元数据列表。

## Design Pattern & Rationale

**依赖注入（ImageToolContext）**

工具层不持有任何全局状态，所有运行时依赖（api_key、session_id、storage、save_record）通过 `ImageToolContext` 在请求入口处注入。这使工具函数可以在测试中被完整替换任意依赖，无需 mock 环境变量或单例。

`ImageToolContext` 定义在 `image_tool.py` 中，打包执行一次图片生成所需的全部依赖：provider 标识、API Key、session_id、notebook_id、storage 后端引用、DB 写入回调。随请求生命周期存在，通过闭包捕获传入 `execute` 函数。它是工具构建层的内部实现细节，不是领域概念。

**策略模式（通过闭包实现）**

`build_image_generation_tool` 在构建时根据 provider 选择 API 调用函数，并将其捕获在 `execute` 闭包中。调用方无需关心 provider 差异，切换 provider 只需重新构建工具。

**ToolCallResult 扩展字段（而非 event_emitter 回调）**

图片生成结果通过 `ToolCallResult` 上的 `images: list[ImageResult]` 字段传递，AgentLoop 像检查 `sources` 一样检查 `images`，非空时构造并 yield `ImageGeneratedEvent`。

选择此方案而非 `event_emitter` 回调的原因：

| 维度 | ToolCallResult.images（选定方案） | event_emitter 回调 |
|---|---|---|
| 复杂度 | 修改 ToolCallResult（加字段）+ AgentLoop（检查字段并 yield），改动点集中 | 修改 ToolDefinition（加回调字段）+ AgentLoop（检测并调用回调），需维护闭包生命周期 |
| 类型安全 | `list[ImageResult]` 类型明确，IDE 可推断 | 回调签名为 `Callable[[ToolCallResult], Optional[Event]]`，闭包内部逻辑不可静态检查 |
| 可测试性 | 构造 ToolCallResult 后直接断言 images 字段 | 需构造完整 ToolDefinition 并模拟闭包调用 |
| 数据完整性 | 工具调用的全部结果统一在 ToolCallResult 中 | 结果裂分为两条路径：content/sources 走 ToolResultEvent，image 走 event_emitter |
| 可审计性 | `result.images` 可直接打印、序列化、日志 | 闭包内部逻辑不可见，需断点追踪 |
| 扩展性 | 每新增媒体类型需加字段和映射，显式可控 | 任意工具可产出自定义事件，无约束扩展 |
| 当前需求 | 仅有图片生成需要 | 仅有图片生成需要 |

核心权衡：牺牲了 event_emitter 的无约束扩展性，换取了更高的类型安全、可测试性和可审计性。当前仅图片一种媒体类型，YAGNI 原则适用。若未来出现图表、音频等媒体类型，在 ToolCallResult 上逐个加字段（`diagrams`、`audio`）是显式、可控的增长方式，每次扩展都有明确的接口契约。如果某天确实出现"一个工具需要产出多种语义不同事件"的场景，再引入 event_emitter 也不迟。

**外部工具注入（external_tools）**

图片工具通过 `ToolRegistry.get_tools(external_tools=[...])` 注入，而非修改 `BuiltinToolProvider`。`BuiltinToolProvider` 是单例，不适合携带请求级状态（session_id）；`external_tools` 机制天然支持请求级构建，仅对 agent 和 ask 模式开放。

## Module Structure & File Layout

```
core/
  engine/
    stream_events.py          # 新增 ImageGeneratedEvent（与现有事件平级）
    agent_loop.py             # 新增 images 字段检测 + ImageGeneratedEvent 构造点（两处工具执行循环）
  tools/
    contracts.py              # ToolCallResult 新增 images 字段；新增 ImageResult 数据类
    image_tool.py             # ImageToolContext + build_image_generation_tool
    zhipu_image.py            # Zhipu GLM-Image 异步 HTTP 调用
    qwen_image.py             # Qwen qwen-image-2.0-pro 异步 HTTP 调用

domain/
  entities/
    generated_image.py        # GeneratedImage 实体
  repositories/
    generated_image_repository.py  # 仓储接口

infrastructure/
  persistence/
    models.py                 # GeneratedImageModel ORM 追加
    repositories/
      generated_image_repo_impl.py
  scripts/db/migrations/
    batch7_generated_images.sql

application/
  services/
    generated_image_service.py   # 查询服务 + save_record 工厂 + message_id 回填
    session_service.py           # 扩展 delete 逻辑（MinIO 清理）
    notebook_service.py          # 扩展 delete 逻辑（MinIO 清理）

api/
  routes/
    generated_images.py          # GET /api/generated-images/{id} 等端点
```

对外稳定接口：`ToolCallResult.images` 和 `ImageResult`（contracts.py）、`ImageGeneratedEvent`（stream_events.py）、HTTP 端点路径。
内部实现：`zhipu_image.py`、`qwen_image.py`、`image_tool.py` 内部细节可自由调整。

## Architectural Constraints & Trade-offs

**tools 层不依赖 engine/stream_events.py**

`image_tool.py` 使用 `ImageResult` 数据类（定义在 contracts.py），不直接依赖 `stream_events.py`。`ImageGeneratedEvent` 的构造发生在 AgentLoop 中（检测 `result.images` 后构造），而非工具层。因此 tools 层不对 engine 层产生新依赖——`ImageResult` 定义在 tools/contracts.py 中，`ImageGeneratedEvent` 定义在 engine/stream_events.py 中，依赖方向合理。

**同步执行，不使用后台任务**

图片生成（API 调用 + 下载 + 存储）在工具 `execute` 函数内顺序完成，不交给 Celery 或后台任务。代价是单次工具调用耗时较长（15-40s），但换来错误处理简单：若任意步骤失败，工具直接返回 error，LLM 可向用户报告失败，无需额外的任务状态管理。

**前端统一通过后端 API 获取图片**

图片字节流通过后端 API 代理返回，不直接暴露 MinIO 地址或返回预签名 URL。理由：(1) 访问控制——后端可校验请求者是否有权访问该图片；(2) 部署安全——MinIO 可能部署在内网；(3) 一致性——项目中现有文档也通过后端代理获取。代价是每张图片的首次浏览经过 Python 后端，但图片生成后内容不变，后端会设置 `Cache-Control: public, max-age=31536000, immutable` + `ETag` 响应头，浏览器和 CDN 会缓存，后续请求不穿透后端。

**放弃的方案：修改 BuiltinToolProvider 接受请求级参数**

若将 session_id、api_key 等加入 `BuiltinToolProvider` 构造函数，则需要将单例改为每请求实例化，影响范围大、测试成本高。external_tools 注入方案代价更小。

**放弃的方案：event_emitter 回调机制**

详见 Design Pattern & Rationale 章节。选择 ToolCallResult.images 扩展字段方案替代。