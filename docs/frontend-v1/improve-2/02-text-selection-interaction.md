# P2+P3: 文字选中交互修复

## P2 蓝色选中菜单位置偏移（反向选择）
## P3 操作按钮在鼠标松开前弹出

> 两个问题出自同一文件 `lib/hooks/useTextSelection.ts`，根本原因相互关联，在此联合分析。

---

## 1. 当前问题

### 1.1 涉及文件与代码位置

主逻辑：`frontend/src/lib/hooks/useTextSelection.ts`（全文 69 行）
菜单组件：`frontend/src/components/reader/selection-menu.tsx`
状态管理：`frontend/src/stores/reader-store.ts`（`showMenu`、`hideMenu`、`setSelection`）

### 1.2 事件模型分析

当前实现只监听两个事件：

```
document.addEventListener("selectionchange", handler)   // 第 58 行
window.addEventListener("scroll", hideMenu, true)       // 第 59 行
```

`selectionchange` 的触发时机：鼠标按下（mousedown）开始拖选，直到松开（mouseup），**整个拖拽过程中持续触发**。

handler 内部逻辑（第 17-56 行）：

```
selectionchange 触发
  -> 清除上一个定时器
  -> 设置 200ms 定时器
  -> 定时器到期后：
       读取 selection 内容
       计算菜单坐标
       调用 showMenu({ top, left })
```

### 1.3 P3 的根本原因：没有 mouseup 门控

**问题场景（用户拖选中途停顿 200ms）：**

```
T+0ms    mousedown，开始拖选
T+80ms   selectionchange，定时器重置到 T+280ms
T+200ms  用户停顿（鼠标还按着）
T+280ms  定时器到期 -> showMenu() 被调用
         此时鼠标按键仍处于按下状态！
T+300ms  用户继续拖选
T+380ms  selectionchange，定时器重置
         菜单在拖选中途短暂出现又消失（闪烁）
T+500ms  mouseup，用户完成选择
         菜单再次出现（或因刚才残留状态导致不出现）
```

核心缺失：整个 hook 没有任何 `mouseup` / `pointerup` 监听，无法知道用户是否完成了选择。

### 1.4 P2 的根本原因：位置计算不考虑选择方向

当前位置计算（第 45-48 行）：

```typescript
const rect = range.getBoundingClientRect();
const menuTop = rect.top + window.scrollY - 44;
const top = menuTop < window.scrollY + 12 ? rect.bottom + window.scrollY + 8 : menuTop;
const left = rect.left + window.scrollX + rect.width / 2;
```

`range.getBoundingClientRect()` 始终返回选中区域的**包围盒**（bounding box），不区分选择方向。

- **正向选择**（从左到右/从上到下）：光标当前位置在选区右下角，菜单出现在选区上方是合理的
- **反向选择**（从右到左/从下到上）：光标当前位置在选区左上角，菜单出现在选区上方反而是在光标的上方，不在光标附近，体验割裂

此外，`selectionchange` 事件触发时，`selection.anchorNode`（选择起点）和 `selection.focusNode`（选择终点/当前光标位置）携带了方向信息，但当前代码完全未使用这两个属性。

---

## 2. 解决方案

### 核心思路

用 **状态机** 替代纯事件+防抖模式：

```
状态: idle | selecting | selected

idle      -> mousedown         -> selecting（清除菜单）
selecting -> selectionchange   -> selecting（更新选区，但不显示菜单）
selecting -> mouseup           -> selected（检查选区，显示菜单）
selected  -> mousedown         -> selecting（清除菜单，开始新选择）
selected  -> selectionchange   -> selecting（选区变化，重新进入选择状态）
任意状态  -> scroll            -> idle（隐藏菜单）
```

### 2.1 mouseup 门控

在 useEffect 中新增 `mouseup` 监听，菜单只在 mouseup 后显示：

```typescript
const isSelectingRef = useRef(false);

// mousedown: 标记开始选择，清除当前菜单
const handleMouseDown = () => {
  isSelectingRef.current = true;
  hideMenu();
  setSelection(null);
};

// selectionchange: 仅在选择完成后处理（mouseup 已触发）
const handleSelectionChange = () => {
  if (isSelectingRef.current) return;  // 仍在拖选，忽略
  showMenuFromCurrentSelection();
};

// mouseup: 标记选择结束，显示菜单
const handleMouseUp = () => {
  isSelectingRef.current = false;
  showMenuFromCurrentSelection();
};

document.addEventListener("selectionchange", handleSelectionChange);
document.addEventListener("mousedown", handleMouseDown);
document.addEventListener("mouseup", handleMouseUp);
window.addEventListener("scroll", hideMenu, true);
```

