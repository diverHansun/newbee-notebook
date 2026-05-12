# dfd-interface.md — classify-library

本文档以**数据流为核心**，描述 classify-library 批次在 Library 列表查询路径上新增的筛选维度如何从 UI 流向 SQL，以及对外接口契约的变更点。

---

## 一、Context & Scope（上下文与范围）

**讨论范围**：从用户在 Library 页面操作"类型筛选 Chip 多选条"开始，到后端返回经过类型过滤的文档列表为止的完整往返路径。

**外部交互方**：
- 上游：浏览器内的 Library 页面用户交互层（chip 点击、清空按钮）。
- 下游：Postgres 中的 `documents` 表（既有；不修改 schema）。
- 同级正交：现有的 `status` 过滤参数（已在路径中存在，本批次确保新参数与其正交并存）。

**不在本文档范围内**：
- 文档上传流程（`content_type` 的产生）。
- 文档删除流程。
- Notebook 侧的文档关联/反查路径。

---

## 二、Data Flow Description（数据流描述）

### 数据流 A：用户筛选→列表刷新（正常路径）

1. **用户输入**：用户在 `app/library/page.tsx` 渲染的 Chip 多选条中点击若干分组（如 `slides` + `word`）。
2. **前端状态更新**：`page.tsx` 持有的 `selectedGroups: Set<DocumentTypeGroup>` 加入这两个分组。
3. **意图→事实展开**：在请求 API 前，`page.tsx` 通过 `lib/library/document-type-groups.ts` 的 `groupToTypes` 把 `selectedGroups` 展开为 `DocumentType[]`（如 `[pptx, docx]`），传入 `listLibraryDocuments({ contentTypes: [...] })`。
4. **序列化**：`lib/api/library.ts` 把 `contentTypes` 数组序列化为重复 query 参数：`?content_type=pptx&content_type=docx`（与 `status`、`limit`、`offset` 同处一个 `URLSearchParams`）。
5. **HTTP 请求**：`apiFetch` 发起 `GET /library/documents?...`。
6. **路由层接收**：`routers/library.py` 的 `list_library_documents` 接收 `content_type: Optional[List[str]] = Query(None)`，将每个字符串校验为 `DocumentType` 枚举值。非法值返回 `400`。
7. **应用层透传**：`LibraryService.list_documents(content_types=[...])` 把列表原样下推到 Repository。
8. **仓储层组装 SQL**：`DocumentRepoImpl.list_by_library` 与 `count_by_library` 在已有 `WHERE library_id IS NOT NULL` 的基础上追加 `AND content_type IN (...)`（仅当列表非空时追加）。
9. **数据库执行**：Postgres 返回过滤后的行与总数。
10. **响应回传**：Service → Router 组装 `DocumentListResponse`（数据形态不变，仅过滤集合变化），HTTP 200 返回。
11. **前端渲染**：`useQuery` 收到结果，表格按返回的 `DocumentItem[]` 渲染，每行的"类型"列由 `DocumentTypeBadge` 根据 `row.content_type` 显示原始扩展名徽章。

### 数据流 B：用户清空筛选

1. 用户点击"清空全部"按钮。
2. `selectedGroups` 重置为空集。
3. 前端发起 `GET /library/documents?status=...`（不携带任何 `content_type` 参数）。
4. 路由层 `content_type` 为 `None`，不做过滤；与本批次前的行为一致。

### 数据流 C：状态与类型组合筛选

1. 用户在 tab bar 选中"已完成"，同时在 chip 条勾选 `sheet`。
2. 请求形如 `GET /library/documents?status=completed&content_type=xlsx&content_type=csv`。
3. Repository 层组装的 SQL 同时具备 `AND status = 'completed' AND content_type IN ('xlsx','csv')`。
4. `total` 与 `data` 都遵循该联合条件。

### 数据流 D：非法 `content_type`（异常路径）

1. 客户端发送 `?content_type=unknown` 或攻击性输入。
2. Router 层尝试 `DocumentType("unknown")` 抛 `ValueError`。
3. Router 捕获并返回 `400 Bad Request`，body 含 `detail: "Invalid content_type filter"`。
4. 不会到达 Service / Repository。

