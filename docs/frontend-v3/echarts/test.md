# test.md — echarts

## 撰写前置确认

- `goals-duty.md` / `architecture.md` / `data-model.md` / `dfd-interface.md` / `use-case.md` / `non-functional.md` 已存在。
- 本模块属于混合原型（见 §一），各部分按 docs-plan 的"侧重速查表"分别确定测试重心。

---

## 一、Module Test Profile（模块测试档案）

### 模块原型判定（混合）

echarts 模块横跨多个性质的子组件，按 architecture.md §一 的子组件归类：

| 子组件 | 原型 | 主要测试类型 | 测试归属目录 |
|---|---|---|---|
| `EChartsTypeDescriptor` 注册 | 纯逻辑 | unit | `newbee_notebook/tests/unit/skills/diagram/` |
| `validate_echarts_option` | 纯逻辑 | unit | 同上 |
| `EChartsPromptComposer`（`_render_echarts_section` + 子类型示例） | 纯逻辑 | unit | 同上 |
| `preview_diagram_inline` tool | 桥接 / 适配 | unit + contract | `newbee_notebook/tests/unit/skills/diagram/` |
| `POST /api/v1/diagrams` 创建接口 | API contract | contract | `newbee_notebook/tests/contract/api/` |
| DB 迁移 + `format` CHECK 扩展 | 基础设施 | smoke | `newbee_notebook/tests/smoke/` |
| `DiagramService` / `export_service` echarts 辅助一致性 | 应用服务 | unit | `newbee_notebook/tests/unit/application/services/` |
| `EChartsRenderer`（含 `echarts-modules` 注册） | 纯逻辑（UI 渲染） | unit | `frontend/src/components/studio/echarts-renderer.test.tsx` |
| `DiagramViewer` 分发分支 | 纯逻辑 | unit | `frontend/src/components/studio/diagram-viewer.test.tsx`（扩展既有） |
| 请求级内联管线（echarts 占位符 + React 注入） | 服务编排（前端） | unit | `frontend/src/components/reader/markdown-viewer.test.tsx`（扩展既有） |
| `SaveToStudioAction` | 桥接 / 适配 | unit + contract | `frontend/src/components/chat/inline-chart-card.test.tsx` |
| 白名单三处一致性 | 纯逻辑 | unit | `newbee_notebook/tests/unit/skills/diagram/test_registry.py`（扩展） |

### Mock 边界

- **后端 unit 测试**：`DiagramService` 在测试 validator / registry / prompt 时不需要 mock（这些都是纯函数）；测 `preview_diagram_inline` tool 时也无需 mock（它本身无 IO）。
- **后端 smoke 测试**：迁移脚本对真实 PostgreSQL 执行，复用既有 `test_db_init_script.py` 框架。
- **前端**：`echarts` 包整体 mock（`vi.mock("echarts/core")`）；`echarts-modules.ts` 中的 `echarts.use(...)` 在测试环境无副作用即可。`SaveToStudioAction` mock REST 客户端。

### 主要测试类型

unit 为主、smoke 兜底基础设施、contract 兜底 `preview_diagram_inline` 与 `SaveToStudioAction` 的对外承诺。

---

## 二、Test Scope（测试范围）

### 覆盖

- echarts `DiagramTypeDescriptor` 注册存在性（registry 表里能查到）。
- `validate_echarts_option` 的合法 / 各类非法路径。
- `build_diagram_system_prompt()` 输出包含 echarts 章节且子类型示例 keys 等于白名单。
- `preview_diagram_inline` tool 的 echarts-only 输入处理、validator 调用、输出格式、无副作用属性。
- `POST /api/v1/diagrams` 创建接口不接收 `format`，复用 `DiagramService.create_diagram` 并固定以 `201` 返回 `DiagramResponse`。
- DB 迁移幂等执行 + `format` 列接受 `'echarts_option'`、拒绝白名单外值。
- `echarts_option` 的 content-type、导出扩展名与 create 失败清理逻辑正确。
- `EChartsRenderer` 在 mount / setOption / 主题切换 / unmount / 导出 PNG 各阶段调用正确的 echarts API。
- `DiagramViewer` 在 `format === "echarts_option"` 时路由到 `EChartsRenderer`。
- 内联管线只在 `enableInlineCharts=true` 时把 echarts 围栏识别为占位符；渲染后挂对应 React 组件。
- `SaveToStudioAction` 调用 REST 客户端，成功后更新卡片状态，失败时不二次调用。
- 白名单三处镜像严格相等。

### 不覆盖

