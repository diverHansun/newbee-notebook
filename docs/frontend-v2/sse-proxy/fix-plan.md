# Frontend SSE Proxy 修复实施计划

## 1. 修复目标

解决 `frontend/src/app/api/v1/**` 自定义 Next App Route proxy 在开发环境下请求挂起的问题。

核心策略：最小化 custom route 面积，只保留真正需要特殊处理的路由，其余回归 fallback rewrite。

---

## 2. 根因分析

### 2.1 关键证据

| 路由文件 | 使用 signal: request.signal | 是否挂起 |
|---|---|---|
| chat/route.ts | 是 | 是 |
| chat/stream/route.ts | 是 | 是 |
| settings/mcp/servers/route.ts | 是 | 是 |
| settings/route.ts | 是 | 未测试但结构相同 |
| documents/library/upload/route.ts | 否 | 未报告 |

### 2.2 结论

所有挂起的路由都将 `request.signal` 透传给后端 `fetch()`，唯一不用它的 upload 路由没有出问题。

在 Next.js App Router 开发模式下，`request.signal` 的生命周期由 dev server 管理（HMR / turbopack 重编译等），可能导致信号状态异常，使内部 `fetch()` 永远不返回。

---

## 3. 实施步骤

### Phase 1: 删除不必要的 custom route

以下 3 个路由不需要手写 proxy，fallback rewrite 即可胜任：

| 文件路径 | HTTP 方法 | 删除原因 |
|---|---|---|
| `src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts` | POST | 普通 POST -> JSON，无流式、无大文件 |
| `src/app/api/v1/settings/route.ts` | PUT | 普通 PUT -> JSON |
| `src/app/api/v1/settings/mcp/servers/route.ts` | GET | 普通 GET -> JSON |

删除后，这些路径上的请求将自动 fallback 到 `next.config.ts` 中的 rewrite 规则：

```typescript
fallback: [
  {
    source: "/api/v1/:path*",
    destination: `${apiHost}/api/v1/:path*`,
  },
],
```

### Phase 2: 修复保留的 custom route

只保留 2 个真正需要特殊处理的路由：

#### 2a. `chat/stream/route.ts` -- SSE 流式代理

保留原因：Next.js rewrite 会缓冲响应体，导致 SSE 事件无法增量到达客户端。

修复内容：

1. 移除 `signal: request.signal`
2. 创建手动 `AbortController`，设置 5 分钟超时（与 `maxDuration: 300` 一致）
3. 监听客户端断开事件（`request.signal.addEventListener('abort', ...)`），在客户端断开时取消后端 fetch
4. 添加边界日志：route entered / request body read / backend fetch start / backend response received / streaming started

修复后核心逻辑：

```typescript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 300_000);

// 客户端断开时取消后端请求
request.signal.addEventListener("abort", () => controller.abort());

try {
  const backendResponse = await fetch(targetUrl, {
    ...options,
    signal: controller.signal,  // 使用自己的 signal，不直接透传 request.signal
  });
  // ...
} finally {
  clearTimeout(timeout);
}
```

#### 2b. `documents/library/upload/route.ts` -- 大文件上传

保留原因：需要 `duplex: "half"` 进行流式上传，绕过 Next.js body size 限制。

修改内容：无需修改（当前未使用 `request.signal`，不受影响）。

### Phase 3: 验证

1. 启动后端 FastAPI（端口 8000）
2. 启动前端 Next.js dev server（端口 3001）
3. 使用 Playwright MCP 验证以下场景：
   - 页面正常加载
   - MCP servers 设置接口可访问（原 settings/mcp/servers 路由已删除，走 rewrite）
   - Chat 非流式对话可正常返回（原 chat 路由已删除，走 rewrite）
   - Chat SSE 流式对话可正常流式返回（修复后的 stream 路由）
   - Studio 面板功能正常（notes, marks）

---

## 4. 改动范围

```
删除 (3 files):
  frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts
  frontend/src/app/api/v1/settings/route.ts
  frontend/src/app/api/v1/settings/mcp/servers/route.ts

修改 (1 file):
  frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/stream/route.ts

不动 (1 file):
  frontend/src/app/api/v1/documents/library/upload/route.ts
```

## 5. 回退方案

如果删除 custom route 后 fallback rewrite 出现问题（例如 POST body 丢失、超时等），可以恢复被删除的 route 文件，但将 `signal: request.signal` 替换为手动 `AbortController`（与 stream route 相同的修复方式）。

## 6. 风险评估

- 低风险：fallback rewrite 已验证可用于普通 API 请求
- 中风险：`chat` POST 请求的 `maxDuration: 300` 在 fallback rewrite 下不再生效；但开发环境无此限制，生产环境（自托管）亦无 serverless 超时
- 无风险：upload 路由不受影响
