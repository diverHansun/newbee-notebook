# goals-duty.md — echarts

## 模块定位（一句话）

为 `/diagram` skill 补齐"数据图表（ECharts 家族）"这一维度，并把图表内容打通到**会话内联渲染**——使用户在 `/diagram` 会话中既可以"持久化到 Studio 复用"，也可以"在当前对话里临时画一张"。

---

## 一、Design Goals（设计目标）

1. **类型可扩展**：以最小改动接入 ECharts 家族——使用单一 `diagram_type="echarts"`，通过 `series.type` 区分子类型；后续新增子类型只改动一处白名单与 prompt 示例片段，不动 registry 抽象层。

2. **注入边界稳定**：echarts 的 agent 能力仅在 `/diagram` 触发后通过 system_prompt 注入，与现有 mindmap / flowchart / sequence 注入模型完全一致；不污染普通对话上下文。

3. **渲染路径统一**：Studio 详情页与会话内联使用同一个 `EChartsRenderer`，仅外层容器与生命周期不同；导出 PNG、深浅色主题、错误回落策略由组件内部统一处理。

4. **校验宽松、prompt 严格**：后端 validator 只做轻量浅校验（JSON 合法 / 顶层 object / series 非空 / 每个 `series[i].type` 在白名单内）；严格性靠 agent system prompt 中按子类型分章节的示例去引导。这是 ECharts schema 的灵活性所要求的工程妥协。

5. **内联渲染管线收敛**：会话内联渲染只对本轮 `/diagram` 请求对应的 assistant 回复启用，首版仅识别 ` ```echarts ``` ` 围栏；mermaid / reactflow 图仍按既有路径持久化到 Studio 后查看。

6. **持久化由用户主动触发**：内联图表卡片提供小型 icon button 作为"保存到 Studio"动作；不在 LLM 默认行为里强制写库，避免污染 Studio 列表，也避免一次性会话中产生的图表占据持久化资源。

---

## 二、Duties（职责）

本批次（echarts）需完成且仅完成以下职责：

1. **后端 registry 扩展**
   - 在 `DIAGRAM_TYPE_REGISTRY` 中注册 `echarts` `DiagramTypeDescriptor`。
   - 新增独立常量 `ECHARTS_SERIES_TYPE_WHITELIST`（不污染通用 `DiagramTypeDescriptor` 接口），首批覆盖 10+ 子类型（bar / line / pie / scatter / effectScatter / radar / heatmap / treemap / sunburst / sankey / gauge / funnel / candlestick / boxplot）。
   - 新增 `DiagramFormat` 字面量 `echarts_option`。

2. **后端 validator 实现**
   - `validate_echarts_option(content: str) -> None`，沿用现有 `_raise_validation_error` 诊断格式。
   - 校验路径：非空 → 无 markdown 围栏 → JSON 合法 → 顶层 object → `series` 是非空 list → 每个 `series[i]` 是 object 且 `type` ∈ 白名单。

3. **后端 agent system prompt 扩展**
   - 在 `_PROMPT_ORDER` 末尾追加 `"echarts"`。
   - 新增 `_render_echarts_section()`：包含 echarts 总规则段，再按子类型展开"最小可用 option JSON 示例"片段。子类型示例片段由 `_ECHARTS_SUBTYPE_EXAMPLES: dict[str, str]` 集中维护。
   - 补充 echarts intent hints，使 `"画一个柱状图"` / `"line chart"` 等中文与英文图表意图可由 `infer_diagram_type_from_prompt` 命中 `"echarts"`。
   - 该 prompt 仍由 `build_diagram_system_prompt()` 拼装；注入策略不变（仍由 /diagram skill provider 在触发后注入）。

4. **后端 skill provider 流程兼容**
   - `/diagram` 当前 manifest 设 `force_first_tool_call=True` 且 `required_tool_call_before_response` 包含 `create_diagram` 等操作工具。本批次需要让 LLM 在"echarts 内联输出"路径下不被强制走 create_diagram。
   - 决策：新增 echarts-only 虚 tool `preview_diagram_inline`，纳入 `required_tool_call_before_response` 名单。该 tool 不写库，但必须调用 `validate_echarts_option(content)`；校验通过后 LLM 才允许在最终响应中输出 ` ```echarts ``` ` 围栏。
   - 若该 tool 返回 `preview_diagram_inline_invalid_type` / `diagram_validation_failed` 等错误，prompt 与测试必须约束 LLM 不输出 ` ```echarts ``` ` 围栏，而是修正后重试或改走持久化 `create_diagram`。

