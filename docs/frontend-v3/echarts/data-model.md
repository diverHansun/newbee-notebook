# data-model.md — echarts

## 撰写说明

本文件采用 docs-plan 的"精简模式"。echarts 模块的核心数据要么沿用既有 `Diagram` 实体（仅 `format` 取值扩展），要么是注入到既有结构里的扁平字段；新增的领域概念集中在 **echarts 内联渲染管线** 的短期值对象上。

---

## 一、Core Concepts（核心概念）

### 1. EChartsDiagram（沿用既有 Diagram 实体）

`Diagram` 是已存在的领域实体；echarts 不引入新实体，只是该实体的一个**特例**：

- 一个 `Diagram` 实例，当 `diagram_type == "echarts"` 且 `format == "echarts_option"` 时，被视为 EChartsDiagram。
- 其 `content`（落在 `content_path` 指向的文件）是一段合法的 ECharts option JSON。
- 其 `node_positions` 保持 `NULL`——echarts 没有"节点位置"概念。
- 其 `format` 不由 REST 客户端传入，而由后端 `DIAGRAM_TYPE_REGISTRY["echarts"].output_format` 推导。
- 其 content 写入 storage 时使用 `application/json`，notebook 导出时使用 `.json` 扩展名。

### 2. EChartsSeriesType（值对象）

一个 ECharts 子类型字符串，对应 `series[].type` 的取值。

- 取值集合受 `ECHARTS_SERIES_TYPE_WHITELIST` 约束。
- 该集合在系统中存在三处镜像：
  - 后端 `ECHARTS_SERIES_TYPE_WHITELIST`（validator 与 prompt 共用）。
  - 前端 `echarts-modules.ts` 中 `echarts.use([...])` 的注册列表。
  - 后端 `_ECHARTS_SUBTYPE_EXAMPLES` 的 key 集合。
- 三处一致性是一项工程约束（见 architecture.md §四.4），通过单元测试断言。

### 3. EChartsOptionPayload（值对象）

一段合法的 ECharts option JSON 文本，作为 `Diagram.content` 的载荷形态。

- 结构特征：顶层 object，包含必填 `series: list[dict]`，每个 series 必须有 `type` 字段。
- 允许多 series；validator 对每个 `series[i].type` 逐项校验，所有 type 都必须属于 `ECHARTS_SERIES_TYPE_WHITELIST`。
- 其他字段（title / legend / tooltip / xAxis / yAxis / grid / radar / visualMap / dataZoom / ...）对本系统是 opaque——validator 不检查、不规范化，原样下发到前端 echarts 实例。
- 不在系统中长期存在的状态；从 LLM 输出到落库再到渲染，全程作为不可变文本流转。

### 4. InlineChartPayload（值对象，前端独有）

一段"会话内联 ECharts 图表"的临时载荷，对应一次 ` ```echarts ... ``` ` 围栏。

- 由 markdown-pipeline 编译阶段从原始 markdown 文本中提取。
- 包含三要素：`chartType`（固定为 `"echarts"`）、`rawContent`（围栏内的文本）、`placeholderId`（在该消息渲染上下文中唯一）。
- 生命周期 = 一次 `MarkdownViewer` 渲染会话；不持久化，不写库。
- 用户点击保存 icon button 时，被升级为一个新的 `EChartsDiagram` 实体（通过新增 `POST /api/v1/diagrams` API）。

### 5. InlineChartPayloadRegistry（短期值容器，前端独有）

把 `InlineChartPayload.placeholderId → rawContent` 的映射在一次渲染中临时持有，让"编译阶段产出占位符 HTML"和"渲染阶段挂载 React 组件"之间能够找到原文本。

- 实现可以是 Map / WeakMap / module-level 单例，由 architecture 阶段决定，但在概念上它是值容器、不是有身份的实体。
- 一次 `MarkdownViewer` unmount 后即可清理。

### 6. InlineChartRenderScope（前端渲染开关）

一个由 Chat 层传给 `MarkdownViewer` 的布尔语义，而非持久化数据。

- `enableInlineCharts === true` 仅表示：当前 assistant 消息对应的用户本轮消息以 `/diagram` 开头。
- 默认值是 `false`，Reader、Video、普通聊天、非本轮 `/diagram` 回复都不会启用内联图表识别。
- 历史消息刷新后，前端可通过"assistant 消息的前一条 user 消息是否以 `/diagram` 开头"恢复该开关。

