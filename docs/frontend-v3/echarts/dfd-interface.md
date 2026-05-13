# dfd-interface.md — echarts

## 撰写前置确认

- `goals-duty.md`、`architecture.md`、`data-model.md` 已存在并已锁定。
- 本文件描述的所有数据流与接口均映射至 architecture.md §一的子组件，未引入新组件。

---

## 一、Context & Scope（上下文与范围）

### echarts 模块与外部模块的关系

- **上游（输入来源）**
  - LLM Runtime（本轮 `/diagram` skill 触发后的对话）——产出 `create_diagram` 调用、`preview_diagram_inline` 调用，以及内联 ` ```echarts ``` ` 文本。
  - Frontend ChatStore / MessageItem——把 assistant 流式响应文本传递给 `MarkdownViewer`。
  - Frontend StudioStore——选择 diagram 详情视图时触发 `DiagramViewer` 渲染。
  - 用户交互——"保存到 Studio"按钮点击。

- **下游（输出目标）**
  - `DiagramService`（既有应用层服务）——echarts 持久化路径直接复用其 `create_diagram` / `get_diagram` / `update_diagram` / `delete_diagram`。
  - PostgreSQL `diagrams` 表 + 文件存储 `content_path`——经由 `DiagramService` 落库。
  - 浏览器 DOM + ECharts 运行时——最终渲染目标。

- **不在本文档讨论范围**
  - `DiagramService` 内部的存储抽象（文件 vs 对象存储）。
  - 全局 markdown 管线的 chunking 策略细节（见 reader 模块文档）。
  - LLM 模型路由 / 推理细节。

---

## 二、Data Flow Description（数据流描述）

### Flow A：echarts 持久化创建（"保存型"主路径）

1. 用户在 `/diagram` 触发的会话中提出"画一个柱状图"。
2. LLM 在注入的 echarts agent prompt 引导下调用 `create_diagram(diagram_type="echarts", content=<json>, ...)`；tool 入参不包含 `format`。
3. `DiagramService.create_diagram` 收到入参，查表 `DIAGRAM_TYPE_REGISTRY["echarts"]`，拿到 `validator=validate_echarts_option`。
4. validator 执行轻量浅校验；失败抛 `DiagramValidationError`，错误信息回到 tool 调用结果。
5. 校验通过后 service 落库（`diagrams` 表行 + content 文件），返回 `Diagram` 实体。
6. Tool 调用结果回到 LLM；LLM 在最终响应文本中提示"图表已生成"。
7. 前端 Studio 通过既有 `useDiagrams` / `useDiagram` / `useDiagramContent` hook 拉取，`DiagramViewer` 根据 `format` 路由到 `EChartsRenderer` 渲染。

### Flow B：echarts 内联预览（"本轮 /diagram 会话临时"路径）

1. 用户在 `/diagram` 会话中说"快速画一张折线图给我看看"。
2. LLM 调用 `preview_diagram_inline(diagram_type="echarts", content=<json>)`。Tool 调用 `validate_echarts_option(content)`，不读写库，只回 echo 满足 `force_first_tool_call`。
3. 若 tool 校验通过，LLM 在最终响应 markdown 中输出 ` ```echarts\n<json>\n``` ` 围栏（作为正文内容）；若 tool 返回错误，LLM 必须修正后重试或改走 `create_diagram`，不得输出 echarts 围栏。
4. 前端 `MessageItem` 把流式 / 终态文本交给 `MarkdownViewer.content`。
5. `MessageItem` 只有在该 assistant 消息的前一条 user 消息以 `/diagram` 开头时，传入 `enableInlineCharts=true`。
6. markdown-pipeline 编译阶段把 echarts 围栏识别并替换为 `<div data-chart-placeholder data-chart-type="echarts" data-payload-id="ck-xxx" />`；原文本入 `InlineChartPayloadRegistry`。
7. `MarkdownViewer` 渲染产出 HTML 后，扫描所有 echarts 占位符，对每个 `placeholderId` 取回 `rawContent`，用 `createRoot` 挂载内联 ECharts 卡片。
8. 流式过程中如果 `rawContent` 不是合法 JSON（未结束），Renderer 显示 loading 占位；JSON 完整后 setOption 渲染。

### Flow C：内联图表"保存到 Studio"