---

## 三、Interface Definition（接口定义）

### 1. HTTP — `GET /library/documents`（变更）

**变更点**：query 参数集新增 `content_type`，可重复。

| 参数 | 类型 | 是否必填 | 含义 |
|---|---|---|---|
| `limit` | int | 否（默认 20） | 单页条数 |
| `offset` | int | 否（默认 0） | 偏移 |
| `status` | `DocumentStatus` 字符串 | 否 | 状态过滤（既有） |
| `content_type` | `DocumentType` 字符串，可重复 | 否 | **新增**。类型过滤；多次出现表示"或"语义 |

**响应**：结构不变（`DocumentListResponse` = `{ data, pagination }`），仅集合受筛选影响。

**错误语义**：
- 任一 `content_type` 值不在 `DocumentType` 枚举内 → `400`，`detail = "Invalid content_type filter"`。
- 任一 `status` 值不合法 → `400`（既有行为，不变）。

**兼容性**：不传 `content_type` 时行为与本批次前完全一致；旧客户端不受影响。

### 2. Service —`LibraryService.list_documents`（变更）

```
list_documents(
    limit: int = 50,
    offset: int = 0,
    status: Optional[DocumentStatus] = None,
    content_types: Optional[List[DocumentType]] = None,   # 新增
) -> Tuple[List[Document], int]
```

- 语义：当 `content_types` 为 `None` 或空列表时不过滤；非空时按 `IN` 语义过滤。
- 仅做参数透传，不在 Service 层做合法性二次校验（合法性已由 Router 完成）。

### 3. Repository — `DocumentRepository.list_by_library` / `count_by_library`（变更）

抽象接口与实现同步增加 `content_types: Optional[List[DocumentType]] = None`。`list_by_library` 与 `count_by_library` 必须共享同一过滤逻辑（建议抽取一个内部 `_content_type_filter(query, content_types)` 辅助方法，与既有的 `_status_filter` 风格对称）。

### 4. 前端 API 客户端 — `listLibraryDocuments`（变更）

```
listLibraryDocuments(params?: {
  limit?: number;
  offset?: number;
  status?: DocumentStatus;
  contentTypes?: DocumentType[];   // 新增
  fetchAll?: boolean;
}): Promise<ApiListResponse<DocumentItem>>
```

- `contentTypes` 为空数组或未传时不附加 `content_type` 参数。
- `fetchAll=true` 时，分页递归调用必须把 `contentTypes` 透传给每一页。

### 5. 前端组件接口

- `TypeFilterChips`：受控组件，props 含 `selected: Set<DocumentTypeGroup>`、`onChange: (next: Set<DocumentTypeGroup>) => void`、`onClear: () => void`。
- `DocumentTypeBadge`：纯展示，props 仅 `contentType: string`。

---

## 四、Data Ownership & Responsibility（数据归属与责任）

| 数据 | 创建者 | 修改者 | 持久化层 | 在本数据流中的角色 |
|---|---|---|---|---|
| `Document.content_type` | 上传链路（既有） | 不修改 | `documents.content_type` 列 | 过滤依据 + 表格徽章数据源 |
| `content_type` query 参数 | 前端 `lib/api/library.ts` | 仅本次请求生命周期 | 无 | 客户端→服务端的过滤意图载体 |
| `selectedGroups` 前端状态 | `app/library/page.tsx` | 用户交互触发 | 内存（不持久化） | UI 状态，请求构造的源头 |
| 列表查询结果 | Repository | 不修改 | 无（查询结果） | 渲染数据源 |

**关键责任声明**：

1. **Router 层是 `DocumentType` 字符串合法性校验的唯一关口**。Service 与 Repository 信任入参已校验。
2. **前端是分组→类型展开的唯一负责方**。后端永远收到的是 `DocumentType` 事实值，不感知分组概念。
3. **`Document.content_type` 的写入责任不在本批次内**。本批次只读不写；但 `.ppt → pptx` 映射修复会影响未来上传链路的写入结果——该修改的责任范围是"扩展名映射函数本身"，不涉及现有文档的回填。
