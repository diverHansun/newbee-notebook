# architecture.md — echarts

## 撰写前置确认

- `goals-duty.md` 已存在并以"模块定位 + 6 条设计目标 + 13 条 Duties + 10 条 Non-Duties"形式锁定边界。
- 本文件描述的所有结构均可追溯到 Design Goals 与 Duties；未引入新职责。

---

## 一、Architecture Overview（总体架构）

echarts 模块横跨 **后端 skill 注册 / 校验 / API / DB** 与 **前端渲染 / 内联管线** 两侧，对应以下子组件：

**后端侧**

1. **EChartsTypeDescriptor**
   - 注册于 `DIAGRAM_TYPE_REGISTRY["echarts"]`，挂载 `validator=validate_echarts_option`、`output_format="echarts_option"`。
   - 与现有 mindmap / flowchart / sequence Descriptor 同形态，遵循"开放-封闭"——注册即扩展，无需修改 registry 抽象。

2. **EChartsValidator**
   - 独立函数 `validate_echarts_option(content)`，承担 Duty #2 的"轻量浅校验"。
   - 复用 `_raise_validation_error` 诊断结构（category / detail / location / suggestion）。

3. **EChartsPromptComposer**
   - 局部于 `registry.py`：`_render_echarts_section()` + `_ECHARTS_SUBTYPE_EXAMPLES`。
   - 与 `_render_type_section()` 解耦——echarts 是"总规则 + 子类型示例"两层结构，套用通用渲染会破坏一致性。
   - 注入路径仍由 `DiagramSkillProvider.build_manifest()` 在 `/diagram` 触发时拼装并下发，本模块**不改注入策略**。

4. **InlinePreviewToolShim（流程兼容层）**
   - 解决"`/diagram` 强制工具调用约束 vs echarts 内联输出"的矛盾（Duty #4）。当前 manifest 有两条约束：`force_first_tool_call=True`（必须先调用某个工具）与 `required_tool_call_before_response=DIAGRAM_OPERATION_TOOLS`（最终响应前必须调过 create/update/delete/list/read 之一）。仅放宽 `force_first_tool_call` 不够；内联路径下 LLM 不会调任何 DIAGRAM_OPERATION_TOOLS，仍然过不了第二条约束。
   - 决策：**新增 echarts-only 虚 tool `preview_diagram_inline`，并把它纳入 `required_tool_call_before_response` 名单（与 DIAGRAM_OPERATION_TOOLS 并集，命名仍由 provider.py 中决定）**。该 tool 接受 `diagram_type="echarts"` + `content`，调用 `validate_echarts_option(content)` 做轻量校验，但不写库、不读库；校验通过后才允许 LLM 输出 ` ```echarts ``` ` 围栏。
   - 约束：tool 返回错误时不视为"允许输出内联围栏"的业务成功。实现阶段至少通过 prompt 规则和 e2e 用例覆盖"preview 失败后不得输出 ` ```echarts ``` `"；若后续 engine 支持"错误 tool 不满足 required tool"，可再收紧到机制层。

**前端侧**

5. **EChartsRenderer**
   - `frontend/src/components/studio/echarts-renderer.tsx`，`forwardRef<DiagramExportHandle>`。
   - 负责 echarts 实例的 init / setOption / resize / dispose、PNG 导出、主题切换。
   - 与 `MermaidRenderer` / `ReactFlowRenderer` 并列，由 `DiagramViewer` 按 `format` 分发。

6. **EChartsModulesRegistry**
   - `frontend/src/lib/diagram/echarts-modules.ts`，集中执行 `echarts.use([...])`，**镜像后端白名单**。
   - 单独抽出来是为了让"后端白名单 ↔ 前端 use() 列表 ↔ prompt 示例"三处一致性可被一处测试断言（见 test.md）。

