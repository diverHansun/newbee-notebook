# architecture.md — classify-library

本文件描述 classify-library 批次涉及的结构调整。所有内容必须可追溯到 `goals-duty.md` 中已确认的职责。

---

## 一、Architecture Overview（总体架构）

本批次不引入新的模块，只在**既有的 Library 查询纵切链路**上对一处正交参数做扩展，并在前端列表页加入一个独立的"类型筛选区"子组件。

涉及的组件（自上而下）：

**后端**
- `routers/library.py`：HTTP 层。接收 `content_type` 多值 query 参数，将字符串列表转换为 `DocumentType` 枚举列表后下推。
- `application/services/library_service.py`：编排层。`list_documents` 增加 `content_types` 入参，原样传递到 Repository；不引入业务逻辑。
- `domain/repositories/document_repository.py`（抽象） + `infrastructure/persistence/repositories/document_repo_impl.py`（实现）：仓储层。`list_by_library` / `count_by_library` 接受 `content_types` 入参，组装 SQL `WHERE content_type IN (...)`。
- `domain/value_objects/document_type.py`：补齐 `.ppt` 扩展名到 `PPTX` 的映射；不改变枚举值集合。

**前端**
- `app/library/page.tsx`：宿主页面。维护"已选分组"状态，渲染状态 tab、类型 Chip 多选条、表格。
- `app/library/components/TypeFilterChips.tsx`（新增）：受控组件。负责 chip 多选条 UI 与"清空全部"。
- `app/library/components/DocumentTypeBadge.tsx`（新增）：纯展示组件。根据 `content_type` 字符串渲染原始扩展名徽章。
- `lib/api/library.ts`：API 客户端。`listLibraryDocuments` 增加 `contentTypes?: DocumentType[]` 入参，序列化为重复 query。
- `lib/api/types.ts`：类型定义。新增 `DocumentType`（前端镜像）、`DocumentTypeGroup`（分组键）与分组→`DocumentType[]` 映射常量。
- `lib/i18n/strings.ts`：在 `uiStrings.libraryPage` 下追加分组名、按钮、列名等中英双语字符串。

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. "事实粒度 / 意图粒度"分离

表格列展示**事实粒度**（原始扩展名 PDF / DOCX / PPTX / ...），筛选器展示**意图粒度**（分组 文档 / Word / 幻灯片 / 表格 / 电子书 / 文本）。两个粒度之间通过一张**前端单向映射表**（分组 → `DocumentType[]`）连接，不在后端建模分组概念。

理由：
- 后端枚举 `DocumentType` 是事实层，稳定且少变。
- 分组是用户认知层，可能随产品演进微调（例如未来把"幻灯片"再拆 keynote）；放在前端单文件里维护，调整成本可控且不污染领域层。
- 该分离让 API 始终接受**事实值**（`content_type=pdf&content_type=docx`），分组只是前端把意图展开为事实的封装。

### 2. 正交参数下推，不引入新业务概念

`content_type` 与现有 `status` 在 Router/Service/Repository 三层完全对称扩展：同样是可选过滤参数、同样下推到 Repo 层组装 SQL、同样作用于 `count` 与 `list` 两侧。

理由：
- 这是"扩展现有数据流"，不是"引入新数据流"。沿用既有结构最小化改动半径，也避免抽象出"FilterSpec"这类提前抽象的容器对象（在只有 2 个过滤维度时是过度设计）。

### 3. 受控组件 + 纯展示组件

前端两个新增组件都保持单一职责：
- `TypeFilterChips` 是受控的——状态由 `page.tsx` 持有，组件只负责渲染和回调；便于测试与未来抽出复用。
- `DocumentTypeBadge` 是纯展示的——只接受 `content_type` 字符串作为 prop。

理由：与现有 `ConfirmDialog` 等组件的拆分风格一致，避免在 `page.tsx` 中堆积 UI 细节。

### 4. 未使用的模式与理由

- **未使用 Strategy / Specification 模式**：当前只有 2 个筛选维度，引入 Strategy 抽象只会增加间接性，不会增加灵活性。
- **未使用全局状态管理**：分组选中态是页面级状态（不需要在路由间持久化、不需要跨组件共享），用 `useState` 持有即可，无需引入 zustand / context。
- **未把"分组"建模为后端实体**：见 `goals-duty.md` Non-Duties #1、#4。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

**新增文件**