---

## 二、Entity / Value Object 区分

| 概念 | 类型 | 备注 |
|---|---|---|
| `EChartsDiagram` | Entity | 沿用现有 `Diagram` 实体身份与生命周期 |
| `EChartsSeriesType` | Value Object | 字符串字面量，无身份 |
| `EChartsOptionPayload` | Value Object | 不可变文本载荷 |
| `InlineChartPayload` | Value Object | 单次会话渲染期临时载荷 |
| `InlineChartPayloadRegistry` | Value Container | 短期 Map，不是领域抽象 |
| `InlineChartRenderScope` | Render Flag | 请求级开关，不入库 |

---

## 三、Key Data Fields（关键数据要素）

### EChartsDiagram 关键字段（仅说明与 echarts 强相关的部分）

- `diagram_type`：固定字符串 `"echarts"`。区分图表家族归属。
- `format`：固定字符串 `"echarts_option"`。决定 `DiagramViewer` 选择 `EChartsRenderer`。
- `content`（经由 `content_path` 文件）：合法的 ECharts option JSON。
- `node_positions`：始终为 `NULL`。echarts 没有节点拖拽位置。
- `document_ids`：可选关联文档（与现有 mindmap / flowchart 行为一致）。

### EChartsOptionPayload 关键内部字段（不被系统强约束，仅作认知参考）

- `series[].type`：必须存在且 ∈ 白名单。**这是 validator 唯一深度检查的内部字段**。
- `series[].data`：通常存在（柱线饼等需要），但 validator 不强制——某些子类型（如 funnel + dataset 外置）可不带 data。
- `xAxis` / `yAxis` / `radar` / `parallelAxis` / 等坐标系字段：系统不检查。

### InlineChartPayload 关键字段

- `chartType`：固定字符串 `"echarts"`。首版只挂载 ECharts Renderer。
- `rawContent`：原始围栏内文本，原样传给对应 Renderer。
- `placeholderId`：消息渲染上下文内唯一；用于 `querySelectorAll` 匹配与原文本回查。

---

## 四、Lifecycle & Ownership（生命周期与归属）

### EChartsDiagram

- **创建**：由 `DiagramService.create_diagram` 写入；触发方为 `/diagram` skill 的 `create_diagram` tool 调用（LLM 主动）或用户点击内联卡片保存 icon button 后前端主动调用 `POST /api/v1/diagrams`。
- **失败清理**：如果 content 文件已经写入、但 metadata 入库失败（例如 DB FK / CHECK / repository create 错误），service 必须删除刚写入的 content 文件，避免 orphan payload。
- **更新**：`update_diagram` tool / API；`update_diagram_positions` 对 echarts **不适用**（format 不匹配会抛 `DiagramFormatMismatchError`，沿用现有 service 行为）。
- **销毁**：`delete_diagram` tool / API，或随父 Notebook 级联删除。
- **归属**：notebook-scoped；与现有 mindmap / flowchart 一致。

### EChartsOptionPayload

- 与所属 `EChartsDiagram` 生命周期对齐。
- 校验时机：创建与更新两条路径上都经过 `validate_echarts_option`。
- 读取时机：Studio 详情页打开时由前端拉取并交给 `EChartsRenderer`。

### InlineChartPayload

- **创建**：`MarkdownViewer(enableInlineCharts=true)` 接收到包含 ` ```echarts ``` ` 围栏的 markdown 时，由 markdown-pipeline 编译阶段产出。
- **使用**：渲染阶段被 `InlineChartPlaceholderLayer` 消费一次。
- **销毁**：消息卸载或 viewer unmount 时随 `InlineChartPayloadRegistry` 一同清理。
- **归属**：仅属于该次渲染上下文，不跨消息、不跨会话。保存成功后也不与新 diagram_id 建立长期绑定。

---

## 五、自检结论

- 每个概念都能用一句话解释清楚，且能在后续接口（dfd-interface.md）或测试（test.md）中找到落点。
- 不存在为设计而设计的抽象：未抽象出 `IChartRenderer` 基类、未抽象 `SubtypeDescriptor`、未抽象 `InlineChartProvider`。
- `EChartsDiagram` 与现有 `Diagram` 通过"特例"关系而非继承关系建立连接，避免领域模型膨胀。