- ECharts 内部渲染正确性（柱子坐标对不对、轴标签好不好看）——属于 echarts 库自身责任。
- LLM 实际输出质量（prompt 是否引导出合理图表）——属于 LLM eval 范畴，不在单测覆盖。
- 跨浏览器视觉回归——非本模块测试范畴。
- markdown 管线现有 chunking / katex / highlight.js 已覆盖的行为——本模块测试不重复。

---

## 三、Critical Scenarios（关键场景）

### S1：validator 正常路径

- 输入：完整合法的 ECharts option JSON（含 series + series[].type ∈ 白名单）。
- 预期：函数静默返回，无异常。
- 覆盖每种白名单子类型至少一个最小可用样本（bar / line / pie / scatter / radar / heatmap / treemap / sunburst / sankey / gauge / funnel / candlestick / boxplot / effectScatter）。
- 覆盖多 series 样本：每个 `series[i].type` 都在白名单内时通过。

### S2：validator 异常路径

| 输入特征 | 预期错误类别（category）|
|---|---|
| 空字符串 / 仅空白 | structure |
| 含 ` ``` ` markdown 围栏 | structure |
| JSON 不可 parse | structure |
| 顶层是数组而非 object | structure |
| 缺 `series` 键 | structure |
| `series` 为空数组 | structure |
| `series` 不是数组 | schema |
| `series[i]` 不是 object | schema |
| `series[i]` 缺 `type` 字段 | schema |
| `series[i].type` 不在白名单（如 `"unknown_chart"`） | schema |

每条用例必须断言 4 段诊断格式（category / detail / location / suggestion）齐全。

### S3：registry / prompt 集成

- `DIAGRAM_TYPE_REGISTRY["echarts"]` 存在且 `output_format == "echarts_option"`、`validator is validate_echarts_option`。
- `build_diagram_system_prompt()` 输出文本包含 "=== echarts rules ===" 且包含每个白名单子类型名称。
- `_ECHARTS_SUBTYPE_EXAMPLES.keys() == ECHARTS_SERIES_TYPE_WHITELIST`（白名单一致性单测）。
- `infer_diagram_type_from_prompt("画一个柱状图")` 等中文 / 英文 intent_hints 命中能返回 `"echarts"`。

### S4：`preview_diagram_inline` tool

- 输入 `diagram_type="echarts"` 且 content 合法 → 返回 `ToolCallResult`，content 是确认文本，metadata 含 `diagram_type` 标记。
- 输入非 echarts 类型（如 `"flowchart"`）→ 返回 `preview_diagram_inline_invalid_type`，不允许会话内联 mermaid/reactflow。
- 输入 echarts 但 content 非法 → 返回 `diagram_validation_failed`，错误信息沿用 validator 诊断。
- tool 返回错误后，端到端用例必须断言最终 assistant 文本不包含 ` ```echarts ` 围栏；LLM 应修正后重试或改走持久化路径。
- 不调用 `DiagramService`（无 IO 副作用断言：service 在测试中是真实实例时统计调用次数 == 0）。
- 列入 `permission_required` 与否、`tool_class`、`risk_level` 满足"只读 / 安全"约束。

### S4.5：`POST /api/v1/diagrams` 创建接口

- 请求 body：必填 `notebook_id`、必填 `title`、必填 `diagram_type`、必填 `content`、可选 `document_ids`。
- 明确不包含 `format`；测试断言前端/合同示例不传 `format`。
- service 成功 → 201 返回 `DiagramResponse`，其中 `format` 来自 descriptor。
- service 抛 `DiagramValidationError` → 400，错误体包含 `diagram_validation_failed` 信息。
- service 抛 `DiagramTypeNotFoundError` → 400，错误体包含类型不存在信息。
- service 抛 document scope `ValueError` → 400，错误体包含 document scope 诊断。
- DB FK / `IntegrityError` → 非 500 错误（建议 400 + `invalid_reference`）。
- 请求缺少 `title` / `content` 等必填字段 → 422，由 FastAPI 请求模型校验负责。

### S5：DB 迁移（smoke）

- 在干净库执行 `batchN_diagrams_echarts.sql` → `format` CHECK 允许 `echarts_option`。
- 重复执行 → 幂等不报错。
- 迁移脚本通过 `pg_constraint` 探测并替换既有 format CHECK，覆盖 `ck_diagrams_format` 与历史自动命名约束。
- 已有 `reactflow_json` / `mermaid` 行不受影响。
- 尝试插入 `format='unknown'` 行被 CHECK 拒绝。

### S5.5：服务辅助一致性

