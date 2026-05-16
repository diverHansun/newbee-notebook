# test.md — classify-library

本批次涉及多个文件，但它们分别落在**不同的模块原型**上。本文件按原型分别声明测试重心。

---

## 一、Module Test Profile（模块测试档案）

本批次涉及三种原型，分别声明：

### Profile A — 后端 Router 变更（桥接 / 适配模块）

- 模块原型：桥接 / 适配模块（HTTP Router）
- 主要测试类型：contract
- Mock 边界：`LibraryService` 全部 mock；HTTP 请求/响应使用 FastAPI `TestClient` 真实发送
- 测试归属目录：`newbee_notebook/tests/contract/api/`
- 关注文件：`newbee_notebook/api/routers/library.py`

### Profile B — Service / Repository 透传（服务编排模块）

- 模块原型：服务编排模块（薄编排，几乎纯透传）
- 主要测试类型：integration（service + repo + 真实 DB），可选 unit（仅 service 透传）
- Mock 边界：测试 service 时 mock Repo；测试 repo 时使用真实测试数据库
- 测试归属目录：`newbee_notebook/tests/integration/`
- 关注文件：`library_service.py`、`document_repo_impl.py`

### Profile C — 前端组件与映射（纯逻辑模块 + 桥接模块）

- 模块原型：
  - `document-type-groups.ts`：纯逻辑（映射与覆盖性不变量）
  - `TypeFilterChips.tsx`、`DocumentTypeBadge.tsx`：纯展示组件
  - `lib/api/library.ts` 中的 `listLibraryDocuments`：桥接（URL 序列化契约）
- 主要测试类型：unit（Jest / Vitest + React Testing Library）
- Mock 边界：API 客户端测试 mock `apiFetch`；组件测试不需要 mock
- 测试归属目录：`frontend/src/**/__tests__/` 或就近 `*.test.tsx`

### Profile D — `DocumentType.from_extension` 映射补齐（纯逻辑模块）

- 模块原型：纯逻辑模块
- 主要测试类型：unit
- Mock 边界：无
- 测试归属目录：`newbee_notebook/tests/unit/`（如目录不存在则就近放置）

---

## 二、Test Scope（测试范围）

### 覆盖

- 后端 Router 在 `content_type` 单值、多值、与 `status` 组合、非法值、缺省下的契约行为。
- Service / Repository 把 `content_types` 下推到 SQL 的正确性（`IN` 子句、与 `status` 共存的 `AND`、空列表与 `None` 行为一致）。
- 前端 `groupToTypes` 映射的全覆盖与互斥不变量。
- 前端 `lib/api/library.ts` 把 `contentTypes` 数组序列化为重复 query 参数。
- 前端 `TypeFilterChips` 的选中态变化回调、清空回调。
- 前端 `DocumentTypeBadge` 按 `content_type` 正确渲染原始扩展名。
- 前端 i18n 新增 key 在 `zh` 和 `en` 都存在（静态断言）。
- `DocumentType.from_extension("ppt")` 返回 `PPTX`。

### 不覆盖

- 文档上传链路（`content_type` 的写入路径既有，不在本批次）。
- 既有的 `status` 过滤行为（本批次不修改其逻辑）。
- 既有的删除、分页行为。
- 性能与压力测试（见 `non-functional.md` 优先级 #4）。

---

## 三、Critical Scenarios（关键场景）

### 后端 Router（Profile A）

**正常路径**
- 不传 `content_type` → 行为与本批次前完全一致（Service 接到 `content_types=None`）。
- 传单个 `content_type=pdf` → Service 接到 `content_types=[DocumentType.PDF]`。
- 传多个 `content_type=pdf&content_type=docx` → Service 接到包含两值的列表。
- 与 `status=completed` 组合 → 两参数同时下推。

**异常路径**
- `content_type=unknown` → 返回 `400`，body 含 "Invalid content_type filter"。
- `content_type=pdf&content_type=unknown`（一合法一非法）→ 返回 `400`，不调用 Service。
- 重复值数量超过 32 → 返回 `400`（抗滥用边界）。

### Service / Repository（Profile B）

**正常路径**
- `content_types=None` → SQL 不含 `content_type` 条件，等价于本批次前。
- `content_types=[PDF]` → SQL 含 `content_type IN ('pdf')`。
- `content_types=[PDF, DOCX]` → SQL 含 `content_type IN ('pdf','docx')`。
- `content_types=[]`（空列表）→ 行为等价于 `None`（不过滤）。
- `count_by_library` 与 `list_by_library` 在相同入参下返回的总数与列表长度一致（除分页外）。

**异常路径**
- 数据库连接失败 → 与既有错误处理路径一致（不在本批次新增异常处理）。

### 前端映射（Profile C — 纯逻辑）

- `groupToTypes` 的并集覆盖全部 `DocumentType` 8 个值（全覆盖不变量）。
- `groupToTypes` 的交集为空（互斥不变量）—— 每个 `DocumentType` 值只属于一个分组。
- 调用 `assertFullCoverage()` 时不应抛错。

### 前端 API 客户端（Profile C — 桥接）

