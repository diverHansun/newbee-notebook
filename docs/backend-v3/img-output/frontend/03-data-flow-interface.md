# 图片生成模块（前端） - Data Flow & Interface

## Context & Scope

本模块在前端数据流中的位置：

- 上游数据源：后端 SSE 流（`image_generated` 事件）和历史消息 API（消息 `images` 字段）
- 上游交互：用户点击图片（放大）、点击下载按钮
- 下游 API：`GET /api/generated-images/{imageId}/data`（图片字节流）、`GET /api/generated-images/{imageId}/data?download=1`（下载）
- 并行组件：`DocumentReferencesCard`、`ConfirmationCard`，图片卡片与它们平级

本文档范围：从前端接收到 `image_generated` SSE 事件，到图片卡片可交互渲染的完整数据流，以及历史消息恢复流。

## Data Flow Description

### 主流程：SSE 实时图片生成

1. 用户发送消息，进入 AgentLoop 流式处理。

2. AgentLoop 工具执行完成后，后端发送 `image_generated` SSE 事件：

   ```json
   {
     "type": "image_generated",
     "images": [
       {
         "image_id": "uuid-1",
         "storage_key": "generated-images/nb123/sess456/uuid-1.png",
         "prompt": "a cat sitting on a windowsill",
         "provider": "zhipu",
         "model": "glm-image",
         "width": 1280,
         "height": 1280
       }
     ],
     "tool_call_id": "call_abc123",
     "tool_name": "image_generate"
   }
   ```

3. `useChatSession` 的 `sendMessage()` 事件分发中，识别 `event.type === "image_generated"`，调用 `addImagesToMessage(sessionId, activeAssistantId, event.images)`。

4. `addImagesToMessage` 在 chat-store 中找到目标 assistant 消息，将 `event.images` 追加到 `message.images` 数组（通过 `imageId` 去重，避免重复追加）。

5. React 响应状态更新，`MessageItem` 检测到 `message.images` 非空，渲染 `ImageCardList`。

6. `ImageCardList` 遍历 `images`，为每张图片渲染 `ImageCard`：
   - `<img src="/api/generated-images/{imageId}/data">` 指向后端 API
   - 浏览器自动发起请求，后端返回图片字节流（带 `Cache-Control: immutable` + `ETag`）
   - 图片加载前显示骨架屏（比例由 `width/height` 决定）
   - 图片加载后切换到正常显示

7. 用户交互：
   - 点击图片 → 打开 `ImageLightbox` 全屏查看
   - 点击下载按钮 → 浏览器下载 `/api/generated-images/{imageId}/data?download=1`

### 恢复流程：历史消息图片加载

1. 用户切换到已有会话，前端调用消息列表 API 获取历史消息。

2. 后端消息 API 返回的 assistant 消息包含 `images` 字段：

   ```json
   {
     "id": 42,
     "role": "assistant",
     "content": "我为你生成了一张图片...",
     "images": [
       {
         "image_id": "uuid-1",
         "storage_key": "generated-images/nb123/sess456/uuid-1.png",
         "prompt": "a cat sitting on a windowsill",
         "provider": "zhipu",
         "model": "glm-image",
         "width": 1280,
         "height": 1280
       }
     ]
   }
   ```

3. 前端将 `images` 映射为 `ChatImage[]` 格式，存入 `ChatMessage.images`。

4. `MessageItem` 渲染时，与实时场景相同的 `ImageCardList` 渲染逻辑生效。

5. 图片 `<img src>` 指向同一后端 API，浏览器通过 ETag 验证缓存，命中则不重新下载。

### 错误路径

- **图片加载失败**（网络错误、后端不可用）：`ImageCard` 的 `<img onError>` 触发，显示灰色占位块 + "图片加载失败" + "重试" 按钮。点击重试重新设置 `src`（加时间戳参数破缓存）。

- **SSE 事件丢失**（网络中断等）：图片元数据仅在 SSE 事件中传递。如果事件丢失，流结束后消息中没有图片。用户刷新页面或切换会话时，从消息 API 获取的 `images` 字段会补全历史数据。

## Interface Definition

### SSE 事件定义

**`image_generated` 事件**

| 字段 | 类型 | 含义 |
|---|---|---|
| type | "image_generated" | 事件类型标识 |
| images | ChatImageSse[] | 生成的图片列表 |
| tool_call_id | string | 关联的工具调用 ID |
| tool_name | string | 工具名称（"image_generate"） |