- `_content_type_for_format("echarts_option") == "application/json"`，并覆盖 create / update content 两条写入路径。
- `export_service._diagram_extension("echarts_option") == ".json"`。
- `DiagramService.create_diagram` 在 storage save 成功、repository create 失败时调用 `storage.delete_file(content_path)` 清理刚写入的 content；清理失败只记录/吞掉 `FileNotFoundError`，原始 create 错误继续抛出。

### S6：`EChartsRenderer` 渲染生命周期

- Mount 时调用 `echarts.init(container)` 且 `setOption(JSON.parse(content))`。
- content 变更触发 `setOption` 而非重新 init。
- unmount 时调用 `instance.dispose()`。
- 容器 resize 触发 `instance.resize()`。
- `exportImage(filename)` 调用 `instance.getDataURL` 并通过 file-saver 落盘。
- `JSON.parse` 失败时退化为 `<pre>` 而非抛错。
- 主题切换时 setOption 被再次调用，且 option 携带主题相关 overlay。

### S7：`DiagramViewer` 分支

- `format === "echarts_option"` 时挂载 `EChartsRenderer`（mock 后断言 props）。
- `format === "mermaid"` / `"reactflow_json"` 时分别挂载现有渲染器，行为与既有测试一致。
- 未知 `format` 退化为 `<pre>`（与现有 default 分支一致）。

### S8：请求级内联管线占位符与挂载

- `enableInlineCharts=false` 时，输入含 ` ```echarts {...}``` ` 围栏的 markdown，输出仍是普通代码块。
- `enableInlineCharts=true` 时，输入含 ` ```echarts {...}``` ` 围栏的 markdown，编译后 HTML 含 `[data-chart-placeholder][data-chart-type="echarts"]` 元素，`InlineChartPayloadRegistry` 中能查到对应 payload。
- 渲染后 effect 在占位符上挂 `EChartsRenderer`（mock 后断言 props 含正确 `rawContent`）。
- ` ```mermaid``` ` 围栏即使在 `enableInlineCharts=true` 时也保持普通代码块，不挂 `MermaidRenderer`。
- 流式中途（JSON 未闭合）时 placeholder 存在但 `EChartsRenderer` 显示 loading；完整后正常渲染。
- `MarkdownViewer` unmount 时清理 React roots 与 registry 条目。

### S9：`SaveToStudioAction` 行为

- 点击保存 icon button 触发 REST 调用，body 包含正确 `notebook_id` / `diagram_type` / `content` / `title` / `document_ids`，且不包含 `format`。
- icon button 的 hover 文案、`title`、`aria-label` 均来自 `uiStrings`。
- inflight 期间按钮 disabled；成功后卡片显示已保存状态；失败后卡片显示后端错误信息。
- 双击不会触发两次 REST 调用。

### S10：i18n 完备

- 所有新增 UI 字符串走 `uiStrings`，断言 zh / en 两个 key 都存在且非空。
- 关键文案 key 列出：`saveToStudio` / `saveToStudioSuccess` / `saveToStudioFailed` / `chartTypeEcharts` / 各子类型中文名 / loading / parseError。

---

## 四、Contract Specification（契约规约）

### `preview_diagram_inline` tool 契约

- **入参**：
  - `diagram_type: string`（必填，只接受 `"echarts"`）。
  - `content: string`（必填，原样回 echo）。
- **返回**：
  - 成功：`ToolCallResult(content=<human-readable confirmation>, metadata={"diagram_type": "echarts"})`。
  - 失败：缺参返回 `preview_diagram_inline_invalid_args`；类型非 echarts 返回 `preview_diagram_inline_invalid_type`；validator 失败返回 `diagram_validation_failed`。
- **副作用承诺**：不读库、不写库、不调用任何 `DiagramService` 方法。
- **权限分类**：`tool_class=READ`，`risk_level=SAFE`。
- **满足 `/diagram` skill 双约束**：该 tool **必须**被纳入 `required_tool_call_before_response` 名单（与 `DIAGRAM_OPERATION_TOOLS` 并集），使内联路径下 LLM 只调用 `preview_diagram_inline` 就能合法结束响应；同时它也算作 `force_first_tool_call` 的有效首调用。prompt 中明确允许"成功调用此 tool 后直接输出 ```echarts``` 围栏并结束响应"；若返回错误，prompt 与 e2e 必须阻止输出 echarts 围栏。

### `SaveToStudioAction` → `POST /api/v1/diagrams` 调用契约（前端侧）

- **请求 body**：
  - `notebook_id: string`
  - `diagram_type: "echarts"`
  - `content: <rawContent string>`
  - `title: string`（前端派生：优先 `option.title.text`，回落"未命名 ECharts 图表"+ 时间戳）
  - `document_ids: []`（当前不绑定文档；未来可扩展）
  - 不允许传 `format`；后端根据 descriptor 推导 `format="echarts_option"`。
