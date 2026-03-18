# 前端测试策略

## 1. 测试分层

前端测试分为三层：组件单元测试、交互集成测试、端到端场景测试。

对齐说明：

- batch-3 前端测试建立在“先补 Vitest + React Testing Library 基建”的前提上
- `StudioView` 命名统一使用 `"home" | "notes" | "note-detail"`
- `[[mark:id]]` 的 preview 点击联动属于后续增强，不纳入 batch-3 必测范围

## 2. 组件单元测试

使用 Vitest + React Testing Library。

### 2.1 SelectionMenu

| 测试用例 | 验证点 |
|---------|--------|
| 渲染三个按钮 | Explain、Conclude、Bookmark 按钮均可见 |
| 点击书签按钮 | 调用 onMark 回调，传递 documentId 和 selectedText |
| 点击书签后菜单关闭 | hideMenu 被调用 |
| 书签按钮与 AI 按钮视觉分隔 | 分隔线元素存在 |

### 2.2 SlashCommandHint

| 测试用例 | 验证点 |
|---------|--------|
| 输入 "/" 显示面板 | 面板可见，列出可用命令 |
| 输入 "/n" 过滤命令 | 只显示匹配 "/n" 的命令 |
| 输入 "/note " 隐藏面板 | 空格后面板消失 |
| 键盘上下键导航 | 高亮项切换 |
| Enter 选择命令 | onSelect 被调用，传递完整命令 |
| Escape 关闭面板 | onDismiss 被调用 |
| 不可用命令灰显 | available=false 的命令不可选择 |

### 2.3 ConfirmationCard

| 测试用例 | 验证点 |
|---------|--------|
| pending 状态渲染 | 显示操作描述、确认和拒绝按钮 |
| 点击确认 | onConfirm 被调用 |
| 点击拒绝 | onReject 被调用 |
| confirmed 状态渲染 | 显示已确认摘要，无按钮 |
| rejected 状态渲染 | 显示已拒绝摘要，无按钮 |
| timeout 状态渲染 | 显示已超时摘要，无按钮 |

### 2.4 StudioHome

| 测试用例 | 验证点 |
|---------|--------|
| 渲染卡片网格 | Notes & Marks 卡片可见 |
| 点击可用卡片 | navigateTo("notes") 被调用 |
| 不可用卡片不可点击 | Mind Map 卡片灰显，点击无响应 |
| 卡片网格 2 列布局 | grid-template-columns 为 2 列 |

### 2.5 NoteCard

| 测试用例 | 验证点 |
|---------|--------|
| 显示标题和关联文档 | 标题文本和文档 pill 可见 |
| 显示更新时间 | 时间文本可见 |
| 点击卡片 | 触发 openNoteEditor |

### 2.6 NoteEditor

| 测试用例 | 验证点 |
|---------|--------|
| 加载 note 数据 | 标题和内容正确显示 |
| 编辑标题 | input onChange 触发 |
| 编辑内容 | textarea onChange 触发 |
| 自动保存 debounce | 变更后 5 秒内调用 updateNote API |
| Ctrl+S 立即保存 | 按键后立即调用 updateNote API |
| 保存状态指示器 | 显示 "已保存" / "保存中..." / "未保存" |
| 删除弹出确认 | ConfirmDialog 弹出 |
| 确认删除后返回列表 | deleteNote API 调用，视图切换 |

### 2.7 MarkInlinePicker

| 测试用例 | 验证点 |
|---------|--------|
| 输入 "[["  触发弹出 | popover 可见 |
| 搜索过滤 | 模糊匹配 anchor_text |
| 键盘选择 | 上下键导航，Enter 确认 |
| 选中后插入 | textarea 光标位置插入 [[mark:id]] |
| Escape 关闭 | popover 消失 |

### 2.8 MarksSection

| 测试用例 | 验证点 |
|---------|--------|
| 折叠/展开 | 点击标题切换 |
| 按文档分组展示 | 分组标题为文档名 |
| 文档筛选 | 筛选后只显示指定文档的 marks |
| 点击 mark 项 | 联动 Reader（studioStore 更新） |

## 3. 交互集成测试

### 3.1 书签创建流程

| 测试用例 | 验证点 |
|---------|--------|
| 选中文本 -> 点击书签 -> API 调用 | createMark 被调用，参数包含 anchor_text 和 char_offset |
| 创建成功后刷新 | marks query 被 invalidate |
| 创建失败提示 | 错误信息显示 |

### 3.2 slash 命令完整流程

| 测试用例 | 验证点 |
|---------|--------|
| 输入 /note -> 选择 -> 发送 | 消息以 "/note ..." 发送到后端 |
| 收到 confirmation_request -> 渲染卡片 | 内联确认卡片出现在消息中 |
| 点击确认 -> API 调用 -> 流继续 | confirmAction API 调用，后续内容正常渲染 |
| 点击拒绝 -> API 调用 -> agent 反馈 | 拒绝信息传递，agent 回复可见 |

### 3.3 跨面板联动

| 测试用例 | 验证点 |
|---------|--------|
| Reader 书签图标点击 | studioStore.activeMarkId 更新 |
| Studio mark 点击 | Reader 打开文档并滚动 |
| 非当前视图收到 activeMarkId | Studio 自动切到 notes 视图并展开 marks 区 |

### 3.4 Note 编辑与 Mark 引用

| 测试用例 | 验证点 |
|---------|--------|
| textarea 输入 [[ 触发 picker | MarkInlinePicker 弹出 |
| picker 中选择 mark | [[mark:id]] 插入 textarea |
| Available Marks 面板 Insert 按钮 | [[mark:id]] 插入 textarea 光标位置 |
| 文档关联标签添加 | addNoteDocument API 调用 |
| 文档关联标签删除 | ConfirmDialog 弹出，确认后 removeNoteDocument API 调用 |

## 4. 端到端场景测试

| 场景 | 步骤 | 预期结果 |
|------|------|---------|
| 创建书签并查看 | 在 Reader 选中文本 -> 点击书签 -> 打开 Studio Marks | Studio 中可见新创建的书签 |
| 创建笔记并引用书签 | Studio 新建 note -> 输入 [[ -> 选择 mark -> 保存 | Note 内容包含 [[mark:id]]，保存成功 |
| Agent 修改笔记需确认 | 输入 "/note 修改笔记标题" -> agent 请求确认 -> 用户确认 | 确认卡片出现，确认后笔记更新 |
| Agent 删除被拒绝 | 输入 "/note 删除笔记" -> agent 请求确认 -> 用户拒绝 | 确认卡片显示已拒绝，agent 反馈 |
| 确认超时 | 输入 "/note 更新内容" -> 等待 3 分钟不操作 | 卡片显示已超时，agent 收到超时反馈 |

## 5. 国际化测试

| 测试用例 | 验证点 |
|---------|--------|
| 切换到英文 | 所有新增文本显示英文 |
| 切换到中文 | 所有新增文本显示中文 |
| 插值文本 | "{n} 条笔记" / "{n} notes" 正确替换 |
| 确认卡片文本 | 确认/拒绝/已确认/已拒绝 按语言显示 |
| slash 命令提示 | 命令描述按语言显示 |
