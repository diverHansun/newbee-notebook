# policy 模块 goals-duty.md

本文档定义 `newbee_notebook/core/policy/` 模块的设计目标与职责边界。

---

## 一、模块定位

**一句话说明**：policy 模块是"**agent 模式下**工具调用的**纯决策中枢**"——给定一次工具调用（含 skill 触发的 Bash 调用），policy 仅根据**用户选择的 agent policy 档位 + 工具声明的 risk_level + 预生成的 capability_signature** 输出三态结果 `ALLOW / DENY / ASK`。decide 函数**纯净**：不读 DB、不调 permission、不弹卡。由 agent_loop 据 policy 输出决定：放行、中止、或把控制权交给 permission 去询问用户。

**只服务 agent 模式**：ask 模式语义已是"面向文档的纯只读问答"，由 ChatService 在工具注册阶段直接过滤可用工具集，不进入 policy 决策路径。policy 假定每次被调用都处于 agent 模式。

**如果没有这个模块**：
- 工具是否需要确认完全由 ToolDefinition 的 `confirmation_required` 静态决定，无法随用户偏好或 agent policy 档位调整
- 引入 skill 后每次脚本调用都要弹卡，用户体验崩溃
- 工具风险等级散落在各 provider 内部，无统一裁决入口
- capability_signature 的生成逻辑无处归属，permission 无法按 skill 维度记忆"始终允许"
- "完全允许"档位（yolo）无法在不破坏代码结构的前提下表达

---

## 二、Design Goals（设计目标）

### G1：决策纯净、可确定性回归

`decide()` 是纯函数：输入 `(agent_policy, tool_class, risk_level, capability_signature, skill_context)`，输出 `Decision` 三态。**不读 DB、不调 permission、不做任何 IO**。相同输入永远得到相同输出，便于覆盖矩阵单测与回放调试。

### G2：两档 agent policy 可选

为 agent 模式提供两档用户可切的 policy 档位：

- **default（默认权限）**：Read/Glob/Grep 自动放行；Edit/Write 类工具与 Bash 命中危险命令模式需用户批准；其余 Bash 与 skill 脚本自动放行（前提是经 sandbox 执行）
- **yolo（完全允许）**：所有工具调用自动放行——前提是 sandbox 强制 host 只读且网络隔离

档位由用户在控制面板/会话级别选择，policy 据档位查表决策。

### G3：sandbox 是前提（前置假设）

两档 policy 共同的安全前提：**任何写入只能落在 sandbox 内**，host 文件系统在沙箱视角内永远是 read-only；**sandbox 不加入 compose 默认网络**，skill 脚本不能直连 postgres / backend 等 sibling 服务。policy 不重复校验这些约束——信任 sandbox 在挂载与网络层硬性拦截。

### G4：risk_level 与 tool_class 分离

policy 决策矩阵的两个维度：

- **tool_class**：工具类别（`read / write / edit / bash / mcp / custom`），与"工具做什么"绑定，来自 ToolRegistry 的静态分类
- **risk_level**：工具自声明风险（`safe / moderate / dangerous`），来自 ToolDefinition 的 `risk_level` 字段，或 Bash 调用被危险命令匹配器升级

两者独立，避免语义混淆。矩阵 cell 的 key 是 `(agent_policy, tool_class, risk_level)`。

### G5：capability_signature 归属

policy **独自负责**构造 capability_signature。不接受上游传入的"半成品签名"，也不委托 skills / sandbox 生成。签名格式固定为：

```
{scope}:{tool}:{arg_hash8}
```

其中 `scope` 是 `"global"` 或 `"skill:<name>@<content_hash>"`（skill 上下文由 SkillRegistry 提供 name + 当前内容哈希）；`tool` 是工具名；`arg_hash8` 是工具参数结构化后 SHA-256 前 8 位。同一 signature 代表"同一 skill 内容 + 同一工具 + 同一参数形态"的调用。

### G6：与 permission 单向调用

policy 是 permission 的上游，但**不主动调 permission**：policy 的 `decide()` 仅返回 `ASK` ——当且仅当 verdict 为 ASK 时才触发 agent_loop 调 permission。policy 不弹任何卡、不知道 UI 的存在、不等待用户响应。

