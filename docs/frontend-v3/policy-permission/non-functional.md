# policy-permission 前端模块 non-functional.md

本文档说明 `frontend-v3/policy-permission` 模块的非功能约束。该模块处于 agent 工具执行的信任路径上，重点不是复杂视觉，而是清晰、可靠、可恢复。

---

## 一、Quality Priorities（质量优先级）

1. **可信度优先于视觉表现**
   - 用户看到的 policy 必须与后端实际执行策略一致。
   - 不允许出现“UI 显示默认权限，但请求按完全访问发送”的状态。

2. **可理解性优先于信息完整性**
   - 本阶段不展示风险等级、capability signature、content hash 等内部字段。
   - 用户只看到必要的人类语言描述、工具名和参数摘要。

3. **交互低干扰**
   - policy selector 常驻但低占用。
   - permission card 只在需要审批时出现。
   - 不新增全屏 modal 或阻断式设置页。

4. **样式一致性优先于新视觉体系**
   - 复用现有按钮、badge、CSS variables。
   - 新 UI 看起来应属于当前 chat panel。

---

## 二、Operational Constraints（运行约束）

1. **输入框布局不得被权限控件撑开**
   - policy button 文案必须有最大宽度。
   - 小屏时可使用短标签或隐藏来源副文本。
   - toolbar 仍能容纳 Agent/Ask、source selector、send button。

2. **Permission Card 按钮必须自适应**
   - 桌面端可横向排列或两列排列。
   - 移动端允许变成单列。
   - 长文案如 `本会话始终允许` 不得溢出按钮。

3. **菜单浮层不得遮挡输入主路径**
   - policy menu 应靠近触发按钮。
   - 点击外部、Escape、选择菜单项均应关闭。
   - stream 进行中可禁用切换或明确展示不可切换状态。

4. **API 状态更新必须防止乱序覆盖**
   - 连续切换 policy 时，慢请求不能覆盖较新的用户选择。
   - 可以使用 request sequence 或 updatedAt 判定。

---

## 三、Reliability & Observability（可靠性与可观测性）

1. **失败必须显性化**
   - confirm 失败、policy 更新失败都必须在 UI 中出现可见反馈。
   - 不允许静默失败后继续展示错误 policy。

2. **权限事件应可调试**
   - 前端保留 `request_id`、`tool_name`、`capability_signature` 等字段。
   - 开发调试时可通过 React DevTools 或日志定位一次 permission request。

3. **卡片状态必须可恢复**
   - pending → resolving → confirmed/rejected/collapsed 是正常路径。
   - resolving → error 后允许重试。
   - timeout 不改变 policy state。

4. **无障碍基本要求**
   - policy selector button 必须有 aria-label。
   - menu item 使用可键盘访问的 button。
   - 当前选中项应通过文本或 check mark 表达，不只依赖颜色。
   - focus-visible 样式复用现有 ring。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

1. **暂缓 Auto Review**
   - 原因：后端尚无第三种 policy 语义。
   - 后续若增加，可在 policy menu 中加入第三项，并扩展 `AgentPolicy`。

2. **暂缓风险等级展示**
   - 原因：会引入解释成本和误解风险。
   - 后续若显示，应先定义风险文案、颜色、触发规则和测试。

3. **暂缓复杂权限历史面板**
   - 原因：当前用户只需要即时切换与即时审批。
   - 后续如需要查看 notebook 授权记录，可作为独立模块。

4. **暂缓全局快捷键**
   - 原因：权限切换是低频高风险操作，不适合初期绑定快捷键。

5. **不追求视觉强提醒**
   - `完全访问权限` 使用 amber 强调即可。
   - 不使用大红色警告态，避免把 sandbox 内完全访问误导成系统级危险。
