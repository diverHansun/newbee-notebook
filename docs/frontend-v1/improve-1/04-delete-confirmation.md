# 04 - 删除操作二次确认与样式优化

## 当前问题

### 问题 A: 所有删除/移除按钮均无二次确认

前端中所有的删除和移除操作在点击后立即执行，没有任何确认对话框。
这对于不可逆操作（如彻底删除文档、删除 Notebook）存在严重的误操作风险。

### 问题 B: "移除"按钮样式未体现危险性

Notebook Sources 中的"移除"按钮使用灰色（muted）样式，
未能向用户传达该操作的危险性，容易误触。

## 根因分析

### 全部删除/移除按钮清单

经过代码级排查，前端共有 6 处删除/移除操作:

| 编号 | 操作 | 文件位置 | 行号 | 后端端点 | 影响范围 | 当前有确认 |
|------|------|----------|------|----------|----------|------------|
| 1 | 删除 Notebook | `app/notebooks/page.tsx` | 162 | `DELETE /notebooks/{id}` | 级联删除全部会话和关联 | 否 |
| 2 | 移除文档（从 Notebook） | `components/sources/source-card.tsx` | 105 | `DELETE /notebooks/{id}/documents/{id}` | 仅移除关联，文档保留 | 否 |
| 3 | 删除会话 | `components/chat/chat-panel.tsx` | 81 | `DELETE /sessions/{id}` | 级联删除全部消息 | 否 |
| 4 | 删除文档（Library 软删除） | `app/library/page.tsx` | 228 | `DELETE /library/documents/{id}` | 删除索引和数据库记录，保留文件 | 否 |
| 5 | 彻底删除文档（Library 硬删除） | `app/library/page.tsx` | 237 | `DELETE /library/documents/{id}?force=true` | 删除全部数据和磁盘文件，不可逆 | 否 |
| 6 | 批量删除文档 | `app/library/page.tsx` | 262 | 循环调用 `DELETE /library/documents/{id}` | 批量软删除 | 否 |

### 当前按钮样式

| 操作 | 当前颜色 | 是否合理 |
|------|----------|----------|
| 删除 Notebook | 红色（destructive） | 合理 |
| 移除文档 | 灰色（muted-foreground） | 不合理，应为红色 |
| 删除会话 | 红色（destructive） | 合理 |
| 删除文档（软） | 默认色 | 不合理，应提示危险 |
| 彻底删除文档 | 红色（destructive） | 合理 |
| 批量删除 | 红色（destructive） | 合理 |

## 解决方案

### 方案 1: 使用 window.confirm 添加确认（最小改动）

对所有删除/移除操作添加 `window.confirm` 二次确认。
这是最快速、侵入性最小的方案。

**示例改动** (`app/notebooks/page.tsx` 删除 Notebook):

```typescript
// 修改前
onClick={(e) => {
  e.stopPropagation();
  deleteMutation.mutate(notebook.notebook_id);
}}

// 修改后
onClick={(e) => {
  e.stopPropagation();
  if (window.confirm(`确定要删除笔记本「${notebook.title}」吗？此操作将删除所有相关会话，且不可撤销。`)) {
    deleteMutation.mutate(notebook.notebook_id);
  }
}}
```

### 方案 2: 封装 ConfirmDialog 组件（推荐）

创建一个可复用的确认对话框组件，提供更好的用户体验。
使用 HTML `<dialog>` 元素或简单的模态实现。

**组件接口设计:**

```typescript
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;   // 默认 "确认"
  cancelLabel?: string;    // 默认 "取消"
  variant?: "danger" | "warning";  // 控制确认按钮颜色
  onConfirm: () => void;
  onCancel: () => void;
}
```

**使用方式:**

```typescript
const [confirmOpen, setConfirmOpen] = useState(false);

<button onClick={() => setConfirmOpen(true)}>删除</button>

<ConfirmDialog
  open={confirmOpen}
  title="删除笔记本"
  message={`确定要删除「${notebook.title}」吗？此操作不可撤销。`}
  variant="danger"
  confirmLabel="删除"
  onConfirm={() => {
    deleteMutation.mutate(notebook.notebook_id);
    setConfirmOpen(false);
  }}
  onCancel={() => setConfirmOpen(false)}
/>
```

### 各按钮的确认文案

| 操作 | 确认标题 | 确认消息 | variant |
|------|----------|----------|---------|
| 删除 Notebook | 删除笔记本 | 确定要删除笔记本「{title}」吗？所有相关会话将被一并删除，此操作不可撤销。 | danger |
| 移除文档 | 移除文档 | 确定要从当前笔记本中移除「{title}」吗？文档本身不会被删除，可以重新添加。 | warning |
| 删除会话 | 删除会话 | 确定要删除此会话吗？所有聊天记录将被删除。 | danger |
| 删除文档（软） | 删除文档 | 确定要删除「{title}」吗？索引数据将被清除，但原始文件保留。 | warning |
| 彻底删除文档 | 彻底删除文档 | 确定要彻底删除「{title}」吗？原始文件和所有相关数据将被永久删除，此操作不可撤销。 | danger |
| 批量删除 | 批量删除文档 | 确定要删除选中的 {count} 个文档吗？ | danger |

### 样式修复: "移除"按钮改为红色

**文件:** `frontend/src/components/sources/source-card.tsx:105-112`

```typescript
// 修改前
style={{ color: "hsl(var(--muted-foreground))" }}

// 修改后
style={{ color: "hsl(var(--destructive))" }}
```

**文件:** `frontend/src/app/library/page.tsx:228-236` （软删除按钮）

软删除按钮也应添加适当的颜色提示:

```typescript
// 增加
style={{ color: "hsl(var(--destructive))" }}
```

## 对架构的影响

### 方案 1（window.confirm）

- 零架构影响，每处改动仅增加一行条件判断
- 缺点: 原生对话框样式无法自定义，与应用风格不统一

### 方案 2（ConfirmDialog 组件）

- 新增一个共享 UI 组件: `frontend/src/components/ui/confirm-dialog.tsx`
- 所有使用删除功能的组件需要增加状态管理（open/close）
- 优点: 统一的交互体验，可自定义样式和文案

建议: 第一阶段先用方案 1 快速修复安全问题，后续再替换为方案 2 提升体验。

## 具体修改点

| 文件 | 修改内容 |
|------|----------|
| `app/notebooks/page.tsx:162` | 添加删除 Notebook 确认 |
| `components/sources/source-card.tsx:105` | 添加移除确认 + 按钮改为红色 |
| `components/sources/source-list.tsx:210` | 配合 source-card 的确认逻辑 |
| `components/chat/chat-panel.tsx:81` | 添加删除会话确认 |
| `app/library/page.tsx:228` | 添加软删除确认 + 按钮加红色 |
| `app/library/page.tsx:237` | 添加彻底删除确认 |
| `app/library/page.tsx:262` | 添加批量删除确认 |
| （新建）`components/ui/confirm-dialog.tsx` | 确认对话框组件（方案 2） |

## 验证方法

1. 逐一点击每个删除/移除按钮，确认弹出确认对话框
2. 点击"取消"后确认操作未执行
3. 点击"确认"后确认操作正常执行
4. 确认移除按钮和软删除按钮颜色已改为红色
5. 确认确认文案准确描述了操作后果