```
frontend/src/app/library/components/
  ├── TypeFilterChips.tsx          # 类型筛选 Chip 多选条（受控）
  └── DocumentTypeBadge.tsx        # 类型徽章（纯展示）

frontend/src/lib/library/
  └── document-type-groups.ts      # 分组定义、分组↔DocumentType 映射
```

**修改文件**

```
后端
  newbee_notebook/api/routers/library.py
  newbee_notebook/application/services/library_service.py
  newbee_notebook/domain/repositories/document_repository.py
  newbee_notebook/infrastructure/persistence/repositories/document_repo_impl.py
  newbee_notebook/domain/value_objects/document_type.py  (仅补 .ppt 映射)

前端
  frontend/src/app/library/page.tsx
  frontend/src/lib/api/library.ts
  frontend/src/lib/api/types.ts
  frontend/src/lib/i18n/strings.ts
```

**职责定位**

| 路径 | 角色 |
|---|---|
| `routers/library.py` | 外部稳定接口（query 参数语义） |
| `services/library_service.py` | 仅做参数透传，不做编排 |
| `repositories/document_repo_impl.py` | 内部实现，SQL 组装逻辑 |
| `lib/library/document-type-groups.ts` | 前端的"事实↔意图"映射，单一来源 |
| `components/TypeFilterChips.tsx` | 受控 UI，不直接调用 API |
| `components/DocumentTypeBadge.tsx` | 纯展示，无业务逻辑 |
| `lib/api/library.ts` | API 客户端边界，负责把分组展开成事实值序列化到 URL |

`document-type-groups.ts` 是前端的"单一来源"——任何需要"分组↔类型值"映射的地方都从这里取，禁止在组件里复制硬编码。

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. **接受"前端持有分组定义"的代价**
分组（"幻灯片"包含哪些 `DocumentType`）在前端 `document-type-groups.ts` 里声明，后端不知道分组的存在。代价：如果未来另一种前端（如移动端）要使用同样的分组，需要复制定义。

替代方案是把分组建模为后端的一种"虚拟筛选 preset"返回给前端——被放弃，理由是：当前只有一个前端，提前抽象成本高于收益；而 API 层接受的是事实值（`content_type=pdf`），即便未来另一端不使用分组，也能直接用枚举值过滤，所以协议层并未泄漏分组概念。

### 2. **不为 `content_type` 列添加数据库索引**
当前 Library 文档量级很小（截图中 7 份，量级估计在百级以内）。`WHERE content_type IN (...)` 在小表上扫描代价可忽略。代价：如果未来文档量增长到万级且类型筛选成为高频路径，可能需要补 `(library_id, content_type)` 联合索引或局部索引。

放弃即时加索引是为了避免**为低概率场景做迁移**；本批次刻意把索引调整列为 Non-Duties（见 `goals-duty.md`）。

### 3. **接受"前端 fetchAll + 后端过滤"并存的临时状态**
前端目前用 `fetchAll=true` 拉全量，本批次仍然让后端按 `content_type` 过滤（而不是仅前端过滤）。代价：后端做了一次按类型的过滤，前端却仍可能拉满；短期内有冗余。

不在本批次修分页是为了控制改动半径（见 `goals-duty.md` Non-Duties #2）。一旦未来拆掉 `fetchAll`，后端的 `content_type` 过滤会立刻发挥分页正确性的作用——属于"为未来改动留好接口、当下不暴露损失"的权衡。

### 4. **接受存量 `.ppt` 文件不被自动回填**
`.ppt → PPTX` 映射修复后，已经被错误归类为 `TXT` 的存量文件不会自动变更其 `content_type`。代价：用户视角下"那份 ppt 还在文本类下"。

不做回填是因为：(1) 用户量级小、单一用户；(2) 写一次性回填脚本本质上是数据修正，与本批次"扩展筛选能力"的职责正交；(3) 用户可手工删除重新上传。如未来发现影响面扩大，再单独立项做回填脚本。

---

## 五、与后续文档的对接预期

- `data-model.md` 将定义"DocumentTypeGroup"概念词及其与 `DocumentType` 的映射。
- `dfd-interface.md` 将描述新增 query 参数的数据流路径与接口契约。
- `use-case.md` 将描述用户选取分组 → 列表刷新的内部编排。
- `test.md` 将按桥接/适配模块（Router 契约）与纯逻辑模块（前端组件与映射）的双原型划分测试重心。
