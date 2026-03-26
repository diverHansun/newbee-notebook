# 进度指示器：设计规格

## 架构概览

```
后端 AgentLoop.stream()
  |
  |  yield ToolCallEvent(tool_name, tool_call_id, tool_input)
  |  yield ToolResultEvent(tool_name, tool_call_id, success, ...)
  v
ChatService.chat_stream()
  |
  |  转换为 dict: {"type": "tool_call", "tool_name": ..., ...}
  |  转换为 dict: {"type": "tool_result", "tool_name": ..., ...}
  v
SSE 适配器 (sse_adapter)
  |
  |  SSEEvent.format("tool_call", payload)    <-- 已有，无需改动
  |  SSEEvent.format("tool_result", payload)  <-- 已有，无需改动
  v
前端 parseSseStream()
  |
  |  解析为 SseEventToolCall / SseEventToolResult   <-- 新增类型定义
  v
useChatSession.onEvent()
  |
  |  "tool_call"   -> addToolStep()      <-- 新增处理分支
  |  "tool_result" -> updateToolStep()   <-- 新增处理分支
  v
Zustand store (ChatMessage.toolSteps)
  |
  v
MessageItem -> ToolStepsIndicator   <-- 新增渲染组件
```

**关键点：后端和 SSE 层零改动。** 所有变更集中在前端。

---

## 数据结构

### ToolStep 类型（新增）

```typescript
export type ToolStep = {
  id: string;           // tool_call_id, 用于匹配 tool_result
  toolName: string;     // 原始 tool_name, 用于前端 label 映射
  status: "running" | "done" | "error";
};
```

字段说明：
- `id`: 与后端 `tool_call_id` 一一对应，确保 `tool_result` 能准确更新对应步骤
- `toolName`: 保存原始工具名称，由前端 `toolDisplayLabel()` 函数映射为用户可读标签
- `status`: 三态，由 SSE 事件驱动转换：`tool_call` -> running, `tool_result(success=true)` -> done, `tool_result(success=false)` -> error

不存储 `tool_input`、`content_preview` 等非渲染字段，避免不必要的内存占用。

### ChatMessage 扩展

```typescript
export type ChatMessage = {
  // ... 现有字段全部保留
  thinkingStage?: string | null;    // 保留，无工具调用时使用
  toolSteps?: ToolStep[];           // 新增，有工具调用时使用
};
```

`thinkingStage` 与 `toolSteps` 的关系：
- 两者在渲染层面互斥：`toolSteps` 非空时，`ToolStepsIndicator` 接管显示
- `thinkingStage` 在 `toolSteps` 模式下仅用于检测 `"synthesizing"` 阶段
- 无需修改 `thinkingStage` 的数据结构或后端发送逻辑

### SSE 事件类型（新增）

```typescript
export type SseEventToolCall = {
  type: "tool_call";
  tool_name: string;
  tool_call_id: string;
  tool_input: Record<string, unknown>;
};

export type SseEventToolResult = {
  type: "tool_result";
  tool_name: string;
  tool_call_id: string;
  success: boolean;
  content_preview: string;
  quality_meta: Record<string, unknown> | null;
};
```

注意：`tool_input`、`content_preview`、`quality_meta` 在事件类型中定义（因为 SSE 流中确实包含这些字段），但前端处理时只提取 `tool_call_id`、`tool_name`、`success`，不存储其余字段到 store。

---

## 状态管理

### Zustand Store 新增 Actions

```typescript
// chat-store.ts 新增两个 action

addToolStep: (messageId: string, step: ToolStep) => void;
updateToolStep: (messageId: string, toolCallId: string, status: ToolStep["status"]) => void;
```

`addToolStep` 实现逻辑：
- 找到 `id === messageId` 的消息
- 将 step push 到 `toolSteps` 数组（如果 `toolSteps` 不存在则初始化为 `[step]`）

`updateToolStep` 实现逻辑：
- 找到 `id === messageId` 的消息
- 在 `toolSteps` 中找到 `id === toolCallId` 的步骤
- 更新其 `status` 字段

两个 action 都是浅更新，O(n) 复杂度（n 为消息数），与现有 `updateMessage` 一致。

---

## 事件处理流程

在 `useChatSession.ts` 的 `onEvent` 回调中新增两个分支：

```
收到 SSE event:

  type === "tool_call":
    if (activeAssistantIdRef.current) {
      addToolStep(activeAssistantIdRef.current, {
        id: event.tool_call_id,
        toolName: event.tool_name,
        status: "running",
      });
    }

  type === "tool_result":
    if (activeAssistantIdRef.current) {
      updateToolStep(
        activeAssistantIdRef.current,
        event.tool_call_id,
        event.success ? "done" : "error",
      );
    }
```

### 事件时序

典型的 Agent 模式工具调用时序：

