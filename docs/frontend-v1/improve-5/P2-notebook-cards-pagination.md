# P2: Notebook 卡片增强与分页管理

## 问题描述

Notebooks 列表页（`/notebooks`）存在以下体验问题：

1. **卡片过小**：当前卡片尺寸紧凑，只占页面顶部一小块区域，大量页面空间浪费
2. **无分页机制**：`listNotebooks(limit=100, offset=0)` 一次性获取所有 notebook，当数量增长时页面会无限拉长，没有分页或虚拟滚动

## 当前实现

```tsx
// notebooks/page.tsx
const { data: notebooks } = useQuery({
  queryKey: ["notebooks"],
  queryFn: () => listNotebooks(100, 0),
});
```

卡片布局通过 `.notebook-grid` CSS 类控制（定义在 `styles/layout.css` 中），采用 CSS Grid `repeat(auto-fill, minmax(280px, 1fr))`，每张卡片为 `.card .card-interactive`。

当前卡片已实现描述行渲染（有 `description` 时显示一行截断文字），本次无需新增描述行，只需调整尺寸。

当前卡片结构：
```
+---------------------------+
| 标题 (strong)              |
| 描述文字（一行截断，若有）  |
| [2 文档] [8 会话]          |
| 更新于 1 小时前             |
|                    [删除]  |
+---------------------------+
```

## 设计方案

### 卡片尺寸增大

**调整 `.notebook-grid` 规则**（位于 `styles/layout.css`）：

- 当前：`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`
- 目标：增大最小宽度至 320px，`repeat(auto-fill, minmax(320px, 1fr))`
- 卡片内边距从当前值增加到 20-24px
- 卡片最小高度设置为 160px（确保即使内容少也有足够视觉重量）

**卡片内容微调**：

- 标题字号从当前值增大到 15-16px
- 统计标签（文档数、会话数）与更新时间之间增加视觉间距
- 删除按钮与更新时间同行，右对齐

> 注意：描述行已在 improve-4 中实现，本阶段无需改动。

### 排序规则

列表默认按 `updated_at` 降序排列（最近更新的 notebook 排在前面）。排序由后端 API 保证，前端不额外排序。

### 分页管理

**分页策略**：采用传统分页（非无限滚动），原因：
- notebook 是用户的核心资源单元，数量通常在数十到数百量级
- 用户需要明确知道自己有多少 notebook，分页提供清晰的总量感知
- 实现简单，不需要额外的滚动监听和虚拟化库

**分页参数**：
- 每页数量：`pageSize = 12`
- 与 Grid 列数解耦：`auto-fill` 会根据视口宽度自动决定每行列数（窄屏 2 列 x 6 行、标准屏 3 列 x 4 行、宽屏 4 列 x 3 行），`pageSize` 不应与固定行列数绑定
- 通过常量定义，后续可根据需要调整

**分页 API 调用**：

后端 `listNotebooks(limit, offset)` 返回的 `ApiListResponse<Notebook>` 已包含完整分页信息（`PaginationInfo` 含 `total`、`has_next`、`has_prev`），无需后端改动。

```typescript
// 修改现有查询
const [currentPage, setCurrentPage] = useState(1);
const PAGE_SIZE = 12;

const { data } = useQuery({
  queryKey: ["notebooks", currentPage, PAGE_SIZE],
  queryFn: () => listNotebooks(PAGE_SIZE, (currentPage - 1) * PAGE_SIZE),
});

// 分页信息直接从响应中获取
const totalPages = data ? Math.ceil(data.pagination.total / PAGE_SIZE) : 0;
```

**分页控件设计**：

位置在卡片网格下方居中，展示形式：

```
                <-- 1 / 3 -->
```

- 左右箭头按钮（上一页/下一页）
- 中间显示"当前页 / 总页数"
- 第一页时左箭头禁用（可用 `data.pagination.has_prev`），最后一页时右箭头禁用（可用 `data.pagination.has_next`）
- 总页数为 1 时隐藏整个分页控件

**分页控件样式**：
- 使用现有 `.btn .btn-ghost .btn-sm` 样式
- 页码文字使用 `.muted` 样式
- 整体水平居中，与卡片网格对齐

## 底部操作栏调整

当前 Notebooks 页底部固定有 "+ 创建 Notebook" 和 "查看 Library" 两个按钮。分页控件引入后需要协调布局：

- 分页控件放在卡片网格和底部操作栏之间
- 底部操作栏保持不变（其位置和功能属于独立关注点，本阶段不调整）

## i18n 文本新增

在 `strings.ts` 的 `notebooksPage` 分区中追加：

```typescript
notebooksPage: {
  // ... 已有字段保持不变
  pageInfo: { zh: "{current} / {total}", en: "{current} / {total}" },
  prevPage: { zh: "上一页", en: "Previous" },
  nextPage: { zh: "下一页", en: "Next" },
}
```

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `app/notebooks/page.tsx` | 修改 | 分页状态、查询参数、分页控件渲染 |
| `styles/layout.css` | 修改 | `.notebook-grid` 列宽从 280px 增至 320px |
| `styles/cards.css` | 修改 | `.card` 内边距和最小高度调整 |
| `lib/i18n/strings.ts` | 修改 | 新增分页相关文本 |

> `lib/api/notebooks.ts` 无需修改：`listNotebooks` 返回的 `ApiListResponse` 已含完整 `PaginationInfo`。

## 边界情况

1. **零 notebook**：保持现有空状态展示（"还没有 Notebook"提示 + 操作按钮），不显示分页控件
2. **恰好一页**：不显示分页控件
3. **删除后页面变空**：如果删除操作导致当前页无数据，自动跳转到前一页（`setCurrentPage(p => Math.max(1, p - 1))`）
4. **创建后跳转详情页（保持当前行为）**：创建 notebook 成功后 `invalidateQueries(["notebooks"])`，并保持当前产品行为 `router.push(`/notebooks/${id}`)` 进入新 notebook 详情页；分页逻辑仅影响列表浏览，不改变创建主流程
