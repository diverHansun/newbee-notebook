# policy-permission 前端模块 goals-duty.md

本文档描述 `frontend-v3/policy-permission` 前端模块的目标与职责边界。该模块服务于 backend-v4 的 `policy` / `permission` / `sandbox` 机制，使用户能在对话界面中理解并控制 agent 的执行权限。

---

## 一、Design Goals（设计目标）

1. **把权限控制放回用户可理解的对话语境中**
   - 用户不需要理解 sandbox、bash executor、capability signature 等内部概念。
   - 用户只需要看到：agent 想做什么、这次是否允许、之后是否自动允许。

2. **让 policy 选择像输入框的一部分，而不是一个独立设置页**
   - 权限选择应靠近发送框，类似 Codex 输入框下方的权限按钮。
   - 用户可以在继续对话前随时切换 `默认权限` / `完全访问权限`。

3. **用新版 Permission Request Card 替代硬编码 Permission Request Card**
   - 前端不再根据 `action_type + target_type` 写死标题矩阵。
   - 卡片应优先消费后端传来的 `description`、`tool_name`、`args_summary`、`response_options`。

4. **明确权限作用域**
   - `允许本次` 只作用于当前 permission request。
   - `本会话始终允许` 只作用于当前 session。
   - `永久允许` 作用于当前 notebook 下所有 sessions。

5. **保持 sandbox 始终存在**
   - `完全访问权限` 表示不触发审批，不表示脱离 sandbox。
   - UI 文案必须避免让用户误以为 agent 能直接越过 backend sandbox。

6. **保持前端改动克制**
   - 主要改动集中在 chat main panel：消息审批卡、发送框下方 policy selector、API 类型与 hook 状态。
   - 不新增面向用户的 bash 输入框、sandbox 配置面板或工具控制台。

---

## 二、Duties（职责）

1. **展示当前有效 policy**
   - 在发送框工具栏中展示当前 policy：`默认权限` 或 `完全访问权限`。
   - policy 状态应能表达其来源：默认、当前 session、当前 notebook。

2. **提供 policy 切换入口**
   - 用户可在发送框下方打开 policy menu。
   - 用户选择 `默认权限` 时，后续敏感操作重新进入审批流程。
   - 用户选择 `完全访问权限` 时，后续请求以完全访问策略发送给后端。

3. **渲染 Permission Request Card**
   - 当 SSE 收到 `confirmation_request` 时，在对应 assistant message 下渲染审批卡。
   - 卡片展示操作描述、工具名、关键参数摘要、权限作用域说明。

4. **支持四类审批动作**
   - `允许本次` → `response: "once"`。
   - `本会话始终允许` → `response: "always_session"`，并把当前 session policy 切到完全访问。
   - `永久允许` → `response: "always_persist"`，并把当前 notebook policy 切到完全访问。
   - `拒绝` → `response: "reject"`。

5. **维护前端权限状态的一致性**
   - session 级授权不得泄漏到其他 sessions。
   - notebook 级授权应在同一 notebook 的 sessions 间共享。
   - 用户手动切回默认权限后，UI 与后端请求策略必须同步。

6. **与 backend-v4 API 契约对齐**
   - 前端确认接口必须从旧 `approved: boolean` 升级为 `response` choice。
   - chat stream / chat once 请求必须携带当前有效 `agent_policy`。
   - `confirmation_request` 类型应兼容 backend-v4 已输出的扩展字段。

7. **提供可测试的用户行为**
   - policy selector 的显示、切换、作用域生效必须能通过组件测试或 hook 测试验证。
   - permission card 的四个按钮必须能验证其 API payload 与 UI 状态变化。

---

## 三、Non-Duties（非职责）

1. **不负责真正执行权限判定**
   - 前端只展示和提交用户选择。
   - 是否允许工具执行仍由后端 `policy` / `permission` 模块决定。

2. **不负责 sandbox 运行与文件隔离**
   - Docker-backed sandbox、notebook `/work`、bash-in-container 等能力属于 backend-v4。
   - 前端不提供 sandbox 管理面板。

3. **不提供用户可输入的 bash / PowerShell 面板**
   - bash 是 agent 工具能力，不是用户手动命令行。

4. **本阶段不展示风险等级**
   - `risk_level` 可进入前端数据模型，但不在 UI 上显示。
   - 后续如增加 `自动审查` 或风险解释，可再扩展。

5. **本阶段不实现 Auto Review 第三策略**
   - 当前后端只有 `default` 与 `yolo` 两类 agent policy。
   - menu 可在设计上预留位置，但不显示或不启用 `自动审查`。

6. **不重做整个 chat UI**
   - 本模块只调整权限相关交互。
   - 不改消息渲染、检索来源、studio 面板、reader 面板等无关结构。

7. **不把旧 skill confirmation 规则继续扩散到前端**
   - notes / diagram / videos 等旧确认逻辑应逐步由统一 permission card 承载。
   - 前端不再新增面向具体 skill 的硬编码规则。
