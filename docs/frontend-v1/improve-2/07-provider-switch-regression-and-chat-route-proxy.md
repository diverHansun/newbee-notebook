# P8 + P9: Provider 切换后的联调回归（非流式 `/chat` 代理未命中 + 流式 60s 超时）

---

## 1. 背景

在 `improve-2` 阶段完成 P1-P7 后，切换 `newbee_notebook/configs/llm.yaml` 的 LLM provider 为 `qwen`（`provider: qwen`）进行联调回归时，出现新的两类问题：

1. **P8（前端代理链路）**：非流式 `POST /chat` 的长请求在 `localhost:3000` 下仍表现为固定约 `30s` 后返回 `500 Internal Server Error`
2. **P9（后端超时策略）**：`explain/conclude` 流式 SSE 在 `qwen` provider 下经常在 `60s` 时收到 `timeout` error event

这两个问题都不是 P1-P7 的交互层回归，而是 **provider 切换后放大了链路与超时策略问题**。

---

## 2. 当前配置与关键代码位置

### 2.1 Provider 配置（已切换到 qwen）

**文件**：`newbee_notebook/configs/llm.yaml`

- `provider: qwen`（第 6 行）
- `qwen.request_timeout: 60.0`（第 27 行）
- `qwen.max_retries: 3`（第 28 行）

### 2.2 非流式 `/chat` 的前端自定义代理（已新增）

**文件**：`frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts`

该路由设计目标是绕过 `frontend/next.config.ts` 的 `rewrites()`，避免长请求在前端开发服务器路径上被代理超时截断。

关键特征：

- `maxDuration = 300`（第 5 行）
- 代理目标 `/api/v1/chat/notebooks/{id}/chat`（第 14 行）
- `signal: request.signal`（第 27 行）
- 返回头包含 `x-chat-proxy-route: next-app-api`（第 35 行），用于确认请求是否命中该路由

### 2.3 流式 `chat_stream()` 的 chunk timeout（当前固定 60s）

**文件**：`newbee_notebook/application/services/chat_service.py`

在 `chat_stream()` 中读取上游 token chunk 时：

```python
chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
```

对应代码位置：第 `352` 行。超时后会返回：

```python
yield {"type": "error", "error_code": "timeout", "message": "Stream timeout"}
```

对应代码位置：第 `405` 行。

---

## 3. 已复现实验与结论

> 说明：以下结果来自本地联调环境（前端 `localhost:3000`，后端 `localhost:8000`），以 `postman_collection.json` 的 `/chat` 与 `/chat/stream` 请求结构为基准。

### 3.1 非流式 `/chat`：短请求在 `3000` 下可成功，长请求稳定 30s 失败（P8）

#### 实测结果（qwen provider）

- `POST http://localhost:8000/api/v1/.../chat`
  - `chat`: `200`
  - `ask`: `200`
  - `conclude`: `200`（长耗时也能完成）
  - `explain`: 可极慢（客户端可能先超时），但不是固定 `30s` 失败

- `POST http://localhost:3000/api/v1/.../chat`
  - `chat`: `200`
  - `ask`: `200`
  - `explain`: **固定约 `30.0s` 返回 `500 Internal Server Error`**
  - `conclude`: **固定约 `30.0s` 返回 `500 Internal Server Error`**

#### 关键证据：`x-chat-proxy-route` 响应头缺失

对 `localhost:3000` 的 `/chat` 请求进行探测时，响应头中未出现：

```http
x-chat-proxy-route: next-app-api
```

结论：

- **新建的 `app/api/.../chat/route.ts` 尚未被当前运行中的 Next dev server 命中**
- 请求大概率仍在走 `frontend/next.config.ts` 的 `rewrites()` 代理路径
- 因此长请求依旧遭遇前端开发服务器的约 `30s` 超时

#### 推断根因（运行态）

最可能原因是：

- 新增 `app/api` 路由后，当前 Next dev server 未重启（HMR 未加载新文件路由）

这属于**运行态生效问题**，不是路由代码本身逻辑错误的首要嫌疑。

---

### 3.2 流式 `/chat/stream`：SSE 链路正常，qwen 下 `explain` 常在 60s 命中后端 chunk timeout（P9）

#### 实测结果（`localhost:3000`）

`explain` 模式流式请求：

- `start` 事件正常到达
- `heartbeat` 每约 `10s` 到达（证明 P5 的 heartbeat 修复生效）
- 在约 `60.6s` 收到：

```json
{"type":"error","error_code":"timeout","message":"Stream timeout"}
```

#### 结论

- 问题已从“链路空闲断开（30s）”转移为“后端应用层 chunk timeout（60s）”
- SSE 代理与 heartbeat 当前工作正常
- `qwen` 在 `explain/conclude` 场景的首 token 延迟/块间延迟可能超过当前固定阈值

---

## 4. 问题拆分（便于继续修复）

### P8：非流式 `/chat` 前端代理未命中（运行态问题）

**性质**：联调环境/前端 dev server 生效问题  
**优先级**：高（影响前端 fallback 成功率与长请求体验）

#### 下一步排查清单

1. **重启前端 Next dev server**
   - 重新加载新增的 `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts`
2. 发送一条短 `/chat` 请求到 `localhost:3000`
   - 验证响应头是否出现 `x-chat-proxy-route: next-app-api`
