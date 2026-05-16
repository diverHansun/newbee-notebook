# use-case.md — echarts

## 撰写前置确认

- `goals-duty.md` / `architecture.md` / `data-model.md` / `dfd-interface.md` 已存在。
- 本文件聚焦"模块内部如何围绕职责完成关键业务动作"，不展开为实现代码。

---

## 一、Use Case Overview（用例概览）

本模块的关键业务动作有 4 个，每个都能追溯到 goals-duty.md 中的具体 Duty：

1. **Create EChartsDiagram via /diagram skill** ——通过 `/diagram` 会话创建并持久化一张 echarts 图表（Duty #1-6, #7-9）。
2. **Render EChartsDiagram in Studio** ——在 Studio 详情页查看与导出已持久化的 echarts 图表（Duty #7-9）。
3. **Render Inline ECharts in Conversation** ——仅在本轮 `/diagram` assistant 回复中内联渲染 ` ```echarts ``` ` 围栏（Duty #2, #4, #10）。
4. **Save Inline Chart to Studio** ——把内联渲染的图表升级为持久化 diagram（Duty #6, #11）。

---

## 二、Main Flow Description（主流程描述）

### Use Case 1：Create EChartsDiagram via /diagram skill

1. 用户在某个 notebook 的会话中输入 `/diagram` 触发 skill。
2. skill provider 注入 echarts 章节扩展后的 system prompt（含子类型示例片段）。
3. 用户提出图表意图，例如"按销售额画一个 2026 年各月度的柱状图"。
4. LLM 按 prompt 指引在 `series.type` 白名单内挑选 `bar`，构造完整 option JSON。
5. LLM 调用 `create_diagram(diagram_type="echarts", content=<json>, title=<auto>, document_ids=[...])`；tool 入参不包含 `format`，后端由 registry descriptor 推导 `format="echarts_option"`。
6. `DiagramService` 从 registry 取出 `validator=validate_echarts_option`，对 content 做轻量浅校验。
7. 校验失败：service 抛 `DiagramValidationError`，tool 返回结构化错误，LLM 看到错误信息后修正并重试（最多由 skill 流程控制重试次数）。
8. 校验通过：service 写入 `diagrams` 表行与 content 文件，返回 `Diagram` 实体。
9. LLM 在最终响应中告知用户图表已生成；Studio diagrams 列表在下次拉取时显示该图。

### Use Case 2：Render EChartsDiagram in Studio

1. 用户在 Studio 侧栏切到"diagrams"列表（既有视图）。
2. 列表显示该 echarts diagram 的标题、类型徽章（"ECharts" / 中文"数据图表"）、更新时间。
3. 用户点击进入详情。
4. 既有 `useDiagram` + `useDiagramContent` hook 拉数据。
5. `DiagramViewer` 按 `format === "echarts_option"` 分发至 `EChartsRenderer`。
6. `EChartsRenderer`：
   - 在 mount 时 init echarts 实例（按白名单注册过的子类型）；
   - `JSON.parse(content)` → setOption；
   - 订阅 `useTheme` 做深浅色 option 微调（如 `backgroundColor`、`textStyle.color`）；
   - 监听容器尺寸变化 resize；
   - unmount 时 dispose 实例。
7. 用户点击工具栏"导出 PNG"，`DiagramExportHandle.exportImage` 调用 `echartsInstance.getDataURL` 生成图片并落盘。

### Use Case 3：Render Inline ECharts in Conversation

1. 用户本轮消息以 `/diagram` 开头，且 LLM 判断用户只需要临时查看 ECharts 图表，而不是直接持久化。
2. LLM 先调用 `preview_diagram_inline(diagram_type="echarts", content=<json>)`，tool 调用 `validate_echarts_option(content)`；校验通过后回 echo（不写库），同时满足 `force_first_tool_call` 与 `required_tool_call_before_response` 两条约束（详见 architecture §一.4）。
3. 若 tool 返回 `preview_diagram_inline_invalid_type` 或 `diagram_validation_failed`，LLM 不得输出 echarts 围栏；应修正 option 后重试，或改走 `create_diagram` 持久化路径。
4. LLM 在最终响应 markdown 中插入 ` ```echarts\n<json>\n``` ` 围栏。
5. 前端 ChatStore 把流式 token 推送到 `MessageItem`；`MessageItem` 把累积文本传给 `MarkdownViewer`。
6. `MessageItem` 只在"前一条 user 消息以 `/diagram` 开头"时传 `enableInlineCharts=true`；其他消息默认关闭。
7. markdown-pipeline 编译阶段只识别 echarts 围栏，每个生成一个 `placeholderId`，把 `rawContent` 放入 `InlineChartPayloadRegistry`，HTML 中只保留占位 div。
8. `MarkdownViewer` 渲染完 HTML 后，effect 阶段扫描 `[data-chart-placeholder][data-chart-type="echarts"]`，创建 `createRoot` 并挂内联 ECharts 卡片。
9. 流式过程中如果 `rawContent` 是不完整 JSON，内联卡片显示 loading 占位；JSON 完整后 setOption 渲染。
10. 当该消息从 DOM 卸载（用户切会话 / 清理上下文）时，对应 React root 卸载，registry 中条目被清理。

### Use Case 4：Save Inline Chart to Studio