5. **数据库迁移**
   - 修改 `diagrams.format` 的 CHECK 约束，加入 `'echarts_option'`。
   - 提供一份 idempotent 的迁移脚本 `batchN_diagrams_echarts.sql`：通过 `pg_constraint` 探测并移除既有 format CHECK（包括 `ck_diagrams_format` 与历史自动命名约束），再重新添加包含 `echarts_option` 的约束；并同步更新 `init-postgres.sql`。
   - 同步更新 SQLAlchemy `DiagramModel` 的 `ck_diagrams_format`、内存初始化脚本 `newbee_notebook/infrastructure/persistence/database.py`，以及相关 smoke test 断言。
   - `diagram_type`（无 CHECK）、`content_path`（TEXT，存 JSON 文件路径）、`document_ids`、`node_positions`（保持 NULL）均复用，不动列结构。

6. **后端 diagrams REST 创建接口**
   - 新增 `POST /api/v1/diagrams`，供内联图表的"保存到 Studio"动作调用。
   - 新增 `CreateDiagramRequest`：请求体包含必填 `notebook_id`、必填 `title`、必填 `diagram_type`、必填 `content`、可选 `document_ids`；**不接收 `format`**，`format` 仍由后端 `DiagramTypeDescriptor.output_format` 推导。
   - 接口复用 `DiagramService.create_diagram`，因此与 LLM tool 创建路径共享 validator、文件存储、document scope 校验和返回实体格式。
   - 成功固定返回 `201` + `DiagramResponse`。请求模型错误返回 FastAPI `422`；`DiagramValidationError` / `DiagramTypeNotFoundError` / document scope `ValueError` 返回 `400`；DB FK / `IntegrityError` 必须显式映射为非 500 错误。
   - 服务一致性同步：`DiagramService._content_type_for_format("echarts_option")` 返回 `application/json`；notebook 导出时 `export_service._diagram_extension("echarts_option")` 返回 `.json`；若 content 文件已写入但 repository create 失败，必须清理 orphan content 文件后再抛出错误。

7. **前端 EChartsRenderer**
   - 新建 `frontend/src/components/studio/echarts-renderer.tsx`，`forwardRef<DiagramExportHandle>`。
   - 引入 `echarts/core` + 按子类型白名单注册 chart / component（与后端白名单镜像）。
   - 实现 init / setOption / resize / dispose 生命周期；PNG 导出走 `echartsInstance.getDataURL`。
   - 支持深浅色主题（与现有 mermaid / reactflow 一致的方式订阅 `useTheme`）。
   - Studio 详情页沿用现有卡片结构与导出 icon，ECharts 渲染区域借鉴当前 mindmap 详情卡片的浅色背景、细边框、圆角与自适应布局。

8. **前端 DiagramViewer 分发**
   - 在 `frontend/src/components/studio/diagram-viewer.tsx` 中新增 `diagram.format === "echarts_option"` 分支，路由到 `EChartsRenderer`。

9. **前端 Studio 列表与详情页适配**
   - `getDiagramTypeLabel` 增加 echarts 标签；Studio diagrams 列表能显示 echarts 类型徽章。
   - 详情页"导出 PNG"按钮复用 `DiagramExportHandle` 接口（已是 ref-based 抽象，无需改动调用方）。
   - 列表卡片不做缩略图，保持当前 title / chip / updated_at / 复制 ID 的信息密度。

10. **前端会话内联管线**
   - 在 `markdown-pipeline` / `MarkdownViewer` 上叠加 opt-in 的"占位符识别 + React 注入"层。
   - `MarkdownViewer` 新增 `enableInlineCharts?: boolean`，默认 `false`；只有"用户本轮消息以 `/diagram` 开头"对应的 assistant 回复传 `true`。
   - 仅把 ` ```echarts ... ``` ` 在编译阶段替换为占位符元素（保留原文本于 attribute / 旁路 store）；` ```mermaid ``` ` 和 reactflow JSON 在会话中仍显示为普通代码块。
   - `MarkdownViewer` 渲染后扫描占位符，对每个使用 `createRoot` 挂载 `EChartsRenderer` 的内联卡片变体。
   - 处理流式半成品：JSON 不完整时显示 loading 占位 + 原始代码块。

11. **前端"保存到 Studio"动作**
    - 内联图表卡片右上角加保存 icon button；hover / `title` / `aria-label` 显示"保存到 Studio"，全部走 i18n。
    - 点击调用新增 `POST /api/v1/diagrams`（diagram_type="echarts", content=原始 JSON；不传 format）。
    - 成功后在卡片内用轻量状态标记显示"已保存"，不提供"打开 Studio"链接，当前也不替换会话内文本。
    - 失败时在卡片内显示错误文案并允许重试；不新增全局 toast 系统。

