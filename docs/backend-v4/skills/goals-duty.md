# skills 模块 goals-duty.md

本文档定义 `newbee_notebook/core/skills/`（升级）与 `configs/skills/`（新增）协同构成的 skills 模块设计目标与职责边界。

---

## 一、模块定位

**一句话说明**：skills 模块为 newbee 引入"用户可安装的 Anthropic 规范 skill"——SKILL.md 描述工作流、`scripts/` 提供脚本，由主 agent（mellow）通过 `/skill-name` 显式激活，借助通用工具（Read/Glob/Grep/Bash）按需读取并在 docker 沙箱中执行，与既有的内置 Python skill（note/diagram/video）双轨共存。模块自身**不实现沙箱、不实现通用工具、不做权限决策、不生成 capability signature**——它只负责 skill 的**发现、安装、注册、激活、内容哈希计算、卸载级联清理**。

**如果没有这个模块**：
- newbee 的能力扩展只能靠后端发版（添加新 Python provider）
- 无法消费 Anthropic 生态已有 skill 资产
- 用户无法把"个人工作流"封装成可复用单元
- skills 这一控制面板入口（[control-panel.tsx:43](../../../frontend/src/components/layout/control-panel.tsx#L43) 当前 coming-soon）永远空置

---

## 二、Design Goals（设计目标）

### G1：严格遵循 Anthropic 规范

SKILL.md frontmatter 仅 `name` + `description` 两字段：
- `name` ≤64 字符，仅小写字母/数字/连字符，禁用 `anthropic`/`claude` 保留词
- `description` ≤1024 字符
- 两字段都禁含 XML 标签

装出去的 skill 无需修改即可在 claude.ai / Claude Code 使用。**但 script 级可移植性有限**：任何假设 `/skill`、`/work`、newbee 特定工具（Read/Bash）或 sandbox 策略的脚本，迁到别的 skill host 需适配——本模块在预览面板显式声明此限制。

### G2：双轨共存

内置 skill（note/diagram/video）保持现有 Python provider 形态不动，v1 维持既有 confirmation_required 路径；用户安装 skill 走新的 config-based provider 通道。两者在同一 SkillRegistry 中合并，但安装/卸载/启停通道完全分离。v2 会把内置 skill 的 confirmation_required 迁入 permission（见 permission 模块）。

### G3：显式激活，不污染默认对话

skill 的 name 与 description **不会**总是出现在系统 prompt 中。只有当用户输入 `/skill-name` 命中 SkillRegistry 时，才注入"激活提示"——一句指令让 mellow **用 Read 工具** 读取 `configs/skills/<name>/SKILL.md`。SKILL.md 正文、references/、scripts/ 全部走渐进披露：Read/Glob/Grep 按需读 host 只读文件；scripts 执行通过 Bash → sandbox。

### G4：沙箱原生（委托给 sandbox 模块）

所有 skill 自带的 `scripts/` 必须在受限环境中执行。skills 模块本身**不实现沙箱**——容器编排、镜像管理、挂载策略、网络隔离全部交给独立的 [sandbox 模块](../sandbox/goals-duty.md)。skills 只：声明"scripts 必须经 sandbox 跑"、在激活提示中告知 mellow "script 用 Bash 运行"。不出现任何 docker SDK 调用。

### G5：与 mellow 双向数据通道

skill 脚本不能直接访问数据库，也不能调用 newbee 内部 API（sandbox 网络隔离保证 compose 内部不可达）。skill ↔ mellow 的数据交换通道：
- **小数据**：stdin/stdout 的 JSON（Bash 工具透传）
- **大文件**：host `tmp/skill-runs/<run_id>/`（由 Bash 工具创建）↔ sandbox `/work/`（sandbox 挂载）

持久化（写笔记、建图表、入 video summary）必须由 mellow 在 skill 工作流指引下显式调业务 service 工具完成。

### G6：安装可逆 + 三通道导入 + 严格校验

支持 GitHub URL（zip 下载）、本地路径（**仅 copy，禁 symlink**）、zip 上传三种。装前一律走"预览-审查-确认"三步，让用户审视 SKILL.md 与脚本清单。安装时强制校验：
- zip slip / 绝对路径 / `..` / symlink / hardlink
- zip bomb（解压比上限、总大小上限）
- 大文件上限（单文件 ≤10MB，目录总大小 ≤50MB）
- 嵌套 `.git` 目录拒绝（防止拖入整个仓库）

卸载是**级联**的：删除目录 + 清 DB `skills.<name>.*` 配置 + **调 permission 的 `clear_skill_permissions(name)`** 清所有相关永久许可 + 清当前 session 内存。

### G7：内容哈希作为许可边界

每次 skill 内容变更（安装、重装、zip 覆盖）时计算并存储**内容哈希**（skill 目录的 tree hash，参考 git 的 tree SHA）到 DB `skills.<name>.content_hash`。该哈希随 SkillContext 传给 policy → permission，使永久允许记录绑定到特定内容版本。**skill 内容变更 → hash 变 → 旧永久许可自动失效**（permission 查 allow 时 scope 不匹配即未命中）。

### G8：单一存储位置

所有用户 skill 物理存储在 `configs/skills/<name>/`（host 文件系统），同时挂载到 backend 容器（可读）与 sandbox 子容器（`:ro`）。不放数据库，不放 docker 命名 volume——便于人眼审查、git 备份、热更新。

---

## 三、Duties（职责）

### D1：SKILL.md 解析与校验

读取 frontmatter（仅 YAML），校验：
- 只允许 `name` + `description` 两字段（多余字段报错但非致命，提示用户移除）
- `name` 正则 `^[a-z0-9][a-z0-9-]{0,63}$`，禁用 `anthropic` / `claude`
- `description` 长度 1~1024
- name 唯一性（与内置 skill、已装 skill 不冲突；冲突直接拒绝安装）

### D2：注册与命令路由

升级 SkillRegistry 为 `UnifiedSkillRegistry`，合并"内置 Python provider + ConfigSkillProvider（用户 skill）"。统一支持 `/<skill-name>` 命中。命中后构造**最小** system prompt：只含 name + description + "use Read tool to open configs/skills/<name>/SKILL.md" 激活指令，**不嵌入 SKILL.md 正文**。

### D3：内容哈希计算

安装完成后，递归遍历 `configs/skills/<name>/`（按路径排序，读每个文件内容 SHA-256），合并成整体 tree hash。写入 DB `skills.<name>.content_hash`。提供 `get_content_hash(name) -> str` 接口供 SkillContext 注入。

### D4：三通道安装

- **GitHub URL**：codeload API 下载 zip（非 git clone；避免 `.git` 历史泄漏），落到隔离区
- **本地路径**：**仅 copy，禁 symlink**；copy 前用 `lstat` 校验，拒绝路径中包含 symlink
- **zip 上传**：multipart 收 zip 落到隔离区

全部落到隔离区后走 D5 预览 + D1 校验 + zip bomb / slip 防御（见 G6），用户确认后才移入 `configs/skills/<name>/`。

### D5：安装预览

安装请求落隔离区后，**先不激活**。返回结构化 manifest 给前端：
- frontmatter 解析结果
- 文件树 + 每文件大小 + SHA-256
- 脚本清单（`scripts/*` 的路径）
- 计算出的 content_hash
- 预估 scopes（即将占用的 slash 命令、 /skills API 标识）

用户在前端预览面板审阅后选择"安装"或"取消"。

### D6：启停与卸载（级联）

- **启停**：写 DB `skills.<name>.enabled`，UnifiedSkillRegistry 据此控制 `/<name>` 是否可命中
- **卸载**：
  1. 从 UnifiedSkillRegistry 移除
  2. `rm -rf configs/skills/<name>/`
  3. 清 DB 所有 `skills.<name>.*` 配置
  4. 调 `permission.clear_skill_permissions(name)` 清永久许可与 session 内存
  5. 清 `tmp/skill-runs/` 中属于该 skill 的残留 run_dir

### D7：列表查询 API

暴露：
- `GET /api/skills`：列出所有 skill（含 enabled / source / content_hash / description）
- `POST /api/skills/install`：三通道入口
- `DELETE /api/skills/<name>`：级联卸载
- `GET /api/skills/<name>/preview`（隔离区的 manifest）

供前端 slash 提示动态渲染（替换硬编码的 [slash-command-hint.tsx](../../../frontend/src/components/chat/slash-command-hint.tsx)），并驱动控制面板 Skills 标签页。

### D8：提供 SkillContext

当命令命中时，构造 `SkillContext(name, content_hash, scripts_dir=/skill/scripts, work_dir_mount=/work)` 给 agent_loop；agent_loop 转发给 policy 用于生成 capability_signature。**本模块不生成 signature 本身**（那是 policy 的事）。

---

## 四、Non-Duties（非职责）

### N1：不实现通用工具

`Read / Glob / Grep / Bash` 这四个工具属于 [`newbee_notebook/core/tools/`](../../../newbee_notebook/core/tools)，不是 skills 模块的一部分。skills 模块只是它们最主要的消费者。

### N2：不实现沙箱

容器编排、镜像选择、挂载、网络隔离、超时回收全部由 [sandbox 模块](../sandbox/goals-duty.md) 负责。skills 模块完全不出现 docker SDK 调用。

### N3：不做权限决策

是否需要弹卡、要不要拒绝由 policy 模块决定。skills 仅提供 SkillContext。

### N4：不生成 capability signature

signature 由 policy 构造（见 policy G5 / D5）。skills 不拼 signature 字符串。

### N5：不做用户确认 UI

预览/确认/卸载提示都由前端控制面板渲染。skills 后端只暴露数据。

### N6：不读写业务数据库

skill 脚本无法访问 postgres（sandbox 网络隔离）。持久化必须经 mellow + 现有 service tool 完成。

### N7：不替代或迁移内置 skill

note/diagram/video 仍是 Python provider，强类型 + 强校验。本模块不为它们提供 markdown 等价物。

### N8：不在 system prompt 注入 SKILL.md 全文

只在命令命中时注入 description + 读取指令；正文由 mellow 用 Read 主动加载。

### N9：不持久化 skill 运行历史

scripts 执行的 stdout/stderr 仅作为 ToolCallResult 流回 mellow。运行级 log 由 sandbox 落盘到 `tmp/skill-runs/`，不入业务 DB。

### N10：不解析 references/ 与 scripts/ 内容

frontmatter 之外的所有文件，本模块不读、不索引、不预处理（但 D3 计算 SHA-256 用于 content_hash 不算"解析"）。它们对 mellow 是黑盒，靠 Bash/Read/Glob 自主探索。

### N11：不支持 SKILL.md 之外的扩展字段

不引入 `runtime` / `network` / `timeout` / `allowed_tools` 等私有字段——这些运行策略走 DB `skills.<name>.sandbox_policy` JSON，与 SKILL.md 解耦，保持可移植。

### N12：不创建 run_dir

skill 脚本每次执行的 `tmp/skill-runs/<run_id>/` 由 Bash 工具在调 sandbox 前创建。skills 不负责。

### N13：不持有内容哈希缓存

`content_hash` 由 D3 计算并写 DB，skills 模块不持有内存副本；每次需要时从 DB 读。这样 skill 内容变更后（比如未来做热加载）读到的永远是最新值。

---

## 五、设计约束与假设

### 约束

1. **存储路径固定**：`configs/skills/<name>/`，不支持别名
2. **依赖 policy + permission + sandbox + core/tools**：skill 任何外部副作用都必须经这四个模块，不留绕过路径
3. **受 ToolRegistry 与 sandbox 影响**：Bash 等通用工具与 sandbox 模块的实现进度直接决定本模块上线时机
4. **zip/源码大小上限**：单文件 10MB、目录 50MB、解压比 ≤100×
5. **本地 copy-only**：symlink 一律拒绝，降低 TOCTOU 攻击面
6. **content_hash 绑许可**：skill 任何内容变更导致许可重新询问，用户须理解

### 假设

1. policy 模块先于 skills 完成 decide 纯函数 + signature 生成 + tool_class/risk_level 字段
2. permission 模块先于 skills 完成永久白名单（含 content_hash scope）+ 提供 `clear_skill_permissions`
3. sandbox 模块先于 skills 完成网络隔离 + 硬化 flags + 挂载校验
4. core/tools 新增 Read/Glob/Grep/Bash：
   - Read/Glob/Grep 在 host 作用域限定 `configs/skills/<active>/` + `tmp/skill-runs/<run_id>/`
   - Bash 全部走 sandbox
5. 前端改造 [slash-command-hint.tsx](../../../frontend/src/components/chat/slash-command-hint.tsx) 使用动态 API
6. 控制面板新增 "Skills" 标签页接管现有 coming-soon 占位

---

## 六、与其他模块的关系

| 模块 | 关系 | 说明 |
|------|------|------|
| policy | 被调用方 | skill 命中时提供 SkillContext（含 content_hash）给 agent_loop → policy；policy 据此拼 signature |
| permission | 级联清理目标 | skill 卸载时调 `clear_skill_permissions`；其余时候不直接交互 |
| sandbox | 间接 | skill 脚本执行经 Bash 工具 → sandbox；本模块不直接调 sandbox |
| core/tools（Read/Glob/Grep/Bash） | 被依赖 | mellow 用这四个工具消费 skill |
| UnifiedSkillRegistry | 拥有 | 在本模块内升级，统一注册"内置 Python skill + 用户 config skill" |
| 内置 skill（note/diagram/video） | 共存 | 不修改、不替代、不重写 |
| ChatService / agent_loop | 被依赖 | 命令命中后由本模块提供 SkillContext 与激活提示 |
| AppSettingsService | 依赖 | 读写 `skills.*` 配置项（含 content_hash） |
| 控制面板（前端） | 被依赖 | 安装预览、卸载、启停 UI；展示 content_hash 让用户感知变更 |

---

## 七、文档自检

- [x] 可以用一句话说明模块存在的意义（加载/运行/管理用户安装的 Anthropic 规范 skill）
- [x] 可以清楚回答"不该做什么"（不实现通用工具、不实现沙箱、不做决策、不生成签名、不创建 run_dir、不读业务 DB）
- [x] 与 policy / permission / sandbox / core/tools / 内置 skill 边界清晰
- [x] 所有职责可被验证（manifest 解析单测、zip slip / bomb 校验集成测、content_hash 稳定性单测、级联卸载集成测）
- [x] 严格遵循 Anthropic 规范（仅 name + description）
- [x] 激活只注入指令，SKILL.md 正文走 Read 渐进披露
- [x] 内容哈希绑定许可，防止重装后的许可继承攻击
- [x] 本地 copy-only 防 symlink 攻击
- [x] 级联卸载覆盖 DB / permission / session memory / tmp run_dir