### G7：上下文感知（仅只读）

policy 从入参中读取当前活跃 skill 标识（由 SkillRegistry 在命令命中后经 agent_loop 传入），用于构造带 skill 维度的 capability_signature。policy **不反向调用 SkillRegistry**。

---

## 三、Duties（职责）

### D1：暴露决策接口

提供 `decide(request: DecideRequest) -> Decision`。`DecideRequest` 字段：
- `agent_policy: "default" | "yolo"`
- `tool_class: ToolClass`
- `risk_level: RiskLevel`
- `tool_name: str`
- `tool_args: dict`
- `skill_context: SkillContext | None`（含 name + content_hash；None 表示全局调用）

`Decision` 字段：
- `verdict: "ALLOW" | "ASK"`（policy 仅产出 ALLOW 与 ASK；DENY 由 agent_loop 在用户拒绝时构造，不在 policy 输出类型中）
- `capability_signature: str`（由 policy 生成，供 permission 使用）
- `reason: str`（人可读，供日志与确认卡展示）

### D2：维护会话 agent policy 档位

为每个 session_id 维护当前选择的 agent policy 档位（`default` / `yolo`）。初始值由 chat 请求体携带（默认 `default`），暴露 `get_policy / set_policy`。

### D3：应用决策矩阵

按 `(agent_policy, tool_class, risk_level)` 在内存矩阵中查表：

- **default 档**：
  - `(default, read, *)` → ALLOW
  - `(default, edit, *)` → ASK
  - `(default, write, *)` → ASK
  - `(default, bash, safe|moderate)` → ALLOW
  - `(default, bash, dangerous)` → ASK
  - `(default, mcp, *)` → 透传 MCP 工具自声明
  - `(default, custom, *)` → ASK（未显式定义的 tool_class 默认需确认）
- **yolo 档**：
  - `(yolo, *, *)` → ALLOW

DENY 不在矩阵中产生——它仅由 agent_loop 在 permission 返回"用户拒绝"时产出，policy 自身不产出 DENY（防止设计模糊）。

### D4：识别危险 Bash 命令

policy 内置一份"危险命令模式表"（如 `rm -rf` / `curl ... | sh` / `chmod` / `dd of=` / `mkfs` 等）。Bash 工具调用进入 decide 时，policy 用模式表对 command 做字面量匹配，匹配命中则把入参的 `risk_level` 升级为 `dangerous` 再查矩阵。**此机制仅作为 UX 层的风险标签**，不作为安全栅栏（安全栅栏是 sandbox 提供的隔离）。

### D5：构造 capability_signature

按 G5 规则构造签名。`arg_hash8` 对参数做稳定规范化：
- dict 按 key 排序
- 对 Bash 的 `command` 字段特殊处理：按空白切成 argv 列表后取前 3 个 token（让"同一命令前缀"的多次调用命中同一签名）
- 其余字段序列化为 canonical JSON 后 SHA-256

### D6：发布档位变化事件

agent policy 档位切换时发 SSE 事件给前端，使工具栏指示器（"Default" vs "YOLO"）实时同步。

---

## 四、Non-Duties（非职责）

### N1：不弹卡、不渲染 UI

`ASK` 决策只是返回值，弹卡由 permission + 前端完成。

### N2：不执行工具

policy 不调用 `tool.execute()`——执行由 agent_loop 在收到 `ALLOW` 后接管。

### N3：不定义 risk_level 默认值

每个 ToolDefinition 自声明 `risk_level`。policy 仅读取，不设兜底默认（ToolRegistry 装载时兜底为 `safe`）。

### N4：不读 DB、不查永久允许

policy **完全不访问** `app_settings` / `permissions.*`。永久允许的查询与写入**全部由 permission 负责**。policy 即便知道 capability_signature 也不查它有没有被允许过——那是 permission 的事。

### N5：不调用 permission

policy 不直接调 `permission.request()`。返回 `ASK` 后由 agent_loop 决定下一步走向。

### N6：不感知 skill 内部细节

