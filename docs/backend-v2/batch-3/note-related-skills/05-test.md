# Note-Related-Skills 模块：测试策略

## 1. 测试分层

分三层测试：Skill 框架层、NoteSkillProvider 工具层、集成层。

## 2. Skill 框架测试

### 2.1 SkillRegistry

| 测试用例 | 验证点 |
|---------|--------|
| register 并 match_command | 注册后能正确匹配 slash 命令 |
| match_command 完整消息 | "/note 帮我创建笔记" -> ("note", "帮我创建笔记") |
| match_command 仅命令 | "/note" -> ("note", "") |
| match_command 无匹配 | "普通消息" -> None |
| match_command 前缀不完整 | "/notebook 查询" -> None（不匹配 /note） |
| match_command 大小写 | "/Note 创建" -> None（区分大小写） |
| get_provider 已注册 | 返回对应 Provider |
| get_provider 未注册 | 返回 None |

### 2.2 SkillManifest

| 测试用例 | 验证点 |
|---------|--------|
| 不可变性 | frozen=True，构建后字段不可修改 |
| confirmation_required 判断 | "update_note" in manifest.confirmation_required -> True |
| 工具列表非空 | manifest.tools 包含预期数量的工具 |

## 3. NoteSkillProvider 工具测试

使用 mock 的 NoteService 和 MarkService，测试每个 ToolDefinition 的 execute 函数。

### 3.1 list_notes

| 测试用例 | 验证点 |
|---------|--------|
| 正常查询 | 调用 NoteService.list_by_notebook(notebook_id) |
| 带 document_id 过滤 | 传递 document_id 参数 |
| 无结果 | 返回 "未找到笔记" 提示 |
| 返回格式 | content 为编号列表文本 |

### 3.2 read_note

| 测试用例 | 验证点 |
|---------|--------|
| 正常读取 | 返回标题、内容、关联文档、书签引用 |
| note_id 不存在 | ToolCallResult.error 设置，content 包含错误说明 |

### 3.3 create_note

| 测试用例 | 验证点 |
|---------|--------|
| 仅标题 | 调用 NoteService.create_note(title=...) |
| 带内容和文档关联 | 调用 create_note + add_document_tag |
| 返回信息 | content 包含创建成功提示和 note_id |

### 3.4 update_note

| 测试用例 | 验证点 |
|---------|--------|
| 更新标题 | 调用 NoteService.update_note(title=...) |
| 更新内容 | 调用 NoteService.update_note(content=...) |
| note_id 不存在 | 返回错误 |

### 3.5 delete_note

| 测试用例 | 验证点 |
|---------|--------|
| 正常删除 | 调用 NoteService.delete_note |
| note_id 不存在 | 返回错误 |

### 3.6 list_marks

| 测试用例 | 验证点 |
|---------|--------|
| 按 notebook 查询 | 调用 MarkService.list_by_notebook(notebook_id) |
| 按 document 过滤 | 调用 MarkService.list_by_document(document_id) |
| 返回格式 | content 为编号列表，包含 anchor_text 和文档名 |

### 3.7 associate / disassociate

| 测试用例 | 验证点 |
|---------|--------|
| 关联成功 | 调用 NoteService.add_document_tag |
| 解除关联 | 调用 NoteService.remove_document_tag |
| 幂等关联 | 重复关联不报错 |

## 4. 确认机制集成测试

### 4.1 确认流程

| 测试用例 | 验证点 |
|---------|--------|
| update_note 触发确认事件 | AgentLoop 产出 ConfirmationRequestEvent |
| 用户确认后执行 | 工具正常执行，返回结果 |
| 用户拒绝后反馈 | ToolCallResult.error = "user_rejected" |
| 确认超时 | 60 秒后自动取消，返回超时信息 |
| 非确认工具直接执行 | list_notes、create_note 不触发确认 |

### 4.2 ChatService 集成

| 测试用例 | 验证点 |
|---------|--------|
| /note 消息触发 skill 激活 | SkillManifest 的工具注入到 agent |
| 普通消息不触发 | 工具列表不变 |
| /note 在非 agent mode | 自动切换到 agent mode |
| /note 消息清理 | agent 收到清理后的消息，不含前缀 |
| manifest.description 注入 | system prompt 包含 skill 描述段 |

### 4.3 确认回传 API

| 测试用例 | 验证点 |
|---------|--------|
| POST /chat/confirm 正常确认 | AgentLoop 收到确认，继续执行 |
| POST /chat/confirm 拒绝 | AgentLoop 收到拒绝，返回拒绝结果 |
| request_id 不匹配 | 返回 404 |
| 重复确认 | 幂等，返回已处理 |

## 5. 端到端场景测试

| 场景 | 步骤 | 预期结果 |
|------|------|---------|
| 创建笔记 | 用户: "/note 帮我创建一个关于大模型基础的笔记" | agent 调用 create_note，返回成功 |
| 查询并修改 | 用户: "/note 把第一条笔记的标题改成摘要" | agent 调用 list_notes -> update_note，触发确认，用户确认后执行 |
| 查询书签 | 用户: "/note 当前文档有哪些书签" | agent 调用 list_marks，返回书签列表 |
| 删除被拒绝 | 用户: "/note 删除所有笔记" | agent 逐个调用 delete_note，用户拒绝，agent 反馈 |