1. 用户在内联图表卡片上点击保存 icon button（tooltip / `title` / `aria-label` 为"保存到 Studio"）。
2. 前端 `SaveToStudioAction` 调用新增 REST `POST /api/v1/diagrams`（或对应封装的 `createDiagram` 客户端方法），body 包含 `notebook_id`、`diagram_type="echarts"`、`content=<rawContent>`、`document_ids=[]`、`title=<auto-derived>`；不包含 `format`。
3. 后端走与 Flow A 第 3-5 步完全相同的 service 流程。
4. 成功后前端在卡片内显示"已保存"状态；当前不替换会话文本，不在消息流中插入引用标记，也不提供 Studio 详情链接。

### Flow D：Studio 详情查看与导出

1. 用户在 Studio diagrams 列表点击一项 echarts diagram。
2. 既有 `useDiagram` + `useDiagramContent` hook 拉数据。
3. `DiagramViewer` 按 `format === "echarts_option"` 分发至 `EChartsRenderer`。
4. `EChartsRenderer` 初始化 echarts 实例、`setOption(JSON.parse(content))`。
5. 用户点击"导出 PNG" → `DiagramExportHandle.exportImage` → `echartsInstance.getDataURL` → 保存为文件。

### Flow E：白名单一致性（构建期 / 测试期数据流）

1. 后端 `ECHARTS_SERIES_TYPE_WHITELIST` 是真相源。
2. 前端 `lib/diagram/echarts-modules.ts` 在编辑时由人工同步；CI 单测断言两端集合相等。
3. prompt 示例 `_ECHARTS_SUBTYPE_EXAMPLES` 的 key 集合同样需要等于白名单；后端单测断言。

这条流不是运行时数据流，但是工程一致性流，必须显性化。

---

## 三、Interface Definition（接口定义）

### 后端接口（语义层面，沿用既有契约）

**`POST /api/v1/diagrams`（新增 REST 创建接口）**
- 请求模型：`CreateDiagramRequest`。
- 输入语义：`notebook_id` 必填，`title` 必填，`diagram_type` 可取 `"echarts"`，`content` 是 ECharts option JSON 文本，`document_ids` 可空。
- 明确不接收 `format`；后端通过 `DIAGRAM_TYPE_REGISTRY[diagram_type].output_format` 推导。
- 输出语义：成功固定返回 `201` + `DiagramResponse`；校验失败返回结构化错误（`diagram_validation_failed` 错误码 + 4 段诊断信息）。
- 错误映射：请求模型校验失败走 FastAPI `422`；`DiagramValidationError` / `DiagramTypeNotFoundError` / document scope `ValueError` 返回 `400`；DB FK / `IntegrityError` 必须被映射为非 500 错误（如 `400 invalid_reference`）。
- 特性：同步。
- 注意：该接口服务于内联保存，也可作为后续前端显式创建 diagram 的通用入口；必须复用 `DiagramService.create_diagram`。

**`PATCH /api/v1/diagrams/{id}/positions`（既有，保持不适用）**
- echarts diagram 的 `update_diagram_positions` 路径不可用（format 不匹配）；这是既有 service 行为，本模块不改。

**`/diagram` skill tools（既有 + 新增）**
- 既有：`create_diagram` / `update_diagram` / `delete_diagram` / `list_diagrams` / `read_diagram` / `confirm_diagram_type` / `update_diagram_positions`。
- 新增：`preview_diagram_inline(diagram_type: str, content: str) -> ToolCallResult`
  - 输入语义：只接受 `diagram_type="echarts"` 与 ECharts option JSON 文本。
  - 输出语义：校验通过时返回 echo 形式 ToolCallResult，content 字段为人类可读确认文本，metadata 带 `diagram_type` 标记；类型错误或校验失败时返回错误码。
  - 特性：同步、无副作用、`tool_class=READ`，`risk_level=SAFE`。
  - 用途：同时满足 `force_first_tool_call`（作为有效首调用）与 `required_tool_call_before_response`（必须被纳入该名单，与 `DIAGRAM_OPERATION_TOOLS` 并集），使 LLM 内联输出路径不被约束阻断。

### 前端接口（语义层面）

