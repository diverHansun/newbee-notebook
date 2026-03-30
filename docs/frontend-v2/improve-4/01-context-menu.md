# 右键菜单设计规范

## 功能定位

右键菜单（Context Menu）是本次改进的入口层，负责收拢原来分散在卡片底部的操作按钮，并新增"编辑信息"入口。用户在任意 Notebook 卡片上点击鼠标右键即可触发。

## 交互行为

### 触发

- 在 `.notebook-card` 上监听 `onContextMenu` 事件
- 调用 `e.preventDefault()` 阻止浏览器默认右键菜单
- 调用 `e.stopPropagation()` 防止事件冒泡

### 菜单项

| 顺序 | 菜单项 | 操作 |
|------|--------|------|
| 1 | 编辑信息 | 打开编辑 Modal，预填当前 notebook 的 title 和 description |
| 2 | 删除 | 触发现有的删除确认流程（`setPendingDeleteNotebook`） |

删除项使用危险色（`--destructive`），与其他项在视觉上区分。

### 定位

菜单以 `position: fixed` 渲染在 `document.body` 层级，坐标取自鼠标事件的 `clientX / clientY`。需做边界检测，防止菜单溢出视口：

```
menuLeft = Math.min(e.clientX, window.innerWidth - MENU_WIDTH - 8)
menuTop  = Math.min(e.clientY, window.innerHeight - MENU_HEIGHT - 8)
```

`MENU_WIDTH` 约 160px，`MENU_HEIGHT` 约 80px（两个菜单项）。

### 关闭机制

以下任意操作关闭菜单：

- 点击菜单外任意区域（监听 `document` 的 `mousedown` 事件）
- 按下 `Escape` 键
- 点击菜单项（执行操作后自动关闭）
- 页面滚动（监听 `scroll` 事件）

### 状态管理

在 `page.tsx` 中新增状态：

```typescript
type ContextMenuState = {
  notebookId: string;
  title: string;
  description: string | null;
  x: number;
  y: number;
};

const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
```

`contextMenu` 为 `null` 时菜单不渲染。

## 组件设计

右键菜单以独立组件 `NotebookContextMenu` 实现，通过 React Portal 挂载到 `document.body`，避免被 `overflow: hidden` 的父容器裁剪。

组件接收以下 props：

```typescript
type NotebookContextMenuProps = {
  x: number;
  y: number;
  notebook: { notebookId: string; title: string; description: string | null };
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
};
```

## 样式规范

沿用项目 CSS 变量，不新增 CSS 类以外的依赖：

```css
.notebook-context-menu {
  position: fixed;
  z-index: 200;
  min-width: 160px;
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  background: hsl(var(--card));
  box-shadow: 0 8px 16px -4px rgba(0, 0, 0, 0.12), 0 4px 6px -2px rgba(0, 0, 0, 0.06);
  padding: 4px;
  outline: none;
}

.notebook-context-menu-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  font-size: 13px;
  border-radius: calc(var(--radius) - 2px);
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: hsl(var(--foreground));
}

.notebook-context-menu-item:hover {
  background: hsl(var(--accent));
}

.notebook-context-menu-item--danger {
  color: hsl(var(--destructive));
}

.notebook-context-menu-item--danger:hover {
  background: hsl(var(--destructive) / 0.08);
}
```

## 与现有删除流程的衔接

菜单点击"删除"后，直接调用 `page.tsx` 中已有的 `setPendingDeleteNotebook`，复用现有的 `ConfirmDialog` 删除确认弹窗，无需修改删除逻辑。
