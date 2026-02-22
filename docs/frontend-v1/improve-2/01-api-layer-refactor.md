# P1: API 层统一化重构

## 1. 当前问题

### 背景：项目 API 层架构

前端 API 调用分为两个层次：

**lib/api/client.ts — 统一 HTTP 客户端**

提供 `apiFetch<T>(path, options)` 函数，负责：
- 自动拼接 `/api/v1` 前缀
- 统一序列化请求体（普通对象自动 JSON 序列化；FormData、Blob 等直接透传）
- 统一解析错误响应，转换为 `ApiError` 实例（兼容后端多种错误格式：`error_code/message`、`detail` 字符串、`detail` 对象）
- 处理 204 No Content 响应

**lib/api/\*.ts — 各业务模块封装**

通过调用 `apiFetch` 提供类型安全的业务函数。所有模块（`documents.ts`、`library.ts`、`notebooks.ts`、`sessions.ts`）均遵循此规范。

### 问题描述

`lib/api/chat.ts` 未使用 `apiFetch`，而是直接调用原生 `fetch()`，并在三个函数中各自手动实现错误处理：

```
chatOnce()         — 第 11 行：fetch(`/api/v1/chat/...`)，第 19-31 行：手动错误解析
chatStream()       — 第 42 行：fetch(`/api/v1/chat/...`)，第 52-64 行：手动错误解析
cancelChatStream() — 第 78 行：fetch(`/api/v1/chat/...`)，无错误处理
```

**具体问题点：**

1. **错误处理逻辑重复**：`chatOnce` 和 `chatStream` 中各有一段 `try/catch` 手动构造 `ApiError`，与 `client.ts` 中的 `buildError()` 逻辑高度重合，但不完全一致。`chat.ts` 中的实现不能处理后端返回 `detail` 对象格式的错误，只处理了 `error_code/message` 和 `detail` 字符串两种情况（`client.ts` 额外处理了 `detail` 为对象的情况）。

2. **URL 构造分散**：`chat.ts` 中硬编码 `/api/v1/...` 前缀，当基础路径需要调整时，`client.ts` 和 `chat.ts` 需要同步修改。

3. **`cancelChatStream` 无错误处理**：直接返回原始 `Response`，调用方无法依赖统一的 `ApiError` 类型，与其他模块行为不一致。

4. **例外：`chatStream` 的流式响应不能使用 `apiFetch`**：`apiFetch` 在响应成功后立即调用 `response.json()` 或 `response.text()`，会消费掉 `response.body`，无法用于 SSE 流式场景。因此 `chatStream` 的主体逻辑需要保留原生 `fetch`，但其错误处理部分应复用统一逻辑。

### 影响评估

- 现阶段对用户无直接可见影响（功能层面可正常运行）
- 当后端新增错误格式时，`chat.ts` 中的错误解析会静默失效，导致前端显示不准确的错误信息
- 增加维护成本：修改错误处理规范时需要同步修改多处

---

## 2. 解决方案

### 原则

- `chatOnce` 和 `cancelChatStream` 完全切换为 `apiFetch`，移除手动错误处理
- `chatStream` 保留原生 `fetch`（因需要访问 `response.body` 流），但将错误处理提取为局部辅助函数，消除内联重复代码
- 不修改任何调用方代码（`useChatStream.ts` 等），保持函数签名不变

### chatOnce — 切换至 apiFetch

当前问题：手动 `fetch` + 手动 `ApiError` 构造（第 11-34 行）

修改方式：

```typescript
// 修改前（chat.ts 第 10-35 行）
export async function chatOnce(notebookId: string, request: ChatRequest) {
  const response = await fetch(`/api/v1/chat/notebooks/${notebookId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    // 手动错误解析，共 10 行
    ...
  }
  return (await response.json()) as ChatResponse;
}

// 修改后
export function chatOnce(notebookId: string, request: ChatRequest) {
  return apiFetch<ChatResponse>(`/chat/notebooks/${notebookId}/chat`, {
    method: "POST",
    body: request,  // apiFetch 自动 JSON 序列化普通对象
  });
}
```

### chatStream — 保留原生 fetch，提取错误处理

`chatStream` 必须访问 `response.body`（ReadableStream），`apiFetch` 不支持此场景。
但其错误处理代码（第 52-64 行）与 `chatOnce` 内的错误处理几乎相同，属于重复代码。

修改方式：仅提取错误解析为内部辅助函数，主体逻辑不变：

```typescript
// 文件顶部新增内部辅助函数（不导出）
async function throwIfNotOk(response: Response, fallbackCode: string): Promise<void> {
  if (response.ok) return;
  let errorPayload: ApiErrorPayload | null = null;
  try {
    errorPayload = await response.json();
  } catch {
    errorPayload = null;
  }
  throw buildError(response.status, errorPayload, fallbackCode);
}
```

但注意：`buildError` 是 `client.ts` 中的非导出内部函数。有两种处理方式：

**方案 A（推荐）**：从 `client.ts` 导出 `buildError`，供 `chat.ts` 复用。
**方案 B**：在 `chat.ts` 中写一个简化版本，承认这是 stream 场景的特例。

推荐方案 A，因为 `buildError` 本身是纯函数，导出不产生副作用，且可以保证错误解析逻辑统一。

修改 `chatStream` 为：
```typescript
export async function chatStream(...): Promise<void> {
  const response = await fetch(`/api/v1/chat/notebooks/${notebookId}/chat/stream`, { ... });
  await throwIfNotOk(response, "E_CHAT_STREAM");
  if (!response.body) {
    throw new ApiError(500, "E_STREAM_BODY", "Stream body is empty");
  }
  await parseSseStream(response.body, { ... });
}
```

### cancelChatStream — 切换至 apiFetch

当前：返回原始 `Response`，无错误处理。

修改后：
```typescript
export function cancelChatStream(messageId: number) {
  return apiFetch<void>(`/chat/stream/${messageId}/cancel`, { method: "POST" });
}
```

---

## 3. 架构影响与修改点

### 修改文件

**`frontend/src/lib/api/client.ts`**
- 导出 `buildError` 函数（当前为模块内私有）
- 无逻辑变更，仅可见性变化

**`frontend/src/lib/api/chat.ts`**
- 新增 import：`apiFetch` 来自 `./client`，`ApiErrorPayload` 类型来自 `./types`
- 删除：`chatOnce` 中的手动 fetch 和错误处理（约 20 行）
- 删除：`chatStream` 中的手动错误处理（约 12 行）
- 新增：内部辅助函数 `throwIfNotOk`（约 10 行）
- 修改：`cancelChatStream` 改用 `apiFetch`

### 非修改文件

- `lib/hooks/useChatStream.ts`：调用方，函数签名不变，无需修改
- `lib/api/types.ts`：类型定义，无变更
- 所有组件层：无变更

### 净变化

删除约 30 行重复的错误处理代码，新增约 10 行共享辅助逻辑，总体减少约 20 行代码量。
`client.ts` 新增 1 行导出语句。

### 风险

- **低风险**：`chatOnce` 和 `cancelChatStream` 的改动是等价替换，`apiFetch` 的错误解析能力是 `chat.ts` 原有逻辑的超集
- **注意**：`apiFetch` 对 204 状态码返回 `undefined`，`cancelChatStream` 调用方需确认能处理 `void` 返回值（当前调用方通常忽略返回值，无影响）