`showMenuFromCurrentSelection()` 封装读取 `selection`、验证、计算坐标、调用 `showMenu` 的逻辑（原 handler 中 setTimeout 内的内容），不再需要防抖定时器。

### 2.2 选择方向感知定位

通过比较 `anchorNode`/`anchorOffset` 与 `focusNode`/`focusOffset` 判断选择方向，将菜单定位到**光标当前所在位置附近**：

```typescript
function getMenuPosition(selection: Selection): { top: number; left: number } {
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();

  // 判断选择方向
  // anchorNode 是起点，focusNode 是终点（当前光标位置）
  const isBackward = isSelectionBackward(selection);

  let anchorTop: number;
  let anchorLeft: number;

  if (isBackward) {
    // 反向选择：光标在选区左上角，菜单放在选区上方左侧对齐
    anchorTop = rect.top + window.scrollY;
    anchorLeft = rect.left + window.scrollX;
  } else {
    // 正向选择：光标在选区右下角，菜单放在选区上方居中
    anchorTop = rect.top + window.scrollY;
    anchorLeft = rect.left + window.scrollX + rect.width / 2;
  }

  const menuTop = anchorTop - 44;
  const top = menuTop < window.scrollY + 12 ? rect.bottom + window.scrollY + 8 : menuTop;

  return { top, left: anchorLeft };
}

// 判断 selection 是否为反向（从后往前）选择
function isSelectionBackward(selection: Selection): boolean {
  if (!selection.anchorNode || !selection.focusNode) return false;
  const position = selection.anchorNode.compareDocumentPosition(selection.focusNode);
  if (position === 0) {
    // 同一节点，比较 offset
    return selection.focusOffset < selection.anchorOffset;
  }
  return !!(position & Node.DOCUMENT_POSITION_PRECEDING);
}
```

### 2.3 容器边界检查不变

mouseup 时仍需检查选区是否在 `containerRef` 内，逻辑与当前代码相同（第 38-43 行），无需调整。

---

## 3. 架构影响与修改点

### 修改文件

**`frontend/src/lib/hooks/useTextSelection.ts`**

具体变更：

| 变更类型 | 内容 |
|----------|------|
| 删除 | `timerRef`（不再需要防抖定时器） |
| 新增 | `isSelectingRef`（选择状态标志） |
| 新增 | `handleMouseDown` 函数 |
| 新增 | `handleMouseUp` 函数 |
| 重命名 | 原 `handler` 改为 `handleSelectionChange` |
| 修改 | `handleSelectionChange` 移除内部 setTimeout，改为调用共享 `showMenuFromCurrentSelection` |
| 新增 | `showMenuFromCurrentSelection` 内部辅助函数（提取原 setTimeout 回调逻辑） |
| 新增 | `getMenuPosition` 内部辅助函数（含方向判断） |
| 新增 | `isSelectionBackward` 内部辅助函数 |
| 修改 | `useEffect` 依赖数组新增 `handleMouseDown`、`handleMouseUp` |
| 修改 | `useEffect` 清理函数新增移除 mousedown/mouseup 监听 |

预计总行数从 69 行增加至约 110 行。

### 非修改文件

- `components/reader/selection-menu.tsx`：无需修改，仍从 store 读取菜单状态渲染
- `stores/reader-store.ts`：无需修改，`showMenu` / `hideMenu` 签名不变
- `components/reader/document-reader.tsx`：无需修改，hook 调用方式不变
- `app/globals.css`：`.selection-menu` 样式无需变更

### 行为变化对比

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 拖选中途停顿 200ms | 菜单提前弹出，干扰选择 | 菜单不出现 |
| 鼠标松开后 | 菜单在 mouseup + 最多 200ms 后出现 | 菜单在 mouseup 后立即出现 |
| 正向选择菜单位置 | 选区中央上方 | 不变（选区中央上方） |
| 反向选择菜单位置 | 选区中央上方（远离光标）| 选区左侧上方（靠近当前光标） |
| 选中内容后继续点击 | `selectionchange` 触发 hideMenu | mousedown 触发 hideMenu（更快更准确） |

### 注意事项

- `mousedown` 监听挂载在 `document` 上，如果用户在文档容器外按下鼠标，同样会触发 `hideMenu`。这是期望行为（等同于点击其他区域收起菜单），与 `selection-menu.tsx` 中现有的 `mousedown` click-outside 逻辑一致，不产生冲突。
- 移动端（touch 事件）不在本次修改范围内。touch 场景使用 `touchstart`/`touchend` 替代 `mousedown`/`mouseup`，如需支持可在后续迭代添加。
