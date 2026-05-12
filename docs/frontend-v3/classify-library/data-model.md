# data-model.md — classify-library

本批次不引入持久化层的新概念，但需要明确**前后端共用与前端独有**两层认知模型，避免后续接口、组件、测试出现概念漂移。

---

## 一、Core Concepts（核心概念）

### 1. `DocumentType`（既有，事实层）

代表"文件本身是什么类型"，由 `DocumentType.from_extension` 在上传时根据文件后缀派生并落库到 `Document.content_type`。

- 取值集合：`pdf` / `txt` / `docx` / `pptx` / `epub` / `md` / `csv` / `xlsx`
- 性质：稳定枚举，后端单一来源
- 本批次仅补一处映射：`.ppt → pptx`

> 该概念已存在于 `newbee_notebook/domain/value_objects/document_type.py`，不在此处重复定义，仅声明其在本批次中的角色：**API 层 `content_type` query 参数的合法取值**，以及**前端表格"类型"列徽章的展示来源**。

### 2. `DocumentTypeGroup`（新增，意图层，前端独有）

代表"用户视角下的一类文件"，是若干 `DocumentType` 值的聚合。它**只存在于前端代码**，不出现在后端 API、数据库或领域层。

- 取值集合（6 个）：
  - `document` —— 文档（PDF）
  - `word` —— Word
  - `slides` —— 幻灯片
  - `sheet` —— 表格
  - `ebook` —— 电子书
  - `text` —— 文本

- 每个分组对应一组 `DocumentType` 值（见下表）。

### 3. `groupToTypes`（映射，前端独有）

`DocumentTypeGroup` → `DocumentType[]` 的单向映射函数 / 常量。是前端把"意图"展开为"事实"的唯一通道。

| Group | 展开后的 `DocumentType` 值 |
|---|---|
| `document` | `pdf` |
| `word` | `docx` |
| `slides` | `pptx` |
| `sheet` | `xlsx`, `csv` |
| `ebook` | `epub` |
| `text` | `md`, `txt` |

> 该映射保证**全覆盖且互斥**：8 个 `DocumentType` 值各自归属到唯一一个分组，不存在某个值既在 `sheet` 又在 `text` 的情况。这条不变量在测试中必须被验证。

---

## 二、Entity / Value Object 区分

| 概念 | 性质 | 说明 |
|---|---|---|
| `DocumentType` | Value Object | 枚举值；无身份；不可变 |
| `DocumentTypeGroup` | Value Object | 前端枚举键；无身份；不可变 |
| `groupToTypes` | 不可变映射常量 | 编译期固定；无运行时状态 |

本批次**不引入任何新的 Entity**——分组不持久化、不可被用户修改、不持有自己的生命周期。

---

## 三、Key Data Fields（关键数据字段）

### API 层（请求/响应字段）

| 字段 | 含义 | 取值 |
|---|---|---|
| `content_type` (query, 多值) | 列表查询的类型过滤条件；可重复出现 | `DocumentType` 字符串 |
| `DocumentItem.content_type` (响应) | 单个文档的事实类型；前端用于渲染表格徽章 | `DocumentType` 字符串 |

注：API 层只识别 `DocumentType` 字符串，**不识别也不接受 `DocumentTypeGroup`**。前端必须负责展开。

### 前端组件状态

| 字段 | 含义 | 取值 |
|---|---|---|
| `selectedGroups: Set<DocumentTypeGroup>` | 当前选中的分组集合 | 空集 = 不过滤；非空 = 过滤为这些分组覆盖的类型 |

派生值：`selectedGroups` → `flat(groupToTypes)` → 传给 API 的 `content_type` 多值列表。

---

## 四、Lifecycle & Ownership（生命周期与归属）

| 数据 | 创建 | 更新 | 销毁 | 负责组件 |
|---|---|---|---|---|
| `Document.content_type` | 文档上传时由 `from_extension` 派生 | 不更新（除非文档被删除重传） | 随文档删除 | 上传链路（既有，不在本批次） |
| `selectedGroups` (前端状态) | 页面挂载时为空集 | 用户点击 chip 或"清空全部"时变化 | 页面卸载时销毁 | `app/library/page.tsx` |
| `groupToTypes` (映射) | 编译期 | 不更新 | 不销毁 | `lib/library/document-type-groups.ts` |

`selectedGroups` 不持久化到 URL / localStorage / 后端。每次进入页面默认是"全部"。这是刻意决策——见 `non-functional.md` 的"暂缓项"。

---

## 五、概念使用一致性约束

所有讨论文件类型分类的代码与文档必须遵循：

1. **API 层只谈 `DocumentType`，不谈 `DocumentTypeGroup`。** Router 不允许接受 group 名作为参数。
2. **`DocumentTypeGroup` 的来源只有一处：** `lib/library/document-type-groups.ts`。组件、测试、i18n key 都引用它，禁止在多处复制定义。
3. **i18n key 与 group 一一对应：** 例如 `uiStrings.libraryPage.typeGroupSlides` 对应 `slides`，命名必须保持机械对应关系，便于将来增减分组时静态检查。
4. **表格徽章按 `DocumentType` 渲染，不按 group。** 即便用户筛选了"幻灯片"分组，表格里每行也显示 "PPTX"，而不是 "幻灯片"。
