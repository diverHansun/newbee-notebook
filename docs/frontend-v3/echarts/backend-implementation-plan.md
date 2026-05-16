# backend-implementation-plan.md — echarts

## 目标

先完成 echarts 模块的后端可运行闭环：registry / validator / prompt / preview tool / provider 约束 / diagrams REST 创建接口 / DB format 约束 / 后端测试。前端组件与 CSS 不在本阶段实施；因此本阶段只验证 tool 与持久化闭环，不把 raw ` ```echarts ``` ` 围栏当作完整用户体验。

---

## 一、实施边界

### 本阶段实施

1. `DIAGRAM_TYPE_REGISTRY["echarts"]` 与 `echarts_option` descriptor。
2. `ECHARTS_SERIES_TYPE_WHITELIST` 14 个子类型：
   `bar / line / pie / scatter / effectScatter / radar / heatmap / treemap / sunburst / sankey / gauge / funnel / candlestick / boxplot`。
3. `validate_echarts_option(content)`：非空、无 markdown 围栏、JSON object、`series` 非空 list、每个 `series[i]` 是 object 且 `type` 在白名单内。
4. `build_diagram_system_prompt()` 增加 echarts 章节与 intent hints；prompt 引导 LLM 在临时查看时调用 `preview_diagram_inline`，仅在 tool 成功后输出 ` ```echarts ``` `，tool 错误时修正重试或改走持久化。
5. `_build_preview_diagram_inline_tool()`：echarts-only，调用 validator，不读写库。
6. `DiagramSkillProvider` 挂载新 tool，并把它纳入 `required_tool_call_before_response`。
7. `POST /api/v1/diagrams`：新增 REST 创建接口，请求体不接受 `format`，复用 `DiagramService.create_diagram`，成功固定返回 `201` + `DiagramResponse`。
8. DB CHECK 约束加入 `echarts_option`：migration、`init-postgres.sql`、SQLAlchemy model、内存初始化 SQL；migration 通过 `pg_constraint` 幂等替换既有 format CHECK。
9. `echarts_option` 辅助一致性：storage content-type 为 `application/json`，export 扩展名为 `.json`，create 失败清理 orphan content 文件。
10. 后端单测、contract 测试、smoke/e2e 验证。

### 本阶段不实施

1. 前端 `EChartsRenderer`、内联卡片、MarkdownViewer 注入、CSS polish。
2. 前端 `createDiagram` client/hook，以及 `DiagramFormat` TypeScript 字面量把 `"echarts_option"` 纳入类型集合。
3. 全局 toast 或 Studio UI 改造。
4. mermaid / reactflow 会话内联渲染。

---

## 二、TDD 任务顺序

### Task 1：validator 与 registry

**测试先行**
- 修改 `newbee_notebook/tests/unit/skills/diagram/test_registry.py`。
- 先添加：
  - 所有 14 个子类型最小合法 option 都通过。
  - 多 series 合法样本通过。
  - 空内容、markdown 围栏、非法 JSON、顶层数组、缺 series、空 series、series 非 list、series item 非 object、缺 type、未知 type 都抛 `DiagramValidationError`。
  - `DIAGRAM_TYPE_REGISTRY["echarts"].output_format == "echarts_option"`。
  - `_ECHARTS_SUBTYPE_EXAMPLES.keys()` 与白名单一致。
  - `infer_diagram_type_from_prompt("画一个柱状图")` 与英文图表意图命中 `"echarts"`。

**实现**
- 修改 `newbee_notebook/skills/diagram/registry.py`。
- 增加白名单常量、validator、prompt 示例、descriptor、intent hints、`_PROMPT_ORDER` 中的 `"echarts"`。

### Task 2：preview tool 与 provider 约束

**测试先行**
- 修改 `newbee_notebook/tests/unit/skills/diagram/test_tools.py`。
- 先添加：
  - `preview_diagram_inline` 合法 echarts 返回 metadata。
  - 非 echarts 返回 `preview_diagram_inline_invalid_type`。
  - 非法 echarts content 返回 `diagram_validation_failed`。
  - preview tool 返回错误后，后端 e2e 断言最终 assistant 文本不包含 ` ```echarts ` 围栏。
  - provider tools 列表包含 `preview_diagram_inline`。
  - `required_tool_call_before_response` 包含 `preview_diagram_inline`，`force_first_tool_call=True` 保持不变。

**实现**
- 修改 `newbee_notebook/skills/diagram/tools.py` 和 `provider.py`。

### Task 3：REST 创建接口

**测试先行**
- 修改 `newbee_notebook/tests/contract/api/test_diagrams_router.py`。
- 先添加：
  - `POST /api/v1/diagrams` 调用 service.create_diagram，body 不含 `format`。
  - 成功返回 `201` + `DiagramResponse`。
  - `DiagramValidationError` 返回 400。
  - `DiagramTypeNotFoundError` 返回 400。
  - document scope `ValueError` 返回 400。
  - 请求模型缺少 `title` / `content` 等必填字段返回 422。
  - DB FK / `IntegrityError` 不冒泡为 500。

**实现**
- 修改 `newbee_notebook/api/models/diagram_models.py` 和 `newbee_notebook/api/routers/diagrams.py`。
- 新增 `CreateDiagramRequest`：`notebook_id`、`title`、`diagram_type`、`content` 必填，`document_ids` 默认空列表。

### Task 4：DB 约束与辅助服务一致性

**测试先行**
- 修改 `newbee_notebook/tests/smoke/test_db_init_script.py` 与相关 repository/model 断言。
- 先添加或更新：
  - `format IN ('reactflow_json', 'mermaid', 'echarts_option')`。
  - 新 migration 幂等存在性检查，并断言其使用 `pg_constraint` 替换既有 format CHECK。
  - `_content_type_for_format("echarts_option") == "application/json"`。
  - `_diagram_extension("echarts_option") == ".json"`。
  - repository create 失败时清理已写入 content。

**实现**
- 修改：
  - `newbee_notebook/scripts/db/migrations/batchN_diagrams_echarts.sql`
  - `newbee_notebook/scripts/db/init-postgres.sql`
  - `newbee_notebook/infrastructure/persistence/models.py`
  - `newbee_notebook/infrastructure/persistence/database.py`
  - `newbee_notebook/application/services/diagram_service.py` 中 `_content_type_for_format` 与 create 失败清理。
  - `newbee_notebook/application/services/export_service.py` 中 `_diagram_extension`，让 `echarts_option` 导出 `.json`。

### Task 5：后端验证

**命令**
- `pytest newbee_notebook/tests/unit/skills/diagram/test_registry.py -q`
- `pytest newbee_notebook/tests/unit/skills/diagram/test_tools.py -q`
- `pytest newbee_notebook/tests/contract/api/test_diagrams_router.py -q`
- `pytest newbee_notebook/tests/unit/application/services/test_diagram_service.py -q`
- `pytest newbee_notebook/tests/smoke/test_db_init_script.py -q`

**服务级验证**
- 启动 FastAPI 后端。
- 用 HTTP 请求创建一个 echarts diagram，确认返回 `diagram_type="echarts"`、`format="echarts_option"`。
- 拉取 `/api/v1/diagrams/{id}/content`，确认内容与请求一致。

---

## 三、自检点

1. `format` 只由 descriptor 推导，REST 和 tool 客户端都不传。
2. `preview_diagram_inline` 不是通用图表预览工具，只接受 echarts。
3. DB、SQLAlchemy model、init SQL、migration、测试断言的 format 枚举一致。
4. 前端未实施，只在文档中锁定接口和交互边界。
