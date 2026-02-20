# 文本选择交互 -- 设计说明

---

## 1. 设计目标

检测用户在 Markdown 查看器渲染区域内的文本选择行为，在选中位置附近显示操作菜单，允许用户触发 explain（解释）或 conclude（总结）操作，并将选中上下文传递给聊天系统。

---

## 2. 职责

- 监听 Markdown 查看器渲染区域内的文本选择事件（mouseup / selectionchange）
- 判断选中内容是否有效（非空、长度合理）
- 在选中文本附近显示浮动操作菜单
- 计算菜单的定位坐标（基于 Selection API 的 getBoundingClientRect）
- 用户点击菜单选项后，将 mode（explain/conclude）和 context（document_id + selected_text）传递给聊天系统的发送方法
- 在以下情况自动关闭菜单：用户点击菜单外区域、选中内容消失、页面滚动

---

## 3. 非职责

- 不负责 Markdown 渲染（由 Markdown 查看器模块完成）
- 不负责消息发送和流式接收（由聊天系统模块完成）
- 不负责 explain/conclude 结果的展示（由聊天系统的 ExplainCard 负责）

---

## 4. 数据流

```
用户在 Markdown 渲染区域选中文本
  |
  v
useTextSelection hook 检测到 selectionchange 事件
  |
  | 防抖处理（200ms）
  v
获取选中文本内容和位置信息
  |
  | 判断选中文本长度 > 0
  v
计算浮动菜单位置（选中区域上方或下方）
  |
  v
显示 SelectionMenu 组件（包含"解释"和"总结"两个按钮）
  |
  v
用户点击"解释"或"总结"
  |
  v
调用聊天系统的 sendMessage：
  mode: "explain" 或 "conclude"
  context: {
    document_id: 当前查看的文档 ID（从 reader-store 获取）,
    selected_text: 选中的文本内容
  }
  |
  v
关闭浮动菜单
```

---

## 5. 关键设计说明

### 5.1 选中检测的防抖

使用 200ms 防抖避免在用户拖拽选择过程中频繁触发菜单显示。只有鼠标释放后 200ms 内选中内容不变，才显示菜单。

### 5.2 菜单定位

基于 `window.getSelection().getRangeAt(0).getBoundingClientRect()` 获取选中文本的位置矩形，菜单默认显示在选中区域上方。如果上方空间不足（距视口顶部 < 菜单高度），则显示在下方。

### 5.3 文件布局

```
components/reader/
  SelectionMenu.tsx          -- 浮动操作菜单 UI
lib/hooks/
  useTextSelection.ts        -- 选中检测 + 位置计算 hook
```

useTextSelection hook 返回：
- `selection`：当前选中信息（text, documentId），null 表示无选中
- `menuPosition`：菜单坐标（top, left）
- `showMenu`：菜单是否可见
- `clearSelection`：手动清除选中状态

### 5.4 与 reader-store 的关系

当前查看的文档 ID 从 reader-store 获取。useTextSelection hook 内部读取 reader-store 的 `currentDocumentId`，不需要外部传入。