7. **InlineChartPlaceholderLayer（内联渲染管线增量层）**
   - 跨两个文件：`markdown-pipeline` 在编译阶段把 ` ```echarts ... ``` ` 替换为占位元素；`MarkdownViewer` 在渲染后扫描占位符并用 `createRoot` 挂 React 组件。
   - 该层必须由 `MarkdownViewer.enableInlineCharts === true` 显式开启；默认关闭。Chat 侧仅对"用户本轮消息以 `/diagram` 开头"对应的 assistant 回复开启。
   - 不重写现有 dangerouslySetInnerHTML 路径，仅在其上叠加"识别 + 注入"两步；` ```mermaid ``` ` 和 reactflow JSON 在会话中仍是普通代码块。

8. **SaveToStudioAction**
   - 内联卡片右上角保存 icon button。调用新增 `POST /api/v1/diagrams`；成功后在卡片内显示已保存状态，不提供 Studio 跳转链接。
   - 不持有本地图表 ID 状态，不改写会话文本。

9. **CreateDiagramRestEndpoint**
   - 新增于 `newbee_notebook/api/routers/diagrams.py`，请求模型放在 `newbee_notebook/api/models/diagram_models.py`。
   - 请求体不接收 `format`，只接收必填 `notebook_id` / `title` / `diagram_type` / `content` 与可选 `document_ids`，并复用 `DiagramService.create_diagram`。
   - 成功固定返回 `201` + `DiagramResponse`。`DiagramValidationError` / `DiagramTypeNotFoundError` / document scope `ValueError` 映射为 `400`；请求模型错误由 FastAPI 返回 `422`；DB FK / `IntegrityError` 必须显式映射，不能冒泡成 500。

10. **BackendServiceConsistency**
   - `DiagramService._content_type_for_format("echarts_option")` 返回 `application/json`，覆盖 create / update 两条写 content 路径。
   - `export_service._diagram_extension("echarts_option")` 返回 `.json`，避免 notebook 导出把 ECharts option 写成 `.mmd`。
   - `DiagramService.create_diagram` 在 content 文件保存成功、metadata 入库失败时清理 orphan content 文件，保证失败路径不留下不可达对象。

### 子组件协作关系

- **后端写入路径**（持久化场景）：LLM 调用 `create_diagram(diagram_type="echarts", ...)` → `DiagramService` → `EChartsValidator` → 写库 → Studio 列表查询 → `DiagramViewer` 选 `EChartsRenderer`。
- **后端内联路径**（一次性预览场景）：LLM 调用 `preview_diagram_inline(diagram_type="echarts", ...)` → validator 通过 → 满足 `force_first_tool_call` → LLM 在文本中输出 ` ```echarts <JSON> ``` ` → 不进入 `DiagramService`。若 validator 失败，LLM 不得输出 echarts 围栏。
- **前端会话路径**：本轮 `/diagram` assistant 消息流式到达 → `MarkdownViewer(enableInlineCharts)` → 编译阶段 echarts 占位符替换 → 渲染后 `InlineChartPlaceholderLayer` 扫描并 `createRoot` 挂内联 `EChartsRenderer` → 用户点击保存 icon → `SaveToStudioAction` 调 REST API。

> 阶段边界：后端先实施时可以完成 registry / validator / preview tool / POST API / DB 与后端验证；真正的用户可见内联渲染体验依赖前端 `MarkdownViewer(enableInlineCharts)` 与 `EChartsRenderer` 落地。在前端完成前，后端 e2e 只验证 tool 与持久化闭环，不把 raw ` ```echarts ``` ` 围栏视为完整 UX。

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Strategy（沿用既有）
`DIAGRAM_TYPE_REGISTRY` 已经是 Strategy 模式实例——不同 `DiagramTypeDescriptor` 提供差异化的 validator / prompt / format。echarts 沿用该模式，**不引入新抽象层**。

**为什么不引入"层级 Strategy"**：曾考虑为 echarts 子类型再做一层 `SubtypeDescriptor`（每个 series.type 一个 strategy）。否决原因：(a) 各子类型差异仅体现在 prompt 示例上，validator 与 format 共享；(b) 子类型增删频次高于顶层类型增删，多一层抽象会让新增 echarts 子类型的成本上升；(c) Non-Duty #2 已明确"不支持运行时新增子类型"。一层 Strategy + 一个常量表足够。

