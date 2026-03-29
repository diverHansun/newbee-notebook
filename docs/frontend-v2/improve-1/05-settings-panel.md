# 设置面板精简

## 背景

当前设置面板（Control Panel）包含多个功能 Tab，其中 RAG 功能在项目架构中已被其他方式替代或暂时隐藏。同时，Skills 功能尚在开发中，应显示为"即将推出"状态。

## 现状分析

### 当前 ControlPanel 结构

`control-panel.tsx` 中定义的功能项：

```typescript
const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "model" },
  { key: "mcp" },
  { key: "data" },
];

const DISABLED_ITEMS: DisabledNavItem[] = [
  { key: "rag" },
  { key: "skills" },
];
```

导航图标定义中的 `ControlPanelNavIconName`：

```typescript
type ControlPanelNavIconName =
  | ControlPanelTab
  | "rag"
  | "mcp"
  | "skills";
```

### 需移除的内容

1. **RAG Tab** - 从 `ACTIVE_ITEMS` 中移除，从导航中完全删除
2. **Skills 保持禁用状态** - 已在 `DISABLED_ITEMS` 中，无需修改

## 设计方案

### 改动范围

仅修改前端代码，不涉及后端 API 变更。

#### 1. 类型定义简化

移除 `ControlPanelNavIconName` 中的 "rag" 类型：

```typescript
// 改动前
type ControlPanelNavIconName =
  | ControlPanelTab
  | "rag"    // 移除
  | "mcp"
  | "skills";

// 改动后
type ControlPanelNavIconName =
  | ControlPanelTab
  | "mcp"
  | "skills";
```

#### 2. ActiveItems 精简

```typescript
// 改动前
const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "model" },
  { key: "mcp" },
  { key: "data" },
];

// 改动后
const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "model" },
  { key: "mcp" },
  { key: "data" },
  { key: "about" },  // about 已在底部导航实现
];
```

注意：`about` 实际上在 `control-panel.tsx` 中是单独在 `control-panel-nav-footer` 中实现的，不是通过 `ACTIVE_ITEMS` 渲染。

#### 3. 导航图标组件清理

删除 `ControlPanelNavIcon` 中的 `case "rag"` 分支：

```typescript
function ControlPanelNavIcon({ name }: { name: ControlPanelNavIconName }) {
  switch (name) {
    case "language":
      // ...
    case "theme":
      // ...
    case "model":
      // ...
    // case "rag":  // 删除此分支
    //   return (...);
    case "mcp":
      // ...
    case "data":
      // ...
    case "skills":
      // ...
    case "about":
      // ...
    default:
      return null;
  }
}
```

#### 4. i18n 字符串清理（可选）

如果后续确定 RAG 不再需要，可以在 `uiStrings.controlPanel` 中移除 `rag` 相关翻译。但为保持扩展性，建议保留翻译键值，暂不处理。

## 界面影响

### 变更前

```
+-------+
| Lang  |
| Theme |
| Model |
| MCP   |
| Data  |
| RAG   |  <-- 有点击效果
|Skills |  <-- 禁用状态
|About  |
+-------+
```

### 变更后

```
+-------+
| Lang  |
| Theme |
| Model |
| MCP   |
| Data  |
|       |  <-- RAG 已移除
|      |  <-- 禁用状态
|About |
+-------+
```

## 改动文件清单

| 文件 | 改动内容 |
|------|----------|
| `frontend/src/components/layout/control-panel.tsx` | 移除 RAG 相关类型和导航项 |
| `frontend/src/styles/control-panel.css` | 检查并移除 RAG 相关样式（如有） |

## 测试要点

1. 验证设置面板正常打开和关闭
2. 验证所有活跃 Tab（language、theme、model、mcp、data）可正常切换
3. 验证 Skills 保持"即将推出"禁用状态
4. 验证 RAG 导航项已完全移除
5. 验证响应式布局在不同屏幕尺寸下正常

## 兼容性考虑

- 不修改任何 API 契约
- 不影响现有用户设置
- 不影响聊天功能
