# use-case.md — classify-library

本批次涉及的业务动作较少且单一（"用户筛选→列表刷新"），但跨越前端 UI、API、Service、Repository 多层。本文件聚焦**职责归属与编排**，避免实现层细节。

---

## 一、Use Case Overview（用例概览）

| Use Case | 一句话描述 |
|---|---|
| UC-1 Filter Library by Type | 用户通过类型 Chip 多选条筛选 Library 文档列表 |
| UC-2 Clear Type Filter | 用户清空已选类型筛选，恢复"全部"视图 |
| UC-3 Combine Type & Status Filter | 用户同时使用类型与状态两个维度筛选 |
| UC-4 Display Per-Row Type Badge | 表格在每行展示原始扩展名徽章 |

所有 use case 都可追溯到 `goals-duty.md` 中的 Duties：UC-1/UC-2/UC-3 → Duty #1、#3、#5；UC-4 → Duty #4。

---

## 二、Main Flow Description（主流程描述）

### UC-1 Filter Library by Type

1. **接收输入**：用户在 `TypeFilterChips` 中点击某分组的 chip（如 `slides`）。
2. **状态更新**：父组件 `page.tsx` 接收 `onChange` 回调，将 `slides` 加入 `selectedGroups`。
3. **意图→事实展开**：在构造 API 请求前，`page.tsx`（或 `library.ts` 客户端内部）通过 `groupToTypes` 把 `selectedGroups` 展开为 `DocumentType[]`。
4. **请求触发**：`useQuery` 因 queryKey 变化重新发起请求，携带 `content_type` 多值参数。
5. **后端过滤**：Router 校验 → Service 透传 → Repository 组装 `IN` 条件 → 返回过滤后的数据与总数。
6. **结果渲染**：表格按返回结果重绘，受筛选影响的行集减少；表格"类型"列每行展示其原始扩展名徽章（属 UC-4）。

### UC-2 Clear Type Filter

1. **接收输入**：用户点击"清空全部"按钮。
2. **状态重置**：`selectedGroups` 设为空集，`onClear` 回调触发。
3. **请求触发**：queryKey 变化，发起不携带 `content_type` 的请求。
4. **结果渲染**：表格恢复到当前状态 tab 下的全集视图。

> 说明：UC-2 不是 UC-1 的特例，而是独立动作——单独按钮、单独可达性焦点、单独的视觉位置；逻辑上虽然等价于"把 `selectedGroups` 设为空集"，但作为独立 use case 表达让交互更清晰。

### UC-3 Combine Type & Status Filter

1. **接收输入**：用户分别在 tab bar 与 chip 条作出选择。
2. **状态合并**：`status: StatusFilter` 与 `selectedGroups: Set<DocumentTypeGroup>` 是两个独立的状态变量，互不联动。
3. **请求构造**：两个维度的参数同时序列化进同一个 query string。
4. **后端过滤**：SQL 的 `WHERE` 子句以 `AND` 连接两个条件。
5. **结果渲染**：同 UC-1。

### UC-4 Display Per-Row Type Badge

1. **接收输入**：表格行渲染时，每行的 `DocumentItem.content_type` 字段。
2. **展示决策**：`DocumentTypeBadge` 根据该字符串渲染对应的原始扩展名徽章（PDF / DOCX / PPTX / ...）。
3. **i18n**：徽章本身的扩展名文字使用全大写英文（PDF/DOCX 等是国际通用缩写，不需要本地化）；但徽章的 `aria-label` 与 tooltip 走 i18n（如"文件类型：PDF" / "File type: PDF"）。

---

## 三、Responsibility Boundaries（责任边界）

### 当前模块（classify-library 批次）必须负责

| 步骤 | 负责组件 |
|---|---|
| 接收用户分组点选 | `TypeFilterChips` |
| 维护选中态 | `page.tsx`（受控） |
| 分组→类型展开 | `page.tsx` 或 `library.ts`（统一在前端，单一来源 `document-type-groups.ts`） |
| `content_type` 序列化为 query | `lib/api/library.ts` |
| `content_type` 字符串→枚举校验 | `routers/library.py` |
| `content_types` 透传 | `LibraryService.list_documents` |
| SQL `IN` 条件组装 | `DocumentRepoImpl.list_by_library` / `count_by_library` |
| 每行徽章渲染 | `DocumentTypeBadge` |
| 中英文字符串提供 | `lib/i18n/strings.ts` |
| `.ppt` 映射补齐 | `domain/value_objects/document_type.py` |

### 外部模块负责（不属于本批次）

| 步骤 | 责任方 |
|---|---|
| 文档上传时识别扩展名并写入 `content_type` | 上传链路（既有，不修改） |
| `Document` 实体的存储、删除 | DocumentService / DocumentRepoImpl 既有职责 |
| 数据库连接、事务边界 | infrastructure 层既有职责 |
| 状态 tab 的现有逻辑 | `page.tsx` 既有代码（不在本批次重构） |

### 基础设施 / 工具层（与本批次正交）

- `apiFetch` 已存在，不修改。
- `useQuery` / `useMutation` 已配置，不调整 staleTime / refetch 策略。
- `badge` CSS class 已存在，新增"中性色"变体如需要再加（详见实施时讨论）。

---

## 四、Failure & Decision Points（失败点与决策点）

### 失败点 F-1：非法 `content_type` 值
- **触发条件**：客户端构造的 query 中含有不在 `DocumentType` 枚举内的值（如手工构造 URL、客户端版本与后端版本不一致）。
- **预期行为**：Router 返回 `400`，前端的 `apiFetch` 错误处理走既有的错误展示路径（与既有 `status` 非法值时一致）。
- **不应发生**：不应静默忽略非法值（绝不能"只过滤合法部分、丢弃非法部分"——这会让客户端误以为筛选成功）。

### 失败点 F-2：网络/服务端 5xx
- **触发条件**：Library 列表请求失败。
- **预期行为**：`useQuery` 进入 error 态，页面展示既有的错误占位；用户的 `selectedGroups` **保留**（不重置），便于用户重试。

### 决策点 D-1：分组→类型展开是否包含未在分组中出现的 `DocumentType`？
- **答**：不允许。`groupToTypes` 必须覆盖全部 8 个 `DocumentType` 值，且每个值归属唯一分组（见 `data-model.md`）。如果未来后端新增枚举值（如 `keynote`），前端必须同步把它归入某个分组，否则该类文档会"用户无法通过分组筛选到"。
- **运行时保护**：在 `document-type-groups.ts` 中导出一个 `assertFullCoverage()` 工具，在测试中调用以验证不变量。

### 决策点 D-2：空 `content_types` 列表是否等同于 "全部"？
- **答**：是。后端 `content_types is None` 与 `content_types == []` 行为一致——都不过滤。前端在 `selectedGroups` 为空集时直接不附加 query 参数（最干净），但后端两种入参都接受。

### 决策点 D-3：选中分组后是否自动重置 `offset`？
- **答**：是。筛选条件变化时，分页应回到第 0 页（否则用户看到"空白"会困惑）。这与既有 `status` 切换的行为对齐——当前 `status` 切换并未显式重置 `offset`，但因 `fetchAll=true` 不暴露问题；本批次保持一致行为，未来拆分页时统一处理。