### 2. Composition over Inheritance（前端渲染器）
`EChartsRenderer` 与 `MermaidRenderer` / `ReactFlowRenderer` 共享 `DiagramExportHandle` 接口，但**不抽象基类**。三者内部实现差异极大（echarts 用 imperative API、reactflow 用声明式 hook、mermaid 用 SVG 字符串），抽象基类会强行同质化。`DiagramViewer` 用 `format` switch 分发足够清晰。

### 3. Adapter（InlinePreviewToolShim）
`preview_diagram_inline` 是适配 `/diagram` skill 的"强工具调用约束"与"echarts 内联输出意图"的虚 tool——把一种本不属于工具调用语义的行为（输出文本围栏）显式映射为一次工具调用，用最小破坏维持现有约束。

该 tool 是 echarts-only：若 `diagram_type != "echarts"`，直接返回 `preview_diagram_inline_invalid_type`，并引导 LLM 对 mindmap / flowchart / sequence 使用 `create_diagram`。若类型正确，则复用 `validate_echarts_option`，避免非法 JSON 在最终回复里被前端反复尝试渲染。

**为什么不直接放宽 `force_first_tool_call`**：放宽会导致"`/diagram` 触发但 LLM 什么都没做"成为合法状态，破坏 skill 的可观测性（现有约束保障"调用了 /diagram 就一定有图表产物"）。Shim tool 保留这个不变量。

### 4. Decorator-like Placeholder Injection（前端内联管线）
现有 `MarkdownViewer` 走 HTML 字符串 + `dangerouslySetInnerHTML`，无法直接塞 React 组件。**不切换**到 react-markdown（Non-Duty #1），而是在 opt-in 管线两端叠加：
- 编译端：当 `enableInlineCharts=true` 时，在 HTML 字符串中保留一个 `<div data-chart-placeholder data-chart-type="echarts" data-payload-id="...">` 占位。
- 渲染端：渲染完成后 `querySelectorAll('[data-chart-placeholder][data-chart-type="echarts"]')`，对每个挂 `createRoot` + 内联 ECharts 卡片。

这种"装饰式增量"避免了重构现有 chunking / IntersectionObserver / katex / highlight.js 路径。代价是占位符与原文本的解耦需要在 store / Map 中维护映射；这个代价由 `data-model.md` 中的 `InlineChartPayloadRegistry` 概念吸收。默认关闭是重要约束：Reader、Video、普通聊天、非本轮 `/diagram` 回复都不会受影响。

### 5. 不使用 Observer / Pub-Sub
内联图表卡片与会话状态弱耦合——"保存到 Studio"是一次性事件，不需要订阅持续更新。保存成功后只显示本卡片的轻量状态，不建立与新 diagram_id 的长期绑定。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
newbee_notebook/
└── skills/diagram/
    ├── registry.py                   # 扩展点：注册 echarts Descriptor、子类型白名单、
    │                                 #         _render_echarts_section、_ECHARTS_SUBTYPE_EXAMPLES
    ├── tools.py                      # 新增 _build_preview_diagram_inline_tool()
    └── provider.py                   # 在 build_manifest 中挂载新 tool；其余不动

newbee_notebook/
└── api/
    ├── routers/diagrams.py           # 新增 POST /api/v1/diagrams
    └── models/diagram_models.py      # 新增 CreateDiagramRequest

newbee_notebook/
└── application/services/
    ├── diagram_service.py            # echarts_option content-type + create 失败清理
    └── export_service.py             # echarts_option 导出 .json

newbee_notebook/
└── scripts/db/
    ├── init-postgres.sql             # format CHECK 加入 'echarts_option'
    └── migrations/
        └── batchN_diagrams_echarts.sql  # 新增 idempotent 迁移

frontend/src/
├── components/studio/
│   ├── diagram-viewer.tsx            # 新增 format === "echarts_option" 分支
│   └── echarts-renderer.tsx         # 新增：薄 React 包装，实现 DiagramExportHandle
├── components/chat/
│   └── inline-chart-card.tsx         # 新增：内联图表卡片 + 保存 icon button
├── components/reader/
│   ├── markdown-pipeline.ts          # opt-in 编译阶段：echarts 围栏 → 占位符
│   └── markdown-viewer.tsx           # 渲染后：扫描占位符、createRoot 挂 React
├── lib/api/
│   └── diagrams.ts                   # 新增 createDiagram 客户端方法
├── lib/diagram/
│   └── echarts-modules.ts            # 集中 echarts.use([...])；镜像后端白名单
└── lib/i18n/
    └── strings.ts                    # 新增 echarts 相关 zh / en 文案