- `contentTypes: undefined` 或 `[]` → URL 不含任何 `content_type` 参数。
- `contentTypes: ['pdf', 'docx']` → URL 含 `content_type=pdf&content_type=docx`（顺序无关，但都存在）。
- 与 `status` 共存 → 两组参数同时序列化。
- `fetchAll=true` → 内部递归调用每一页都携带 `contentTypes`。

### 前端组件（Profile C — 展示）

**`TypeFilterChips`**
- 渲染 6 个 chip，分别对应 6 个分组。
- 点击 chip → 触发 `onChange`，传入更新后的 `Set`。
- 选中态视觉变化（受控）。
- 点击"清空全部"→ 触发 `onClear`。
- 所有可见文本来自 i18n（mock 不同 lang 验证中英文切换正确）。

**`DocumentTypeBadge`**
- `contentType="pdf"` → 渲染 "PDF" 徽章。
- `contentType="pptx"` → 渲染 "PPTX" 徽章。
- 未知值（容错）→ 显示该值原样（不崩溃）。
- aria-label 走 i18n。

### i18n 完整性（Profile C — 静态检查）

- 新增的每个 key（如 `typeGroupDocument`、`typeGroupWord`、`typeGroupSlides`、`typeGroupSheet`、`typeGroupEbook`、`typeGroupText`、`typeFilterLabel`、`typeFilterClear`、`tableType`、`typeBadgeAriaLabel`）必须在 `zh` 和 `en` 中都有非空字符串。
- 测试方式：遍历 `uiStrings.libraryPage` 中新增 key，断言两个语言键都存在。

### 扩展名映射（Profile D）

- `DocumentType.from_extension("ppt")` 返回 `DocumentType.PPTX`。
- `DocumentType.from_extension(".PPT")` 返回 `DocumentType.PPTX`（大小写与点号处理与既有一致）。
- `supported_extensions()` 包含 `"ppt"`。
- 既有映射保持不变（`pdf`/`docx`/`doc`/`pptx`/`epub`/`md`/`markdown`/`csv`/`xlsx`/`xls`/`txt`）。

---

## 四、Contract Specification（契约规约）

### `GET /library/documents`

**请求**
- Query 参数：
  - `limit: int`（默认 20，1–100）
  - `offset: int`（默认 0，≥0）
  - `status: str?`（`DocumentStatus` 枚举字符串）
  - `content_type: str[]?`（可重复，每个值必须是 `DocumentType` 枚举字符串）

**成功响应**：`200`
- Body：`DocumentListResponse = { data: DocumentItem[], pagination: PaginationInfo }`
- `total` 反映"经过 status 与 content_type 联合过滤后"的总数。

**错误响应**
- `400`：`status` 或 `content_type` 任一非法 → `{ detail: "Invalid status filter" }` 或 `{ detail: "Invalid content_type filter" }`。
- `400`：`content_type` 重复次数超过 32 → `{ detail: "Too many content_type values" }`。

**兼容性承诺**
- 不传 `content_type` 时，响应结构与字节级行为与本批次前一致。

### 前端 API 客户端契约

`listLibraryDocuments({ contentTypes, status, ...page })` 的 URL 序列化必须满足：
- `contentTypes` 缺省或空数组时，URL 不含 `content_type`。
- 多值时，每个值各一次 `content_type=...`。
- 不对 `contentTypes` 做去重（去重是调用方责任；测试可以假设调用方传入去重后的数组）。

---

## 五、Integration Points（集成点测试）

- **Router ↔ Service**：通过 contract 测试以 mocked service 验证下推参数形态；通过 integration 测试以真实 service + repo 验证端到端语义。
- **Service ↔ Repository**：integration 测试使用测试数据库，预置不同 `content_type` 的若干文档，验证组合筛选返回集合正确。
- **前端 page ↔ API 客户端**：以 React Testing Library 渲染 `LibraryPage`，mock `listLibraryDocuments`，验证 chip 交互触发的入参形态。
- **i18n ↔ 组件**：组件测试在两种 `lang` 下分别断言渲染文案。

---

## 六、Verification Strategy（验证策略）

- **后端单元/契约**：`pytest`，与既有 Library 相关测试并列；mock 边界沿用现有 fixture（`get_library_service` / `get_document_service` 依赖注入覆盖）。
- **后端集成**：在已配置的测试数据库下运行；不需要新的迁移脚本。
- **前端测试**：沿用项目当前的前端测试框架（Vitest/Jest，详见 `frontend/package.json` 与既有 `*.test.tsx`）。
- **i18n 静态检查**：作为前端单元测试的一条断言，遍历对象树。
- **人工验证**：实施完成后需在浏览器中手工验证：(1) 中文/英文切换；(2) 多选 + 清空；(3) 与状态 tab 组合；(4) 表格类型列在不同文件类型下正确显示。这部分在 `non-functional.md` 中未要求自动化。

---

## 七、自检确认（落地前 review）

- [x] 已声明三个 Profile 与各自的测试归属。
- [x] 关键场景覆盖正常路径与异常路径（含 400 抗滥用）。
- [x] Contract Specification 给出了请求/响应/错误码的明确契约。
- [x] mock 边界对每个 Profile 都有声明。
- [x] 测试不绑定具体实现细节（不指定函数签名 / 内部状态字段名）。
