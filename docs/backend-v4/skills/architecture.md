# skills 模块 architecture.md

本文档描述 `newbee_notebook/core/skills/`（升级）+ `configs/skills/`（存储根）协同构成的 skills 模块内部结构与设计选择。严格服从 [goals-duty.md](goals-duty.md)：双轨共存、显式激活、Anthropic 规范 frontmatter、内容哈希绑定许可、沙箱与通用工具各司其职、级联卸载。

---

## 一、Architecture Overview（总体架构）

skills 模块由七个子组件组成，分两层：

**注册层（运行时常驻）**：
1. **UnifiedSkillRegistry（升级版注册中心）** — 合并"内置 Python provider（note/diagram/video）+ 用户 ConfigSkillProvider"，暴露统一的 slash 命令路由。
2. **ConfigSkillProvider（配置型 skill 适配器）** — 把一个 `configs/skills/<name>/` 目录映射为"可被 UnifiedSkillRegistry 注册的 provider"。它**只读 SKILL.md 的 frontmatter**（仅 name + description）用于注册；SKILL.md 正文、references/、scripts/ 都对它是黑盒，由 mellow 通过通用 Read/Glob/Grep 按需读。不生成 tools 列表（通用工具来自 core/tools）。
3. **ActivationContextBuilder（激活上下文构造器）** — 命中 `/<name>` 时，构造最小 system prompt（仅 description + "use Read tool to open configs/skills/<name>/SKILL.md"），同时组装 `SkillContext(name, content_hash, scripts_dir, work_mount)` 供 agent_loop 传给 policy。

**管理层（管理面板调用）**：
4. **SkillInstaller（三通道安装器 + 安全校验）** — 处理 GitHub URL / 本地路径 / zip 上传；防 zip slip / bomb / symlink / 大文件 / 嵌套 repo；本地路径**仅 copy**；统一落隔离区后等用户确认。
5. **ManifestParser（SKILL.md 解析与 Anthropic 规范校验）** — 解析 frontmatter、校验 name/description、拒绝 `anthropic`/`claude` 保留词、长度限制、唯一性。
6. **ContentHasher（内容哈希计算器）** — 安装完成后递归计算 skill 目录的 tree hash（按路径排序、每文件 SHA-256、合并后再 hash），写入 DB `skills.<name>.content_hash`。
7. **SkillLifecycle（启停与级联卸载）** — 读写 `app_settings.skills.<name>.*`；卸载触发级联清理（物理删目录 + 清 DB 配置 + 调 `permission.clear_skill_permissions` + 清残留 run_dir）。

### 内部依赖方向

```
（注册层，随进程常驻）
UnifiedSkillRegistry
├── [内置 Python provider]（来自 newbee_notebook/skills/）
└── ConfigSkillProvider（由 SkillLifecycle 在启动/安装后注册）
       └── ActivationContextBuilder（命中时构造激活 prompt + SkillContext）
                                                │
                                                ▼
                             agent_loop ← SkillContext(name, content_hash, ...)
                                                │
                                                ▼
                                           policy 生成 signature

（管理层，由 API 路由触发）
SkillInstaller
├── ManifestParser             （校验 SKILL.md frontmatter）
├── zip slip / bomb 防御        （SkillInstaller 内置）
└── [隔离区 → 用户确认 → 移到 configs/skills/<name>/]
       ↓
ContentHasher.calculate(<skill_dir>)  →  DB.skills.<name>.content_hash
       ↓
SkillLifecycle.enable → UnifiedSkillRegistry.register

（卸载路径）
SkillLifecycle.uninstall
├── UnifiedSkillRegistry.unregister
├── rm -rf configs/skills/<name>/
├── app_settings: DELETE skills.<name>.*
├── permission.clear_skill_permissions(name)
└── 清 tmp/skill-runs/ 中残留该 skill 的 run_dir
```

### 激活路径（高层）

1. 用户输入 `/my-skill ...`，ChatService → UnifiedSkillRegistry.match_command 命中
2. ConfigSkillProvider 构造 SkillManifest：tools 空列表；system_prompt_addition 为 ActivationContextBuilder 生成的激活提示
3. ActivationContextBuilder 读 DB `skills.my-skill.content_hash` 构造 `SkillContext`
4. agent_loop 收到 SkillManifest + SkillContext，把激活提示注入、SkillContext 作为决策上下文
5. mellow 看到 prompt 后用 **Read** 工具（不是 Bash）读 `configs/skills/my-skill/SKILL.md`
6. 后续进入 progressive disclosure：Read/Glob/Grep 按需读 references/；scripts/ 的执行走 Bash → policy decide（拿到 signature）→ permission（如需）→ sandbox
7. 执行路径上 skills 模块**不再出现**

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Adapter — ConfigSkillProvider（非 MarkdownSkillProvider）