```
1. thinking(reasoning)     -> thinkingStage = "reasoning"   -> 显示 "AI 正在思考..."
2. thinking(retrieving)    -> thinkingStage = "retrieving"   -> (被 toolSteps 接管后不影响显示)
3. tool_call(knowledge_base) -> toolSteps.push({status: "running"})
4. tool_result(knowledge_base, success) -> toolSteps[0].status = "done"
5. tool_call(tavily_search)  -> toolSteps.push({status: "running"})
6. tool_result(tavily_search, success) -> toolSteps[1].status = "done"
7. thinking(synthesizing)  -> thinkingStage = "synthesizing" -> 步骤列表末尾显示 "正在生成回答..."
8. content(delta)          -> 步骤列表渐隐，消息内容开始渲染
```

无工具调用场景的时序：

```
1. thinking(reasoning)     -> thinkingStage = "reasoning"   -> 显示 "AI 正在思考..."
2. thinking(synthesizing)  -> thinkingStage = "synthesizing" -> 显示 "正在生成回答..."
3. content(delta)          -> 指示器消失，消息内容开始渲染
```

---

## 渲染逻辑

### 条件分支

```
MessageItem 渲染:
  if (status === "streaming" && !content) {
    if (toolSteps 存在且非空) {
      渲染 <ToolStepsIndicator
        steps={toolSteps}
        thinkingStage={thinkingStage}
      />
    } else {
      渲染 <ThinkingIndicator stage={thinkingStage} />   // 现有组件，不变
    }
  } else {
    渲染消息内容   // 现有逻辑，不变
  }
```

### ToolStepsIndicator 组件结构

```
<div class="tool-steps-indicator">
  <div class="tool-steps-list">
    <!-- 已完成步骤 -->
    <div class="tool-step tool-step--done">
      <span class="tool-step-icon" />     <!-- 静态对勾 -->
      <span class="tool-step-label">检索知识库</span>
    </div>
    <!-- 进行中步骤 -->
    <div class="tool-step tool-step--running">
      <span class="tool-step-icon" />     <!-- 旋转圆环，复用 thinking-indicator-ring -->
      <span class="tool-step-label">搜索网络...</span>
    </div>
    <!-- synthesizing 阶段（可选） -->
    <div class="tool-step tool-step--running">
      <span class="tool-step-icon" />
      <span class="tool-step-label">正在生成回答...</span>
    </div>
  </div>
  <!-- 底部进度条，复用现有 shimmer bar -->
  <div class="tool-steps-progress">
    <span class="tool-steps-progress-bar" />
  </div>
</div>
```

### 渐隐消失逻辑

当第一个 `content` delta 到达时，`appendMessageContent` 将 `thinkingStage` 设为 null 并开始填充 content。此时 `showThinkingIndicator` 条件（`!content`）变为 false，组件自然被替换为消息气泡。

要实现 0.5s 渐隐效果，需要在 content 到达时先播放退出动画，再切换渲染。具体方案见 [implementation-guide.md](./implementation-guide.md) 中的消失动画部分。

---

## 标签映射

### 映射函数

```typescript
function toolDisplayLabel(toolName: string, t: TranslateFn): string {
  const known: Record<string, LocalizedString> = {
    knowledge_base:   uiStrings.tools.knowledgeBase,
    tavily_search:    uiStrings.tools.webSearch,
    tavily_crawl:     uiStrings.tools.webCrawl,
    zhipu_web_search: uiStrings.tools.webSearch,
    zhipu_web_crawl:  uiStrings.tools.webCrawl,
    time:             uiStrings.tools.getTime,
  };
  if (known[toolName]) return t(known[toolName]);

  // 兜底：下划线转空格，首字母大写
  return toolName.replace(/_/g, " ").replace(/^\w/, c => c.toUpperCase());
}
```

### i18n 词条

```typescript
// strings.ts 新增
tools: {
  knowledgeBase: { zh: "检索知识库", en: "Searching knowledge base" },
  webSearch:     { zh: "搜索网络", en: "Searching the web" },
  webCrawl:      { zh: "抓取网页", en: "Fetching web page" },
  getTime:       { zh: "获取时间", en: "Getting time" },
},
```

新增工具时只需往映射表加一行。MCP 和 Skill 工具走兜底逻辑，无需预先注册。

---

## 性能评估

| 指标 | 影响 |
|------|------|
| 额外 re-render 次数 | 每轮对话 2-6 次（远少于 content delta 的几十上百次） |
| Store 更新开销 | push / 浅更新，O(1) 操作 |
| 新 SSE 事件解析 | 事件已有，仅新增 JSON 反序列化（微秒级） |
| DOM 节点增量 | 最多 5-10 个 step div（极少数场景） |
| 动画性能 | 复用现有 GPU 加速的 transform/opacity 动画 |
| 内存增量 | 每个 ToolStep 约 60 bytes，消息完成后可清理 |

结论：性能影响可忽略不计。不引入轮询、定时器或额外网络请求。