**`DiagramViewer({ diagram, content })`（既有，扩展分发）**
- 输入：`diagram: Diagram`、`content: string`。
- 输出：渲染对应 React 子树；通过 `ref: DiagramExportHandle` 暴露 `exportImage(filename)`。
- 扩展点：当 `diagram.format === "echarts_option"`，分发至 `EChartsRenderer`。

**`EChartsRenderer({ diagram, content }, ref)`（新增）**
- 输入：`diagram: Diagram`、`content: string`（echarts option JSON 文本）。
- 输出：在容器内挂载 echarts 实例并 setOption；通过 ref 暴露 `exportImage`。
- 特性：客户端组件（"use client"），不参与 SSR；订阅 `useTheme` 切换深浅色 option overrides。
- 失败行为：`JSON.parse` 失败时退化为 `<pre>` 显示原文，与 mermaid renderer 的失败回落形态一致。

**`MarkdownViewer({ content, ... })`（既有，渲染管线增量）**
- 输入：markdown 文本。
- 输出：渲染产出 HTML + 在占位符处挂载 React 子树。
- 扩展点：新增 `enableInlineCharts?: boolean`，默认 `false`。启用时在 effect 中扫描 `[data-chart-placeholder][data-chart-type="echarts"]` 元素并挂内联 ECharts 卡片；payload 从 `InlineChartPayloadRegistry` 取回。

**`SaveToStudioAction.save(payload: InlineChartPayload)`（新增）**
- 输入：内联图表 payload。
- 输出：成功 → 返回新建的 `diagram_id`，调用方把卡片状态置为 saved；失败 → 抛错由调用方在卡片内显示错误。
- 特性：异步，单次调用，无自动重试策略（用户可手动重试）。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

| 数据 | 创建者 | 更新者 | 销毁者 | 一致性责任 |
|---|---|---|---|---|
| `EChartsDiagram` 实体 | `DiagramService.create_diagram`（被 LLM tool 或前端"保存"动作触发） | `DiagramService.update_diagram` | `DiagramService.delete_diagram` 或父 Notebook 级联 | `DiagramService` 负责事务一致性；validator 负责输入正确性 |
| `EChartsOptionPayload`（content 文件） | LLM 输出 → service 落盘 | 更新走 service 重写 | 随 diagram 删除清理 | content 与 `format` 字段一致由 service 负责 |
| ECharts 子类型白名单 | 后端代码常量是真相源 | 代码 PR | — | 前端 `echarts-modules.ts` 与 prompt 示例由 CI 测试断言一致 |
| `InlineChartPayload` | markdown-pipeline 编译阶段（仅 `enableInlineCharts=true`） | 不可变 | `MarkdownViewer` unmount 清理 | 仅在单次渲染上下文有效，不跨持久层 |
| 内联保存到 Studio 后的新 diagram | `DiagramService.create_diagram` | 同 EChartsDiagram | 同 EChartsDiagram | 保存动作完成后，会话内 payload 与新 diagram **不绑定关系**——这是有意的（Non-Duty #8）|

### 关键不变量

1. `Diagram.format == "echarts_option"` ⇒ `content` 必经过 `validate_echarts_option`。
2. `Diagram.diagram_type == "echarts"` ⇒ `Diagram.node_positions IS NULL`。
3. `POST /api/v1/diagrams` 的客户端请求不传 `format`，避免前端伪造 format 与 diagram_type 不一致。
4. `InlineChartPayload` 不进入持久层，除非通过"保存到 Studio"显式动作转化为 `EChartsDiagram`。
5. ECharts 子类型白名单的三处镜像（后端常量 / 前端 use 列表 / prompt 示例 keys）严格相等。
6. `echarts_option` content 写入与导出均按 JSON 处理：storage content-type 为 `application/json`，notebook 导出扩展名为 `.json`。
7. `DiagramService.create_diagram` 失败路径不得留下 orphan content 文件：若保存 content 后 metadata 入库失败，必须清理刚写入的 `content_path`。

---

## 五、自检结论

- 每条数据都能说清"从哪来 → 经过谁 → 到哪去"。
- 每个接口都对应至少一条数据流；没有"孤立接口"。
- `preview_diagram_inline` 虚 tool 的责任边界已明确——它属于 skill 流程兼容层，不持有数据状态。
- 内联 payload 与持久化 diagram 之间的"显式转化"边界清晰，避免后续出现一致性疑问。