之前叫"MarkdownSkillProvider"容易误导——它其实不解析 markdown 正文（那是 mellow 用 Read 做的事）。**改名为 ConfigSkillProvider**：它只是把"配置目录"适配为 SkillProvider 协议。tools 返回空（通用工具来自 core/tools），system_prompt 只含激活指令。服务于 goals-duty **G2 + G3**。

### 2. Progressive Disclosure（Anthropic 规范对齐）

SKILL.md 正文不预加载。ActivationContextBuilder 只注入 description 和"use Read tool to open SKILL.md"。SKILL.md 正文、references/、scripts/ 全部由 mellow 主动按需读取。用 **Read** 而不是 Bash：
- 解析 SKILL.md 本质是读文件内容
- 用 Bash 意味着"cat 不存在的文件"会走 shell 报错，且 Bash 经 sandbox，读 SKILL.md 走沙箱反而复杂
- Read 作用域已限定到 `configs/skills/<active>/`，安全等价且语义更清晰

服务于 goals-duty **G3**。

### 3. Strategy — 三通道安装

SkillInstaller 对三种来源走不同实现，出口统一。未来加 Anthropic Skills API 加一个 strategy。服务于 goals-duty **G6**。

### 4. Defense in Depth — 安装校验

codex P1 指出多个安装期攻击面。SkillInstaller 串联多道校验（顺序重要）：
1. 入口过滤：GitHub 仅 codeload（非 git clone，避免 `.git` 历史泄漏）；本地仅 copy，禁 symlink；zip 走内存流处理
2. zip 解压安全：拒绝 `..`、绝对路径、符号链接条目、硬链接条目、重复文件名
3. 大小阈值：单文件 ≤10MB、目录 ≤50MB、解压比 ≤100×
4. 嵌套 `.git` 拒绝
5. ManifestParser 校验 frontmatter
6. name 唯一性校验
7. 隔离区完成 → 前端预览（含 file tree + content_hash）→ 用户确认 → 移入正式目录

服务于 goals-duty **G6**。

### 5. Content-Bound Ownership — ContentHasher

codex P1 指出永久许可若不绑内容会被供应链攻击利用。ContentHasher 是 skills 模块对外承诺"每次内容变更 content_hash 必变"。skills 不缓存哈希，每次从 DB 读最新值——避免 skill 热加载场景下旧哈希滞留。服务于 goals-duty **G7**。

### 6. Cascading Uninstall — SkillLifecycle

卸载不只是删目录。五步级联：UnifiedSkillRegistry unregister → 物理删 → 清 DB config → 调 `permission.clear_skill_permissions` → 清残留 run_dir。codex 指出遗漏任一步都是许可残留/路径残留。集中在 SkillLifecycle 一个入口保证完整。服务于 goals-duty **G6 + D6**。

### 7. Single Source of Truth — 存储位置

`configs/skills/<name>/` 唯一。不做 DB 存内容 + 文件缓存。服务于 goals-duty **G8**。

### 8. 未做：skill 优先级/覆盖式注册

name 冲突在安装阶段直接拒绝。不做覆盖。

### 9. 未做：Plugin Hook 机制

skill 生命周期极简：命中 → 激活 → 执行走通用工具 → 结束。不引入 before-activate/after-exec 等 hook。违反"skill 只是 workflow 说明"定位。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

