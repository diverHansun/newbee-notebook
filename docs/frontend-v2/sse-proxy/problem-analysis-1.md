# Frontend SSE Proxy 问题文档分析

## 1. 问题摘要

当前 `frontend` 在开发环境下存在一个高优先级代理层问题：

- 通过 `http://localhost:3001/api/v1/...` 访问一部分 **自定义 Next App Route 代理接口** 时，请求会长时间挂起，客户端拿不到任何响应头，最终表现为超时。
- 直接访问后端 `http://localhost:8000/api/v1/...` 时，请求不会挂起；即使后端业务返回 `500`，也会很快返回。
- 因此，问题不在后端服务本身，而在 `frontend/src/app/api/v1/**` 这层自定义代理实现。

这不是 `/note` skill 自身的问题，也不是 SSE parser 的问题，而是 **frontend proxy boundary** 的问题。

---

## 2. 受影响范围

### 2.1 已确认会挂起的前端代理路径

- `POST /api/v1/chat/notebooks/{notebookId}/chat`
- `POST /api/v1/chat/notebooks/{notebookId}/chat/stream`
- `GET /api/v1/settings/mcp/servers`

### 2.2 已确认正常的路径

- 页面访问：`GET /notebooks` 正常
- 通过 fallback rewrite 代理的普通 `/api/v1/...` GET 请求可正常返回
- 后端直连：
  - `GET http://localhost:8000/api/v1/health` 正常
  - `POST http://localhost:8000/api/v1/chat/.../chat` 会快速返回业务结果或业务错误，不会挂起
  - `POST http://localhost:8000/api/v1/chat/.../chat/stream` 之前已验证可正常返回 SSE 事件和 `done`

结论：

- **不是整个前端都坏了**
- **不是整个 `/api/v1` 都坏了**
- **只要走到自定义 App Route proxy，就有概率挂住**

---

## 3. 复现结论

### 3.1 当前主分支状态

- `stage/backend-v2` 已经 fast-forward 合并了 batch-3
- 前端依赖已恢复，`frontend/node_modules` 可用
- `frontend` 的 `lint` / `typecheck` 已重新通过
- 后端健康检查正常

### 3.2 关键复现结果

#### Case A: 后端直连 chat

对：

- `POST http://localhost:8000/api/v1/chat/notebooks/.../chat`

结果：

- 后端会快速返回 HTTP 响应
- 即使是 `500`，也不会超时挂住

说明：

- 后端 chat endpoint 本身不是“卡死不返回”的状态

#### Case B: 前端代理 chat

对：

- `POST http://localhost:3001/api/v1/chat/notebooks/.../chat`

结果：

- 客户端等待很久，最终超时
- 超时前拿不到任何有效响应头

说明：

- 前端自定义 `/chat` proxy route 没有把后端响应及时返回给客户端

#### Case C: 后端直连 stream

之前已验证：

- `POST http://localhost:8000/api/v1/chat/notebooks/.../chat/stream`

结果：

- 能拿到 `start`
- 能拿到 `tool_call` / `tool_result`
- 能拿到 `confirmation_request`
- 能在确认后继续执行
- 最终拿到 `done`

说明：

- 后端 SSE 生成器本身是可工作的

#### Case D: 前端代理 stream

对：

- `POST http://localhost:3001/api/v1/chat/notebooks/.../chat/stream`

结果：

- 客户端等待 60s 仍拿不到首包
- 最终超时

说明：

- 前端 stream proxy route 没有把后端 SSE 首包及时转发出来

#### Case E: 前端代理 settings GET

对：

- `GET http://localhost:3001/api/v1/settings/mcp/servers`

结果：

- 同样超时

说明：

- 问题并不只限于 SSE
- 问题也不只限于 POST
- 范围已经扩展为：**自定义 App Route proxy 普遍异常**

---

## 4. 代码层定位

当前项目里有两种 API 代理策略并存：

### 4.1 策略 A：`next.config.ts` fallback rewrite

文件：

- `frontend/next.config.ts`

特点：

- 对 `/api/v1/:path*` 做统一 fallback rewrite
- 这一路径下的大部分普通 API 请求是正常的

### 4.2 策略 B：手写 `src/app/api/v1/**/route.ts`

关键文件：

- `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts`
- `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/stream/route.ts`
- `frontend/src/app/api/v1/settings/route.ts`
- `frontend/src/app/api/v1/settings/mcp/servers/route.ts`
- `frontend/src/app/api/v1/documents/library/upload/route.ts`

当前观察到的行为是：

- rewrite 路径大体正常
- 手写 proxy route 异常

这说明问题集中在 **策略 B**，而不是整个 frontend 或 backend。

---

## 5. 共同特征分析

异常路由有以下共同点：

1. 都运行在 Next App Route Handler 中
2. 都在服务端再次 `fetch()` 后端地址
3. 都依赖 `process.env.INTERNAL_API_URL || "http://localhost:8000"`
4. 大部分都把 `request.signal` 透传给后端 `fetch`
5. 都缺少边界日志，因此客户端只能看到“超时”，看不到卡在哪一步

其中两个最关键的代表实现如下：

### 5.1 非流式 chat proxy

文件：

- `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts`

核心模式：

- `await request.text()`
- `await fetch(targetUrl, ...)`
- `await backendResponse.text()`
- `return new NextResponse(responseText, ...)`

理论上，这条路径即使后端返回 `500`，也应该很快把 `500` 透传给客户端。

但现实是：

- `8000` 直连很快返回
- `3001` 代理超时

因此挂点不在业务层，而在 proxy route 自身。