- **成功响应**：201 + `DiagramResponse`（包含 `diagram_id`、`format="echarts_option"` 等字段）。
- **失败响应**：
  - 400 + `{ code: "diagram_validation_failed", detail: "..." }` → 卡片内显示 `detail`。
  - 400 + `{ code: "invalid_diagram_type" | "invalid_reference", detail: "..." }` → 卡片内显示 `detail`。
  - 422 → 请求模型错误，通常代表前端构造请求 bug。
  - 5xx → 卡片内显示通用错误，提示稍后重试。
- **前端不变量**：保存 icon button 在 inflight 期间 disabled；同一 `placeholderId` 不会触发多次 in-flight。

---

## 五、Integration Points（集成点测试）

### IP1：echarts 模块加载

- 与 `echarts/core` 的交互：测试通过 `vi.mock("echarts/core")` 隔离；断言 `use([...])` 被以正确白名单调用。
- echarts 包加载失败的退化路径在 `EChartsRenderer` 内部处理（已在 S6 覆盖），不进 integration test。

### IP2：DiagramService 集成（持久化路径）

- 由既有 `test_diagram_service.py` 等单测覆盖创建 / 更新 / 删除流程；本模块只**追加** echarts format 的 happy-path 用例（不重复测 service 内部逻辑）。
- 失败注入：validator 抛错时 service 是否正确返回 `DiagramValidationError`（既有覆盖，echarts 沿用）。
- 辅助服务：追加 content-type、导出扩展名、repository create 失败后 storage cleanup 的单测。

### IP3：DiagramSkillProvider 集成

- `provider.build_manifest()` 输出包含 `preview_diagram_inline` tool。
- `required_tool_call_before_response` 名单**包含** `preview_diagram_inline`（与既有 `DIAGRAM_OPERATION_TOOLS` 并集）——这是内联路径合法结束响应的必要前提。
- `force_first_tool_call=True` 保持不变。
- system_prompt 包含 echarts 章节（来自 `build_diagram_system_prompt()`）。
- 后端 e2e：模拟 `preview_diagram_inline` 返回错误的路径，最终 assistant 文本不得包含 ` ```echarts ` 围栏。

### IP4：markdown 渲染管线集成

- 现有 `MarkdownViewer` 行为（chunking / 增量加载 / katex / highlight.js）在引入占位符层后**不退化**——既有 `markdown-viewer.test.tsx` 全部通过。
- 新增 echarts chart placeholder 路径单独覆盖（S8）。

### IP5：Studio diagrams hook 集成

- `useDiagrams` 返回的列表中能正确显示 echarts diagram（title、type label、updated_at）；这部分由 `studio-panel` 既有测试扩展 echarts case 覆盖。

---

## 六、Verification Strategy（验证策略）

### 6.1 测试运行环境

- **后端单测**：`pytest` 默认环境，无需 DB。
- **后端 smoke**：需要 Docker PostgreSQL（沿用 `tests/smoke/test_db_init_script.py` 既有方式）。
- **前端单测**：`vitest`；jsdom 环境；`echarts` 库 mock；`canvas`/PNG 导出相关用 stub。

### 6.2 自动化 vs 人工

- **自动化**：以上全部 Critical Scenarios + Contract + Integration 用例都在 CI 中执行。
- **人工抽检**：每次 LLM-facing prompt 调整后，建议在本地用 `/diagram` 跑 3-5 个典型 case（柱 / 线 / 饼 / 散点 / 雷达），目测确认图表语义合理。这部分不进 CI。

### 6.3 关键回归测试

- 白名单三处一致性测试（IP3 + S3）是首要回归保险——任何加子类型的 PR 必须通过。
- `DiagramViewer` 分支测试是第二保险——确保 echarts 不破坏现有 mindmap / flowchart / sequence 渲染。

### 6.4 不进 CI 的验证

- echarts bundle 体积监控：构建产物报告由 release 流程人工查看；阈值触发条件已在 non-functional §四.1 列明。
- LLM 实际输出质量评估：由 `/diagram` 整体 eval 流程承担，不在 echarts 模块测试范畴。

---

## 七、自检结论

- 已声明混合原型并分子组件标注侧重。
- Critical Scenarios 10 类覆盖了 dfd-interface.md 中所有数据流的关键节点与 use-case.md 中所有失败点。
- 桥接子组件（`preview_diagram_inline`、`SaveToStudioAction`）有明确 Contract Specification。
- 基础设施部分（DB 迁移）单独标 smoke 路径并说明幂等性验证。
- 不引入"覆盖率"导向的描述；每个测试都指向一个具体不变量。
