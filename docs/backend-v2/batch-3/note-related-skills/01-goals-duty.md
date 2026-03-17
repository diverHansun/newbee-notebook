# Note-Related-Skills 模块：设计目标与职责边界

## 1. 设计目标

### 1.1 Slash 命令驱动的工具注入

Agent 默认看不到笔记和书签相关工具。只有当用户在聊天输入中使用 `/note` 前缀时，系统才将 note skill 的工具定义注入到当前请求的 agent 工具列表中。这避免了工具列表的膨胀，同时给用户显式的控制权。

### 1.2 用户操作与 agent 操作的语义分离

| 操作方 | 入口 | 确认机制 | 适用场景 |
|--------|------|---------|---------|
| 用户 | Studio UI / REST API | 无需确认（用户直接操作） | 手动创建笔记、添加书签、关联文档 |
| Agent | /note 激活 + 工具调用 | 破坏性操作需用户确认 | agent 按指令操作笔记 |

两者调用同一套 Service 层方法，差异仅在上层控制（确认机制、工具可见性）。

### 1.3 轻量 Skill 抽象，为 batch-4 铺路

引入 SkillManifest、SkillRegistry 两个小抽象。batch-3 中只有 `/note` 一个 skill 实现，但抽象层为 batch-4 的动态 skill 加载（基于 SKILL.md 协议）提供了自然扩展点。

设计原则：不提前构建 batch-4 的完整框架（SKILL.md 解析、scripts/ 执行、动态发现），只建立最小可用的 Manifest + Registry 模式。

### 1.4 破坏性操作确认

Agent 对笔记的更新和删除操作需要用户在前端 UI 确认后才执行。确认机制在 Skill 层声明（哪些工具需要确认），由 engine 层和前端协作实现。

## 2. 职责

### 2.1 SkillManifest

定义 skill 的静态描述信息：名称、slash 命令、包含的工具列表、哪些工具需要确认。

### 2.2 SkillRegistry

管理所有已注册的 skill。提供 slash 命令匹配能力：给定用户消息，返回匹配的 skill 和清理后的消息文本。

### 2.3 NoteSkillProvider

构建 `/note` skill 的 SkillManifest。将 NoteService 和 MarkService 的操作适配为 ToolDefinition 列表。接收请求级上下文（notebook_id）以生成正确的工具定义。

### 2.4 确认事件产出

当 agent 调用需要确认的工具时，产出确认请求事件（ConfirmationRequestEvent），暂停工具执行，等待前端回传确认结果。

## 3. 非职责

- 不实现 SKILL.md 文件解析和动态加载（属于 batch-4）
- 不实现 scripts/ 目录的沙箱执行环境（属于 batch-4）
- 不实现 skill 的安装/卸载/版本管理（属于 batch-4）
- 不负责 Note/Mark 的业务逻辑（属于 note-bookmark Service 层）
- 不负责 Studio UI 的用户操作流程（属于前端）
- 不处理 `/note` 之外的其他 slash 命令（但 SkillRegistry 的设计支持扩展）