### 5.2 流式 chat proxy

文件：

- `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/stream/route.ts`

核心模式：

- `await request.text()`
- `await fetch(targetUrl, ...)`
- `return new Response(backendResponse.body, headers)`

理论上，这条路径应该把后端 SSE body 直通给浏览器。

但现实是：

- `8000` 直连可收到 SSE 事件
- `3001` 一直拿不到首包

因此问题不是 SSE parser，而是 proxy route 自己没有成功把响应建立起来。

---

## 6. 已排除项

以下方向目前已经可以排除：

### 6.1 不是 `/note` skill 逻辑错误

原因：

- 直连后端 `/chat` 和 `/chat/stream` 时，`/note` 的 list/create/delete/confirm 都已验证过

### 6.2 不是前端 SSE parser 错误

文件：

- `frontend/src/lib/utils/sse-parser.ts`

原因：

- 连非流式 `/chat` 代理也会超时
- 说明问题发生在 parser 之前

### 6.3 不是后端 health 问题

原因：

- `GET /api/v1/health` 正常
- 后端直连 chat 路径会快速返回 HTTP 结果

### 6.4 不是 rewrite fallback 本身的问题

原因：

- 依赖 rewrite 的普通 API 请求可以工作

---

## 7. 高置信度结论

### 7.1 精确问题定义

**当前真正的问题是：**

`frontend/src/app/api/v1/**` 下的自定义 Next App Route proxy 在开发环境里没有正确完成“前端请求 -> Route Handler -> 后端 fetch -> 响应回传”这条链路，导致客户端对这些 route 的请求长期挂起，拿不到响应头。

这已经不是单个接口问题，而是 **custom proxy route layer** 的系统性问题。

### 7.2 高置信度原因判断

从现有证据看，最高置信度的原因不是某一条业务语句写错，而是：

**项目当前混用了两套代理机制，而自定义 App Route proxy 这一套在当前 Next dev 环境下不稳定/不可用。**

也就是说：

- rewrite fallback 这一套能工作
- handcrafted app route proxy 这一套不能稳定工作

这属于 **proxy architecture mismatch**，而不是 note/bookmark 业务回归。

---

## 8. 次级原因候选（需要修复时逐条验证）

下面这些是修复阶段需要验证的候选点，按优先级排序：

### 候选 A：自定义 App Route proxy 本身在当前 Next dev 环境下失效

现象支持：

- GET / POST / SSE 都能中招
- 说明不是单一方法或单一业务路径

### 候选 B：`request.signal` 透传到后端 `fetch` 存在问题

现象支持：

- 多个 custom route 都用了相同模式
- rewrite fallback 不会走这段逻辑

但目前证据不足以直接下结论，因为理论上若 `request.signal` 立刻异常，通常应返回 `499/502`，而不是无限挂住。

### 候选 C：Route Handler 的服务端 `fetch()` 已经卡住，但没有任何边界日志

现象支持：

- 客户端只能看到 timeout
- 当前 route 里没有 `before fetch` / `after fetch` / `first chunk` 级别日志

### 候选 D：流式 route 中直接返回 `backendResponse.body` 的方式在当前环境下不可用

这个候选只解释 `chat/stream`，但解释不了 `chat` 和 `settings/mcp/servers` 的超时。

所以它**不是总根因**，最多只是流式路径上的附加问题。

---

## 9. 建议方案（只讨论，不实施）

### 方案 1：统一代理策略，非流式接口回归 rewrite

建议：

- 把 `chat`、`settings`、`mcp/servers` 这类非流式接口从手写 App Route proxy 退回统一 rewrite
- 只保留真正需要特殊处理的 route

优点：

- 架构更简单
- 与当前已经验证可工作的路径保持一致
- 排错面最小

缺点：

- 需要重新梳理哪些接口必须走 App Route

### 方案 2：只为 SSE 保留专用 route，其余全部回归 rewrite

建议：

- `chat/stream` 单独保留
- `chat` 非流式也不要走手写 proxy

优点：

- 最符合“最小必要特殊化”原则
- 能最大限度减少 custom proxy 面积

缺点：

- 需要重新拆分客户端 API 路由策略

### 方案 3：保留现有 App Route proxy，但先加边界日志再修

建议：

- 在每个 proxy route 里增加以下日志点：
  - route entered
  - request body read complete
  - backend fetch start
  - backend fetch response headers received
  - response returned to client
  - stream first chunk forwarded

优点：

- 能把“超时”精确定位到某一行

缺点：

- 这一步更适合进入修复阶段时做

### 方案 4：开发环境临时绕过 Next proxy，前端直连后端

建议：

- 仅在本地开发阶段，让 chat 相关请求直接打 `8000`

优点：

- 最快恢复联调

缺点：

- 只是 workaround，不是根修复
- 生产和开发路径会分叉

---

## 10. 推荐路线

如果下一步进入修复，我建议按这个顺序：

1. 先验证“统一 rewrite / 缩小 custom route 面积”是否可行
2. 如果只剩 `chat/stream` 必须特殊处理，再单独修 SSE proxy
3. 修之前先加边界日志，避免继续盲修

也就是说，**推荐优先级是先做架构收敛，再做点状修补**。

---

## 11. 当前结论一句话版

当前前端问题不是 `/note`、不是 SSE parser、也不是后端 chat 服务本身，而是：

**`frontend/src/app/api/v1/**` 这层自定义 Next App Route proxy 在当前开发环境中整体不可靠，导致 custom proxy 请求超时；应优先收敛代理架构，而不是直接在 note/SSE 业务层继续打补丁。**
