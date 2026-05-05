# policy 模块 dfd-interface.md

本文档描述 `newbee_notebook/core/policy/` 模块的数据流与对外接口，说明数据如何进入模块、经何种处理、以何种形态输出。设计严格基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

---

## 一、Context & Scope（上下文与范围）

policy 模块处于 agent_loop 工具调用链的**决策节点**：每次工具执行前，agent_loop 调用 `PolicyDecider.decide()` 获取裁定结果。

### 与外部模块的交互关系

| 方向 | 模块 | 角色 |
|------|------|------|
| 输入来源 | agent_loop | 调用方，传入 `DecideRequest` |
| 输入来源 | SessionPolicyState（内部） | 维护当前 session 的 agent policy 档位 |
| 输入来源 | SkillRegistry（经 agent_loop 透传） | 提供 `SkillContext(name, content_hash)` |
| 输出去向 | agent_loop | 返回 `Decision`（ALLOW / ASK） |
| 输出去向 | permission（经 agent_loop） | `ASK` 决策触发 agent_loop 调 `permission.request()` |
| 不交互 | DB / AppSettingsService | policy 不读 DB（见 goals-duty N4） |
| 不交互 | sandbox | policy 信任 sandbox 保证隔离，不直接调用 |

### 本文档范围

仅描述 policy 模块内部的数据流——从接收 `DecideRequest` 到产出 `Decision` 的全过程。不描述 agent_loop 收到 Decision 后的调度逻辑（那是 agent_loop 的职责），也不描述 permission 如何弹卡（那是 permission 的职责）。

---

## 二、Data Flow Description（数据流描述）

policy 的数据流是**纯函数管线**：一次同步调用，无 IO、无副作用、无状态变更（除 SessionPolicyState 的读写）。

### 主路径：工具调用前的决策裁定

```
agent_loop
  │
  │  DecideRequest(session_id, agent_policy, tool_class, risk_level,
  │                 tool_name, tool_args, skill_context)
  ▼
PolicyDecider.decide()
  │
  ├─(1)─ SessionPolicyState.get(session_id)  →  agent_policy（若 DecideRequest 未携带）
  │
  ├─(2)─ [若 tool_class==bash] DangerousCommandMatcher.maybe_upgrade(command)
  │       对 command 做字面量模式匹配，命中则 risk_level → dangerous
  │
  ├─(3)─ DecisionMatrix.lookup(agent_policy, tool_class, risk_level)
  │       ┌──────────────────────────────────────────────────────┐
  │       │ default 档位：                                       │
  │       │   (default, read, *)                 → ALLOW         │
  │       │   (default, edit, *)                 → ASK           │
  │       │   (default, write, *)                → ASK           │
  │       │   (default, bash, safe|moderate)     → ALLOW         │
  │       │   (default, bash, dangerous)         → ASK           │
  │       │   (default, mcp, *)                  → 透传自声明     │
  │       │   (default, custom, *)               → ASK           │
  │       │                                                      │
  │       │ yolo 档位：                                          │
  │       │   (yolo, *, *)                       → ALLOW         │
  │       └──────────────────────────────────────────────────────┘
  │       输出 verdict ∈ {ALLOW, ASK}
  │       DENY 不在矩阵中——仅由 agent_loop 在用户拒绝时构造
  │
  ├─(4)─ SignatureBuilder.build(tool_name, tool_args, skill_context)
  │       构造 capability_signature:
  │         scope = "global"
  │           或 "skill:<name>@<content_hash>"（若 skill_context 非 None）
  │         arg_hash8 = SHA-256(canonical_json(args))[:8]
  │         signature = "{scope}:{tool_name}:{arg_hash8}"
  │
  └─(5)─ 组装 Decision(verdict, capability_signature, reason)
         reason 为人可读字符串，如 "yolo 模式自动允许"
  │
  ▼
agent_loop 收到 Decision
  ├── verdict==ALLOW → 执行工具
  └── verdict==ASK   → 调 permission.request(capability_signature, ...)
```

### 辅助路径：会话档位切换

```
chat-input UI / Commands
  │
  │  set_policy(session_id, "yolo")
  ▼
SessionPolicyState.set(session_id, "yolo")
  │
  ├─ 更新内存 dict
  └─ 发 SSE 事件 "agent_policy_changed" → 前端工具栏指示器实时同步
```

### 辅助路径：档位读取

```
agent_loop
  │
  │  get_policy(session_id)
  ▼
SessionPolicyState.get(session_id)
  │
  └─ 返回 "default" | "yolo"（未设置时默认 "default"）
```

### 关键分支条件

| 条件 | 行为 |
|------|------|
| agent_policy == "yolo" | 跳过危险命令匹配与矩阵查表，直接 ALLOW（仍构造 signature） |
| tool_class == "bash" | 先过 DangerousCommandMatcher 升级 risk_level，再查矩阵 |
| skill_context is None | scope 为 "global"，不绑定 skill 维度 |
| skill_context is not None | scope 为 "skill:<name>@<content_hash>" |
| ask 模式误调用 | PolicyDecider 防御性断言抛错（ask 模式不应出现在调用栈中） |