```
newbee_notebook/core/skills/
├── __init__.py
├── contracts.py                    # 既有文件，新增 SkillSource / SkillManifestMeta / SkillContext 等
├── registry.py                     # 升级为 UnifiedSkillRegistry
├── config_provider.py              # ConfigSkillProvider（适配器，不读正文，只读 frontmatter）
├── activation.py                   # ActivationContextBuilder（构造激活 prompt + SkillContext）
├── install/
│   ├── __init__.py
│   ├── installer.py                # SkillInstaller（门面 + 校验串联）
│   ├── github_source.py            # GitHub URL 通道（codeload，非 git clone）
│   ├── local_source.py             # 本地路径通道（仅 copy，禁 symlink）
│   ├── zip_source.py               # zip 上传通道
│   └── safety.py                   # zip slip / bomb / 大小 / 嵌套 .git 校验集合
├── manifest_parser.py              # ManifestParser（YAML frontmatter + Anthropic 规范校验）
├── content_hasher.py               # ContentHasher（tree hash）
├── lifecycle.py                    # SkillLifecycle（enable/disable/uninstall 级联）
└── errors.py                       # SkillInstallError / SkillNameConflict / InvalidManifestError / SkillNotFoundError

configs/skills/
├── <skill-name-1>/
│   ├── SKILL.md
│   ├── references/                 # 可选，用户可选任意组织
│   └── scripts/                    # 可选
└── <skill-name-2>/
    └── SKILL.md

newbee_notebook/api/routers/
└── skills.py                       # GET /api/skills, POST /api/skills/install, DELETE /api/skills/<name>, GET /api/skills/<name>/preview
```

### 稳定接口 vs 内部实现

- **对外稳定**：
  - `UnifiedSkillRegistry.match_command`
  - `SkillLifecycle.enable / disable / uninstall`
  - `SkillInstaller.install_from_github / install_from_local / install_from_zip`
  - `ManifestParser.parse`
  - `ContentHasher.calculate`
  - `/api/skills`、`/api/skills/install`、`/api/skills/<name>`、`/api/skills/<name>/preview`
- **内部可演化**：安装策略实现、ActivationContextBuilder 文案、ContentHasher 哈希算法细节（但输出长度/稳定性不变）

### configs/skills/ 的布局选择

- 直接以 skill name 为目录名（与 `/command` 一致）
- 无额外元文件（enabled.json 等都不用）——"本地化状态"都在 DB `skills.*` 里
- git 友好

### 不包含的子组件

- **通用工具（Read/Glob/Grep/Bash）**：在 `core/tools/`（见 goals-duty N1）
- **Sandbox 编排**：在 `core/sandbox/`（见 goals-duty N2）
- **policy/permission 决策**：在各自模块
- **capability_signature 生成**：在 policy 模块（见 goals-duty N4）
- **run_dir 创建**：由 Bash 工具在调 sandbox 前创建（见 goals-duty N12）
- **内置 skill 实现**（`newbee_notebook/skills/note` 等）：保持原状

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 放弃方案：把内置 skill 迁成 markdown

放弃理由详见 goals-duty G2 注释。**代价**：双形态维护，但边界清晰。

### 放弃方案：在 system prompt 预加载所有 skill description

放弃理由：显式 `/` 激活。前端 SlashCommandHint 用动态 API 提示用户。模型不知道"有哪些 skill 存在"直到用户输入 `/`。

### 放弃方案：SKILL.md 私有扩展字段

严守 Anthropic 规范（name + description）。其它运行策略走 DB `skills.<name>.sandbox_policy`。

### 放弃方案：本地路径 symlink 安装

codex P1 明确拒绝。**仅 copy，lstat 校验后复制**。代价：skill 开发者迭代需重装；但安全成本必须付。

### 放弃方案：永久许可不绑内容

codex P1 拒绝。ContentHasher + permission scope 编码 `@<hash>` 构成天然失效机制。代价：用户更新 skill 后重新确认；正确代价。

### 放弃方案：让 ConfigSkillProvider 直接读 SKILL.md 正文放 system prompt

违反渐进披露。代价：mellow 多一次 Read 调用；但符合 Anthropic 规范且保护 context。

### 放弃方案：skill 脚本直调业务 API / DB

sandbox 网络隔离 + skills 契约都禁止。skill 要做业务副作用必须经 mellow。代价：writer skill 需要多一跳；但维持信任边界。

### 放弃方案：命名冲突自动加前缀

直接拒绝安装，让用户重命名。最简单、可预测。

### 可演进性

- 未来远程 Skills API：`install/` 加通道
- 未来 skill 依赖（A 依赖 B）：ManifestParser 解析可选字段；此时可能需要向 Anthropic 规范提议或做可选扩展
- 未来 skill 版本：ManifestParser + SkillLifecycle 扩展 version 字段；ContentHasher + permission scope 的内容绑定仍然独立生效，两者互补
- 未来 skill 签名：ContentHasher 输出可作为签名输入，做 GPG/ed25519 验证