不读 SKILL.md、不解析 scripts/、不验证 frontmatter。仅消费 SkillRegistry 通过 agent_loop 传入的 `(name, content_hash)` 二元组。

### N7：不管 ask 模式

ask 模式由 ChatService 在工具注册阶段直接过滤掉所有写/执行类工具，不调用 policy。policy 假定每次被调用都处于 agent 模式，若误被 ask 模式调用应抛错（防御性断言）。

### N8：不跨会话保持档位

每个新会话从默认档位（`default`）开始；切换为 yolo 仅当前会话有效，不持久化。

### N9：不实施 host 写拦截与网络隔离

"host 文件系统不可写"与"compose 内部服务不可达"由 sandbox 在挂载层与网络层硬性保证。policy 不重复校验——它信任 sandbox 是 sandbox 内执行的唯一通道。

### N10：不生成 DENY 决策

`DENY` 只由 agent_loop 在收到 permission 的"用户拒绝"响应后产生。policy 的矩阵只有 `ALLOW` 与 `ASK` 两种 cell，简化语义。

### N11：不监听快捷键 / 命令

档位切换接口被 chat-input UI、Commands（未来扩展）调用，policy 不直接挂键盘事件。

---

## 五、设计约束与假设

### 约束

1. **仅 agent 模式**：ask 模式由上游过滤，policy 不必出现在 ask 模式调用栈中
2. **decide 纯函数**：无 IO、无锁、无外部状态；可在测试中随意并发调用
3. **risk_level 是 ToolDefinition 字段**：本设计需在 [contracts.py](../../../newbee_notebook/core/tools/contracts.py) 加字段，是必要的破坏性变更
4. **tool_class 是 ToolDefinition 字段**：同上新增 `tool_class: ToolClass` 字段
5. **content_hash 由 SkillRegistry 提供**：policy 不计算哈希，只消费
6. **sandbox 是写/网隔离的唯一保证**：policy 输出仅决定"放行/询问"语义，隔离由 sandbox 强制

### 假设

1. ToolDefinition 会被改造增加 `risk_level` 与 `tool_class` 两个字段
2. SkillRegistry 在命令命中后会把 `(skill_name, content_hash)` 通过 SkillContext 传给 agent_loop → policy
3. agent_loop 在收到 `ASK` 后负责调 permission
4. agent_loop 在收到用户拒绝后产出 `DENY` 给调用栈，policy 不参与
5. ChatService 在 ask 模式下只注册 ToolRegistry 中标记为 `safe + read` 的只读工具，policy 不会被调用
6. sandbox 模块负责挂载 `:ro` + 网络隔离，policy 不验证

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| permission | 单向被调用 | policy 返回 ASK 后由 agent_loop 调 permission；policy 不直接调、不订阅 permission 事件 |
| sandbox | 前置依赖（不直接交互） | policy 信任 sandbox 保证写隔离与网络隔离 |
| ChatService（ask 模式过滤） | 平级 | ask 模式由 ChatService 直接限制工具集，policy 不参与 |
| ToolRegistry / ToolDefinition | 被依赖 | 读取 `tool_class` 与 `risk_level` |
| SkillRegistry | 被依赖 | 通过 agent_loop 读取当前活跃 skill 的 `(name, content_hash)` |
| agent_loop | 调用方 | 每次工具调用前 `decide()`；收到 `ASK` 后调 permission；收到用户拒绝后产出 `DENY` |
| chat-input UI | 间接 | 通过 agent policy 档位切换 API 与本模块交互 |
| DB / AppSettingsService | 不接触 | policy 完全不读 DB |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在意义（**agent 模式下**的纯决策中枢）
- [x] 可以清楚回答"不该做什么"（不弹卡、不执行、不读 DB、不调 permission、不产出 DENY、不管 ask 模式）
- [x] 与 permission（DB + 弹卡）、SkillRegistry（skill 上下文）、ToolRegistry（工具分类）、sandbox（隔离）边界清晰
- [x] 所有职责可被验证（决策矩阵单测、签名算法单测、档位切换集成测）
- [x] decide 纯函数便于覆盖测试
- [x] capability_signature 格式稳定、规范化可复现