1. 内联图表卡片右上角显示保存 icon button；hover / `title` / `aria-label` 显示"保存到 Studio"。
2. 用户点击 icon button，按钮进入 loading/disabled 状态。
3. `SaveToStudioAction` 从 `InlineChartPayloadRegistry` 取回 `rawContent`，自动生成标题（如根据 series.name / title.text 派生，或回落"未命名 ECharts 图表"）。
4. 前端调用新增 `POST /api/v1/diagrams` REST 接口，body 包含 `notebook_id`、`diagram_type="echarts"`、`content=<rawContent>`、`title`、`document_ids=[]`；不传 `format`。
5. 后端走 Use Case 1 第 6-8 步的相同 service 流程。
6. 成功：卡片内显示"已保存"轻量状态；当前会话文本不变（Non-Duty #8），不提供"打开 Studio"链接。
7. 失败：卡片内显示后端返回的诊断信息（来自 `DiagramValidationError`）并允许重试；用户也可回到对话让 LLM 改图。

---

## 三、Responsibility Boundaries（责任边界）

| 步骤 | 责任归属 |
|---|---|
| 注入 echarts agent system prompt | `DiagramSkillProvider.build_manifest`（既有）+ `_render_echarts_section`（本模块扩展） |
| 校验 ECharts option | `validate_echarts_option`（本模块）|
| 持久化写库 / 文件 | `DiagramService`（既有应用层） |
| Tool 调用编排（错误回执、retry） | `/diagram` skill runtime（既有） |
| Studio 详情视图 / 列表视图状态管理 | `useStudioStore` + react-query hooks（既有） |
| `DiagramViewer` 按 format 分发 | 本模块扩展（增加 echarts 分支） |
| echarts 实例 init / setOption / resize / dispose | `EChartsRenderer`（本模块） |
| ECharts 子类型按需注册 | `echarts-modules.ts`（本模块） |
| 请求级内联开关 | `MessageItem` / `MarkdownViewer(enableInlineCharts)`（本模块扩展） |
| echarts markdown 围栏 → 占位符替换 | `markdown-pipeline`（本模块扩展） |
| 占位符 → React root 挂载 | `MarkdownViewer` effect（本模块扩展） |
| 内联 payload 短期存储 | `InlineChartPayloadRegistry`（本模块） |
| "保存到 Studio" REST 调用 | `SaveToStudioAction`（本模块），底层走新增 diagrams create API |
| 错误诊断格式 | `_raise_validation_error`（既有，复用即可） |
| 主题切换 | `useTheme`（既有）+ `EChartsRenderer` 内部 option overlay |

### 刻意不归属

- echarts option 的语义正确性（柱状图轴该不该有 yAxis 等）→ 不属于本模块，由 LLM + ECharts 自身宽容机制承担。
- 内联图表的"流式半成品"判定 → 由 `EChartsRenderer` 内部用 `JSON.parse` try / catch 判定，不下推到 pipeline。
- 跨消息的图表引用 / 反向链接 → Non-Duty，不属于本模块。
- mermaid / reactflow 的会话内联渲染 → 不属于本模块，仍通过 Studio 展示。

---

## 四、Failure & Decision Points（失败点与决策点）

### 失败点 F1：LLM 输出非法 ECharts option

- 触发场景：JSON 不可 parse、缺 series、series.type 不在白名单。
- 当前模块行为：`create_diagram` 路径返回结构化错误码 `diagram_validation_failed` + 诊断信息；LLM 看到后通常会自我修正一次。
- 不可接受行为：静默接受非法 content 入库。

### 失败点 F2：流式过程中 JSON 不完整

- 触发场景：用户看到一段未完成的 echarts 围栏（流式正在进行）。
- 当前模块行为：内联 ECharts 卡片 `JSON.parse` try / catch；失败显示 loading 占位；下一次 chunk 到达重新尝试。
- 不可接受行为：抛出未捕获的 JS 异常导致整个消息渲染崩溃。

### 失败点 F3：ECharts 运行时报错（不支持的字段组合等）

- 触发场景：option 合 schema 但运行时 echarts 拒绝渲染。
- 当前模块行为：捕获 echarts 抛出的异常，组件退化为 `<pre>` 显示原始 JSON，并在卡片底部显示简短错误提示。
- 不可接受行为：整个 viewer 白屏或 React tree 崩溃。

### 失败点 F4："保存到 Studio" REST 失败

- 触发场景：后端 validator 拒绝（极少见，因为内联已经渲染通过——除非用户改过 JSON 后才保存）、或网络错误。
- 当前模块行为：卡片内显示错误诊断；保存 icon 恢复可点击，用户可重试。
- 不可接受行为：声称已保存但实际未落库；或重复点击导致重复创建（按钮在 inflight 期间应 disabled）。

### 失败点 F5：白名单三处不一致

- 触发场景：开发者只改了后端常量但忘了同步前端 `echarts-modules.ts` 或 prompt 示例。
- 当前模块行为：CI 单测断言三处集合相等，PR 阶段拦截。
- 这是构建期失败，不会进入生产。

### 决策点 D1：内联 vs 持久化路径选择

- 责任归属：LLM 决策（由 agent prompt 引导）+ 用户事后通过"保存到 Studio"补救。
- 模块不强制决策规则——prompt 提供倾向（如"如果用户说'快速看看'且适合 echarts，倾向内联；如果说'保存'、'记一下'，或选择 mindmap / flowchart / sequence，倾向持久化"），但最终选择由 LLM 完成。

### 决策点 D2：echarts diagram 的 `node_positions` 始终 NULL

- 责任归属：service 层创建时不设值；DiagramViewer 不读取该字段。
- `update_diagram_positions` 对 echarts diagram 的调用按既有 `DiagramFormatMismatchError` 拒绝（沿用现有行为，本模块不动）。

---

## 五、自检结论

- 4 个 use case 全部映射到 Duties，无"流程膨胀"。
- 责任边界明确写出"哪些步骤不归本模块"，避免后续把 LLM 决策、ECharts 内部语义、跨消息引用等悄悄收纳。
- 失败点覆盖了"输入非法 / 流式中间态 / 运行时异常 / 网络失败 / 构建期一致性"五类典型场景。