3. 复测 `explain/conclude` 非流式 `/chat`
   - 观察是否摆脱固定 `30s` `500`

#### 通过标准

- `localhost:3000 /chat` 响应头可见 `x-chat-proxy-route`
- 长请求不再出现固定 `30s` plain text `Internal Server Error`

---

### P9：qwen provider 下流式 `explain/conclude` 60s chunk timeout（后端策略问题）

**性质**：后端超时策略与 provider 时延特征不匹配  
**优先级**：高（影响 explain/conclude 稳定性）

#### 当前根因

`chat_service.py` 在 `chat_stream()` 中使用固定 `timeout=60` 等待下一块 token。对 `qwen` provider 的某些请求（尤其检索 + explain/conclude）不够宽松。

#### 下一步修复方向（建议）

方案 A（最小改动，优先）：

- 将 `chat_stream()` 的 chunk timeout 提取为常量/配置项（例如 `STREAM_CHUNK_TIMEOUT_SECONDS`）
- 默认提升到 `120` 或 `180` 秒

方案 B（更合理，建议后续）：

- 按模式设置 timeout（`chat/ask` 较小，`explain/conclude` 较大）
- 或与 provider 配置联动（例如从 `llm.yaml` 读取可选 `stream_chunk_timeout`）

#### 验收标准

- `qwen` 下 `explain/conclude` 流式请求在 `localhost:3000` 不再稳定于 `60s` 返回 `timeout`
- 仍能通过 heartbeat 保持连接活跃，不回退到 `30s` idle 断链问题

---

## 5. 对 `04-sse-stream-cancellation-and-fallback.md` 的关系说明

P5 文档中的修复（heartbeat + 持久化顺序 + fallback）仍然成立，并已显著改善 SSE 链路稳定性。  
本文件记录的是 **切换 provider 后新增暴露的回归/收尾问题**：

- P8：非流式 `/chat` 前端代理运行态生效问题
- P9：后端流式 chunk timeout 策略需要按 provider/模式调优

二者不应视为 P5 修复失败，而是联调深水区问题。

---

## 6. 建议的后续文档更新

在完成修复后，建议同步更新以下文档：

1. `docs/frontend-v1/improve-2/README.md`
   - 将 P8/P9 状态更新为“已修复”
2. 本文档（`07-...md`）
   - 补充最终修复方案与测试矩阵
3. `docs/frontend-v1/improve-2/04-sse-stream-cancellation-and-fallback.md`
   - 在文末增加“后续补充”节，链接到本文档（避免问题背景割裂）

---

## 7. 最终修复方案与回归结果（2026-02-23）

### 7.1 P8 修复：将 `next.config.ts` 的 API rewrite 调整到 `fallback` 阶段

**根因补充（最终确认）**

`frontend/next.config.ts` 中原先直接返回 rewrites 数组，属于默认 `afterFiles` 阶段。对于本项目的 `/api/v1/:path*` catch-all 规则，这会在部分情况下抢先于动态 `app/api` 路由匹配，导致新增的：

- `frontend/src/app/api/v1/chat/notebooks/[notebookId]/chat/route.ts`

未被命中，请求仍走 Next 开发服务器的 rewrite 代理路径。

**修复内容**

将 rewrite 改为 `fallback` 阶段，确保本地 `app/api` 路由优先，只有未命中的 API 路径才转发到后端：

```ts
return {
  fallback: [
    { source: "/api/v1/:path*", destination: `${apiHost}/api/v1/:path*` },
  ],
};
```

**结果**

重启前端后，`POST http://localhost:3000/api/v1/.../chat` 响应头出现：

```http
x-chat-proxy-route: next-app-api
```

说明非流式 `/chat` 已命中新建的 Next API 代理路由，不再走旧 rewrite 链路。

### 7.2 P9 修复：按模式提升流式 chunk timeout（`explain/conclude = 180s`）

**修复内容**

在 `newbee_notebook/application/services/chat_service.py` 中新增模式化 timeout 策略：

- `chat/ask`: 保持 `60s`
- `explain/conclude`: 提升为 `180s`

目的：为 `qwen` provider 下检索 + 长提示词 + 首 token 延迟留出余量，同时继续依赖 P5 的 heartbeat 保持连接活跃。

### 7.3 回归结果（qwen provider）

#### 非流式 `/chat`（经 `localhost:3000`）

- `explain`: `200`（约 `207.4s`，`x-chat-proxy-route=next-app-api`）
- `conclude`: `200`（约 `77.2s`，`x-chat-proxy-route=next-app-api`）

不再出现固定 `30s` 的 `500 Internal Server Error`。

#### 流式 `/chat/stream`（经 `localhost:3000`）

- `explain`: 心跳持续到 `80s+`，约 `83.2s` 收到首个 `content`（此前会在 `60s` timeout）
- `conclude`: 心跳持续到 `80s+`，约 `85.9s` 收到首个 `content`

不再稳定命中 `60s` `Stream timeout`。

### 7.4 验收结论

- P8：已修复（前端非流式 `/chat` 长请求链路）
- P9：已修复（qwen provider 下 explain/conclude 流式 chunk timeout 过低）

后续若切换到更慢 provider 或启用更重的推理模式（如 search / thinking），建议继续沿用“按模式/按 provider 配置化 timeout”的策略，而不是回到固定常量。