12. **i18n 完备**
    - 所有新增 UI 字符串（"保存到 Studio" icon tooltip / aria-label、"已保存"、加载/错误态文案、echarts 类型徽章标签、各子类型中文名）走 `uiStrings`，提供 zh / en 双值；不在组件内硬编码字面量。

13. **测试覆盖**
    - 后端：validator 单测（合法 / 各类非法）、registry 注册存在性与 intent hint 测试、agent system prompt 包含 echarts 章节断言、`preview_diagram_inline` tool 契约测试（含 error 后不得输出 fence 的 e2e 约束）、`POST /api/v1/diagrams` contract 测试、DB CHECK smoke 测试、content-type / 导出扩展名 / create 失败清理测试。
    - 前端：`EChartsRenderer` 渲染与导出测试（mock echarts core）、`DiagramViewer` 分支测试、请求级 `enableInlineCharts` 识别测试、内联 echarts 占位符识别与 React 注入测试、"保存到 Studio" 调用 API 测试。

---

## 三、Non-Duties（刻意排除）

以下功能虽然相关，但**不在本批次范围内**：

1. **不重写整个 markdown 渲染管线**
   - 保留现有 `dangerouslySetInnerHTML` + 增量加载（chunking + IntersectionObserver），只在其上叠加"占位符识别 + React 注入"层。
   - 不切换到 react-markdown 或完整 AST → React 管线，避免大重构。

2. **不支持运行时新增 echarts 子类型**
   - 子类型白名单是代码常量；新增类型走代码 PR，不通过配置或运行时注册。
   - 这与后端"白名单 → prompt 示例 → 前端按需注册"三处一致性是有意的。

3. **不做图表交互编辑**
   - Studio 内 echarts 仅"查看 + 导出 PNG"。
   - 不支持类似 mindmap 的节点拖拽、不支持表单式 option 编辑、不支持双向"图 ↔ JSON"编辑器。

4. **不做严格 Pydantic schema 校验**
   - ECharts option 结构极深且选项可选性高，严格 schema 的长期维护成本高于收益。
   - 严格性由 agent prompt 中的子类型示例承担，validator 只兜底"明显错误"。

5. **不在普通会话或非本轮 `/diagram` 回复中支持 echarts 围栏**
   - echarts agent 能力随 `/diagram` 注入；只有用户本轮消息以 `/diagram` 开头对应的 assistant 回复会启用 `enableInlineCharts`。
   - 未启用时即便文本中出现 ` ```echarts ... ``` ` 围栏，前端也只渲染为普通代码块。
   - 这是为了维持 `/diagram` 触发模型的边界稳定（见 Design Goals #2）。

6. **不实现复杂 ECharts 特性的 prompt 引导**
   - 首版只覆盖单 series 的常见子类型；dataset、多 series 联动、visualMap、dataZoom 等高级特性不在引导范围内（LLM 输出能跑就行，但 prompt 不强制示例）。

7. **不引入 dynamic import 拆分 echarts chunk**
   - 第一次接入直接静态 import；bundle size 监控放到 non-functional.md 的暂缓项跟踪。
   - 若后续 bundle 过大再单独立项做 code splitting。

8. **不实现"内联图表自动持久化"或"对话粘贴图表 ID 回引用"**
   - "保存到 Studio" 是显式按钮动作，不自动绑定；保存后也不改写会话文本。
   - `[[diagram:xxx]]` 引用协议如未来需要，单独立项。

9. **不修改现有 reactflow / mermaid 的会话渲染语义**
   - reactflow / mermaid 继续通过 `create_diagram` 持久化，并在 Studio 列表与详情页显示。
   - 本批次不把 mermaid 围栏接入会话内联，也不重构 `MermaidRenderer` / `ReactFlowRenderer` 内部。

10. **不实现 echarts 多图联动 / dashboard 视图**
    - Studio diagram 详情页仍是单图视图，不引入"看板"概念。

---

## 四、与其他文档的关系

- 本文件是 `docs/frontend-v3/echarts/` 设计文档集的边界声明；后续 `architecture.md` / `data-model.md` / `dfd-interface.md` / `use-case.md` / `non-functional.md` / `test.md` 必须以本文件为前提。
- 若实施过程中发现需要超出 Duties 的能力，必须先回到本文件讨论调整，而不是在下游文档中"扩职责"。