---

## 三、Interface Definition（接口定义）

### 3.1 对外暴露接口

#### PolicyDecider.decide()

- **调用方**：agent_loop
- **语义**：对一次工具调用做出裁定
- **输入**：`DecideRequest`
  - `session_id: str` — 会话标识，用于从 SessionPolicyState 读取档位（若 DecideRequest 未携带 agent_policy）
  - `agent_policy: "default" | "yolo" | None` — 优先使用此值；为 None 时从 SessionPolicyState 读取
  - `tool_class: ToolClass` — 工具类别枚举
  - `risk_level: RiskLevel` — 工具自声明风险等级
  - `tool_name: str` — 工具名称
  - `tool_args: dict` — 工具参数（用于构造 arg_hash8）
  - `skill_context: SkillContext | None` — 活跃 skill 上下文
- **输出**：`Decision`
  - `verdict: "ALLOW" | "ASK"`
  - `capability_signature: str` — 供 permission 使用的规范化签名
  - `reason: str` — 人可读的决策理由
- **同步/异步**：同步纯函数（无 await、无 IO）
- **错误**：仅在 ask 模式误调用时抛 `PolicyError("policy invoked in ask mode")`

#### SessionPolicyState.get()

- **调用方**：agent_loop、chat 入口
- **语义**：读取当前 session 的 agent policy 档位
- **输入**：`session_id: str`
- **输出**：`"default" | "yolo"`（不存在时默认 `"default"`）

#### SessionPolicyState.set()

- **调用方**：chat-input UI、Commands（未来）
- **语义**：切换当前 session 的 agent policy 档位
- **输入**：`session_id: str, policy: "default" | "yolo"`
- **副作用**：发 SSE 事件 `agent_policy_changed`

### 3.2 不暴露的内部接口

以下组件为模块内部实现，外部不直接调用：

- `DecisionMatrix.lookup(agent_policy, tool_class, risk_level) -> verdict` — 由 PolicyDecider 编排
- `DangerousCommandMatcher.maybe_upgrade(command: str) -> RiskLevel` — 仅对 bash 工具类触发
- `SignatureBuilder.build(tool_name, tool_args, skill_context) -> str` — 由 PolicyDecider 编排

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建责任

| 数据 | 创建者 | 说明 |
|------|--------|------|
| `Decision` | policy | policy 是唯一生产者 |
| `capability_signature` | policy (SignatureBuilder) | policy 独占生成，格式 `{scope}:{tool}:{arg_hash8}` |
| `agent_policy` 档位 | session 入口（chat 请求体）或用户切换 | policy 仅通过 SessionPolicyState 读写，不决定初始值 |
| `SkillContext` | skills 模块 | policy 仅消费 `(name, content_hash)` 二元组 |
| `tool_class` / `risk_level` | ToolDefinition（core/tools） | policy 仅读取，不修改、不设默认值 |

### 数据更新与销毁责任

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| SessionPolicyState（agent_policy 档位） | policy | 内存 dict，session 关闭时随进程清理 |
| capability_signature | permission | policy 生成后不再持有；permission 用作 key 查询/写入 |

### 当前模块不负责的数据

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| 永久 allow 记录 | permission | policy 不读 DB，不参与 allow 记录的查询/写入 |
| 用户确认响应 | permission + 前端 | policy 返回 ASK 后不再参与后续流程 |
| DENY 决策 | agent_loop | policy 矩阵仅产出 ALLOW/ASK，DENY 由 agent_loop 在用户拒绝时构造 |
| ask 模式工具过滤 | ChatService | policy 假定每次调用均处于 agent 模式 |

---

## 五、与其他模块 dfd-interface 的交叉引用

| 本文档描述的流向 | 对应模块文档 | 衔接点 |
|------------------|-------------|--------|
| DecideRequest 由 agent_loop 传入 | agent_loop（不属于本文档体系） | agent_loop 在每次工具调用前构造 DecideRequest |
| SkillContext 由 skills 经 agent_loop 透传 | [skills/dfd-interface.md](../skills/dfd-interface.md) | skills.D8 "提供 SkillContext" |
| decision.capability_signature 被 permission 消费 | [permission/dfd-interface.md](../permission/dfd-interface.md) | permission 用 signature 查 AllowStore + 记录许可 |
| tool_class / risk_level 来自 ToolDefinition | core/tools（不属于本文档体系） | ToolRegistry 装载时注入字段 |

---

## 六、自检清单

- [x] 可以清楚说明每条数据从哪里来、到哪里去（agent_loop → Decision → agent_loop，signature → permission）
- [x] 所有接口都服务于明确的数据流（decide 是唯一对外入口，get/set 服务于档位管理）
- [x] 不存在数据责任不清或重复处理的风险（signature 由 policy 独占生成，permission 仅作字符串 key）
- [x] 与 goals-duty.md 的 Non-Duties 一致（不读 DB、不调 permission、不弹卡、不产出 DENY）
- [x] 与 architecture.md 的子组件划分一致（PolicyDecider 编排 SessionPolicyState / DangerousCommandMatcher / DecisionMatrix / SignatureBuilder）