**`ChatImageSse`（SSE 中的图片数据）**

| 字段 | 类型 | 含义 |
|---|---|---|
| image_id | string | 图片 UUID |
| storage_key | string | MinIO 对象键（前端不直接使用，调试用） |
| prompt | string | Agent 优化后的绘图描述 |
| provider | string | 生成服务提供方（zhipu / qwen） |
| model | string | 模型名称 |
| width | number \| null | 实际输出宽度像素 |
| height | number \| null | 实际输出高度像素 |

### 前端内部数据类型

**`ChatImage`（存储在 ChatMessage 中）**

| 字段 | 类型 | 含义 |
|---|---|---|
| imageId | string | 图片 UUID |
| storageKey | string | MinIO 对象键 |
| prompt | string | Agent 优化后的绘图描述 |
| provider | string | 生成服务提供方 |
| model | string | 模型名称 |
| width | number \| null | 宽度 |
| height | number \| null | 高度 |

SSE 事件的 `snake_case` 字段名在追加到 `ChatMessage.images` 时转换为 `camelCase`。

### 后端 API 端点（前端消费）

| 端点 | 用途 | 前端使用方式 |
|---|---|---|
| `GET /api/generated-images/{imageId}/data` | 返回图片字节流 | `<img src>` 直接引用，浏览器自动处理缓存 |
| `GET /api/generated-images/{imageId}/data?download=1` | 下载图片 | `<a href download` 链接 |

前端不需要调用 `GET /api/generated-images/{imageId}`（元数据）端点，因为元数据已通过 SSE 事件或消息 API 获取。

### Chat Store 接口变更

**`ChatMessage` 类型新增**

```typescript
images?: ChatImage[]
```

**新增 action**

```typescript
addImagesToMessage(sessionId: string, messageId: string | number, images: ChatImage[]): void
```

实现逻辑：
1. 在 `sessions[sessionId].messages` 中找到 `id === messageId` 的消息
2. 合并 `images`（通过 `imageId` 去重）
3. 触发 Zustand 状态更新

### useChatSession 事件处理新增

在 `sendMessage()` 的事件分发 switch/case 中新增：

```typescript
if (event.type === "image_generated") {
  if (activeAssistantIdRef.current) {
    addImagesToMessage(sessionId, activeAssistantIdRef.current, event.images)
  }
  return
}
```

## Data Ownership & Responsibility

| 数据 | 来源 | 持久化 | 销毁 |
|---|---|---|---|
| ChatMessage.images | SSE 事件 / 消息 API | 内存（Zustand store），页面刷新后从 API 恢复 | 随会话切换自然清除 |
| ImageCard 渲染状态（loading/loaded/error） | 组件内部 state | 不持久化 | 组件卸载时清除 |
| 图片字节流 | 后端 `/data` API | 浏览器缓存（Cache-Control + ETag） | 浏览器缓存策略管理 |
| ImageLightbox 状态 | 组件内部 state | 不持久化 | 关闭时清除 |

## File Changes Summary

### 新增文件

| 文件 | 用途 |
|---|---|
| `frontend/src/components/chat/image-card.tsx` | 单张图片卡片组件 |
| `frontend/src/components/chat/image-card-list.tsx` | 图片列表容器 |
| `frontend/src/components/chat/image-lightbox.tsx` | 全屏放大浮层 |
| `frontend/src/styles/image-card.css` | 卡片和 lightbox 样式 |
| `frontend/src/lib/api/generated-images.ts` | 图片 API URL 工具函数 |

### 修改文件

| 文件 | 改动 |
|---|---|
| `frontend/src/lib/api/types.ts` | 新增 `SseEventImageGenerated` 类型、`ChatImage` 类型 |
| `frontend/src/stores/chat-store.ts` | `ChatMessage` 新增 `images` 字段；新增 `addImagesToMessage` action |
| `frontend/src/lib/hooks/useChatSession.ts` | `sendMessage` 事件分发中新增 `image_generated` 处理 |
| `frontend/src/components/chat/message-item.tsx` | assistant 消息渲染区域新增 `ImageCardList` 渲染块 |
| `frontend/src/styles/globals.css` | `@import "./image-card.css"` |

### 不改动的文件

- Next.js 配置、路由、核心框架
- SSE 解析器（`sse-parser.ts`）—— 只负责解析 JSON，不关心事件类型
- Markdown 渲染管线
- 主题系统
- 现有组件（SourcesCard、ConfirmationCard、ExplainCard 等）