docs/frontend-v3/echarts/             # 本模块设计文档集
```

### 对外稳定的接口

- 后端：`DIAGRAM_TYPE_REGISTRY["echarts"].validator` 调用约定不变；新增 `POST /api/v1/diagrams` 复用 `DiagramService.create_diagram`，且由 descriptor 推导 `format`。
- 前端：`DiagramExportHandle` 接口（`exportImage(filename)`）；`DiagramViewer` 的 `(diagram, content)` 入参不变。

### 内部实现（不对外稳定）

- echarts 子类型白名单、子类型 prompt 示例片段、占位符标记格式、`InlineChartPayloadRegistry` 内部结构、内联保存卡片的局部状态——这些可以在后续批次重构而不影响调用方。

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 放弃严格 schema 校验，换灵活性
- **被放弃方案**：为每个 series.type 写 Pydantic schema，严格校验所有字段。
- **当前方案代价**：LLM 输出诡异字段（如拼错 `xAxis` → `xaxis`）不会被后端拦截，运行时由 ECharts 自身宽容处理（多数情况下"画出来但样式异常"）；用户视觉发现错误后回写 prompt。
- **理由**：ECharts schema 巨大、可选字段多、社区文档本身鼓励变化；严格 schema 维护成本永久存在，而轻量校验 + prompt 引导覆盖 95% 常见错误。

### 2. 放弃完整 markdown 管线重写，换实现收敛
- **被放弃方案**：换成 react-markdown / 完全 AST 驱动的 React 管线。
- **当前方案代价**：占位符识别 + `createRoot` 注入是一种"侵入式"做法；占位符与原文本通过 store / Map 关联，多一层间接。Hydration 边界要小心（避免 SSR 时尝试渲染浏览器 only 的 echarts）。
- **理由**：现有 markdown 管线（chunking + IntersectionObserver + highlight.js + katex）经过多次调优，重写风险远大于增量。

### 3. 放弃运行时拆 chunk，换接入简单
- **被放弃方案**：`dynamic import('echarts')`，Next.js 自动拆分独立 chunk。
- **当前方案代价**：首屏 bundle 增加约 200-400KB（按需注册后的体积估算），但 ECharts 仅在打开包含图表的会话或 Studio 详情页时才真正初始化。
- **理由**：第一次接入优先简单；bundle size 监控放到 `non-functional.md` 的暂缓项，达到阈值再单独立项做 splitting。

### 4. 放弃前端运行时白名单（动态注册），换三端一致性
- **被放弃方案**：让前端读取后端白名单的 API，运行时按需 `echarts.use(...)`。
- **当前方案代价**：新增子类型需要同步改三处（后端常量、前端 `echarts-modules.ts`、prompt 示例）；用一致性测试兜底。
- **理由**：echarts 的 `use()` 在模块加载时执行最简单可靠；运行时动态注册需要处理"图表组件还没注册就开始 setOption"等竞态，复杂度不值。

### 5. 接受 `preview_diagram_inline` 是一个"语义稀薄但有校验价值"的工具
- 该工具不做读写，仅以 echarts-only 预览校验满足 `force_first_tool_call`。这是 Adapter 的代价。
- 它的业务价值仅限于"允许一次性内联预览且提前拦截明显非法 option"；文档中明确将其归类为"流程兼容层（Shim）"，避免后续维护者把它扩展成通用预览工具。

---

## 五、自检结论

- 每个子组件存在的理由都可追溯到 Duties 或既有架构（registry / DiagramViewer）。
- 不存在为"优雅"而新增的抽象层（如层级 Strategy、渲染器基类）。
- 与现有 mindmap / flowchart / sequence 的架构对称——新增类型遵循"注册 Descriptor + 写 validator + 写 prompt + 写 renderer"四步，无引入新概念。
