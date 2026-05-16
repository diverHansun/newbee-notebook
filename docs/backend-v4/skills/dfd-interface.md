# skills 模块 dfd-interface.md

本文档描述 `newbee_notebook/core/skills/`（升级）与 `configs/skills/`（存储根）协同构成的 skills 模块数据流与对外接口。设计严格基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

---

## 一、Context & Scope（上下文与范围）

skills 模块处于 newbee 能力扩展系统的**入口与生命周期管理层**。它负责两件事：**注册层**——运行时常驻，接收 `/skill-name` 命令并构造激活上下文；**管理层**——按需触发，处理 skill 的安装、预览、启停、级联卸载。

### 与外部模块的交互关系

| 方向 | 模块 | 角色 |
|------|------|------|
| 输入来源 | 前端 chat-input（SlashCommandHint） | 用户输入 `/skill-name`，ChatService 路由到 UnifiedSkillRegistry |
| 输入来源 | 前端控制面板 | 安装/卸载/启停操作 |
| 输入来源 | GitHub API / 本地文件系统 / multipart upload | 安装的三种来源 |
| 输出去向 | ChatService / agent_loop | 输出 SkillManifest + SkillContext + 激活 prompt |
| 输出去向 | policy（经 agent_loop） | SkillContext 供 policy 构造 capability_signature |
| 输出去向 | permission（级联清理） | 卸载时调 `clear_skill_permissions` |
| 输出去向 | 前端 | `/api/skills` 等 REST 响应 |
| 依赖 | AppSettingsService（DB） | 读写 `skills.<name>.*` 配置（含 content_hash） |
| 依赖 | 文件系统 `configs/skills/` | 物理存储 |
| 不交互 | sandbox | skills 不直接调 sandbox（执行走 Bash 工具中转） |
| 不交互 | core/tools（直接） | skills 不实现通用工具，仅供 mellow 通过通用工具消费 |

### 本文档范围

描述 skills 模块的激活路径、安装路径、卸载路径三组数据流。不描述 mellow 如何使用 Read/Glob/Grep/Bash 消费 skill 内容（那是工具链的职责），不描述 sandbox 如何隔离执行（那是 sandbox 的职责）。

---

## 二、Data Flow Description（数据流描述）

### 路径一：Skill 激活（运行时高频路径）

```
用户输入 "/my-skill ..."（chat-input 前端）
  │
  │  ChatService 接收消息
  ▼
UnifiedSkillRegistry.match_command("my-skill")
  │
  ├─ 查内置 Python provider（note/diagram/video）→ 未命中
  ├─ 查 ConfigSkillProvider 集合 → 命中 "my-skill"
  │
  ├─ ConfigSkillProvider.get_manifest()
  │     ├─ 读 SKILL.md frontmatter（仅 name + description）
  │     │   不读正文、不读 references/、不读 scripts/
  │     └─ tools 列表为空（通用工具来自 core/tools）
  │
  ├─ ActivationContextBuilder.build("my-skill")
  │     ├─ 从 DB 读 skills.my-skill.content_hash
  │     ├─ 构造 SkillContext:
  │     │     name="my-skill"
  │     │     content_hash="a1b2c3d4..."
  │     │     scripts_dir="/skill/scripts"
  │     │     work_dir_mount="/work"
  │     └─ 构造激活 prompt（仅 description + "use Read tool to open
  │         configs/skills/my-skill/SKILL.md"——不嵌入全文）
  │
  └─ 输出 SkillManifest(system_prompt_addition=激活_prompt,
                        tools=[])
         + SkillContext(name, content_hash, ...)
  │
  ▼
ChatService / agent_loop
  ├─ 激活 prompt 注入 system prompt
  ├─ SkillContext 传给 agent_loop
  └─ agent_loop 在后续工具调用前将 SkillContext 传给 policy
       → policy 构造 signature（见 policy/dfd-interface.md）

后续（mellow 自主探索）：
  mellow 看到激活 prompt → 用 Read 工具读 configs/skills/my-skill/SKILL.md
  → 按 SKILL.md 指引用 Read/Glob/Grep 读 references/
  → 需要执行 scripts/ 时用 Bash 工具
    → Bash 走 policy.decide() → permission.request() → sandbox.exec()
  → 执行路径上 skills 模块不再出现
```

### 路径二：Skill 安装（管理路径）

```
前端控制面板 "安装 Skill"
  │
  ├─ GitHub URL 通道
  │     SkillInstaller.install_from_github(url)
  │       ├─ codeload API 下载 zip（非 git clone，避免 .git 历史泄漏）
  │       └─ 落到隔离区 tmp/skill-installs/<uuid>/
  │
  ├─ 本地路径通道
  │     SkillInstaller.install_from_local(path)
  │       ├─ lstat 校验路径中无 symlink
  │       ├─ 仅 copy，禁 symlink
  │       └─ 落到隔离区
  │
  └─ zip 上传通道
        SkillInstaller.install_from_zip(file)
          ├─ multipart 收 zip
          └─ 落到隔离区

（三条通道汇聚到隔离区后统一流程）
  │
  ▼
SkillInstaller._install_from_staging(staging_path)
  │
  ├─(1)─ 安全校验（顺序重要）：
  │       ├─ zip slip 防御：拒绝 .. / 绝对路径 / symlink entry / hardlink entry
  │       ├─ zip bomb 防御：解压比 ≤ 100x、总大小 ≤ 50MB
  │       ├─ 单文件 ≤ 10MB
  │       ├─ 拒绝嵌套 .git 目录
  │       └─ 文件树遍历，每文件 SHA-256 记录
  │
  ├─(2)─ ManifestParser.parse(staging_path / "SKILL.md")
  │       解析 YAML frontmatter：
  │         - 仅允许 name + description 两字段
  │         - name 正则 ^[a-z0-9][a-z0-9-]{0,63}$
  │         - 禁 anthropic / claude 保留词
  │         - description 1~1024 字符
  │         - name 唯一性校验（与内置 skill + 已装 skill 不冲突）
  │       失败 → InvalidManifestError
  │
  ├─(3)─ 生成预览 manifest → 推给前端预览面板：
  │       ├─ frontmatter 解析结果
  │       ├─ 文件树 + 每文件大小 + SHA-256
  │       ├─ scripts 清单（scripts/* 的路径）
  │       ├─ content_hash 预估值
  │       └─ scope 信息（slash 命令标识）
  │
  ├─(4)─ 用户确认
  │       ├─ 确认 → 继续 (5)
  │       └─ 取消 → 清理隔离区，返回
  │
  ├─(5)─ 移入正式目录：mv staging_path → configs/skills/<name>/
  │
  ├─(6)─ ContentHasher.calculate("configs/skills/<name>/")
  │       递归遍历目录（按路径排序）
  │       每文件 SHA-256 → 合并 → 整体 tree hash
  │       写入 DB: skills.<name>.content_hash = "a1b2c3d4..."
  │
  ├─(7)─ SkillLifecycle.enable("my-skill")
  │       DB: skills.my-skill.enabled = true
  │       UnifiedSkillRegistry.register(ConfigSkillProvider("my-skill"))
  │
  └─(8)─ 返回成功响应给前端，控制面板 Skills 列表更新
```

### 路径三：Skill 卸载（级联清理路径）

```
前端控制面板 "卸载 my-skill"
  │
  │  DELETE /api/skills/my-skill
  ▼
SkillLifecycle.uninstall("my-skill")
  │
  ├─(1)─ UnifiedSkillRegistry.unregister("my-skill")
  │       /my-skill 命令不可命中
  │
  ├─(2)─ rm -rf configs/skills/my-skill/
  │       删除物理目录
  │
  ├─(3)─ 清 DB：DELETE FROM app_settings WHERE key LIKE "skills.my-skill.%"
  │       删除 content_hash、enabled 等配置
  │
  ├─(4)─ 调 permission.clear_skill_permissions("my-skill")
  │       permission 删除永久 allow 记录 + session 内存（见 permission/dfd-interface.md）
  │
  └─(5)─ 清残留 run_dir：清理 tmp/skill-runs/ 中属于该 skill 的残留
         （按 run_id 前缀匹配）
```

### 辅助路径：启停切换

```
控制面板 "禁用 my-skill"
  │
  ▼
SkillLifecycle.disable("my-skill")
  └─ DB: skills.my-skill.enabled = false
     UnifiedSkillRegistry 在 match_command 时跳过已禁用的 skill

控制面板 "启用 my-skill"
  │
  ▼
SkillLifecycle.enable("my-skill")
  └─ DB: skills.my-skill.enabled = true
     UnifiedSkillRegistry 重新纳入匹配
```

### 关键分支条件

| 条件 | 行为 |
|------|------|
| skill name 与内置 skill 冲突 | 拒绝安装 |
| skill name 与已装 skill 冲突 | 拒绝安装（不做覆盖） |
| SKILL.md 无 frontmatter 或格式错误 | InvalidManifestError |
| zip 含 symlink / .. / 绝对路径 | 拒绝安装（SecurityError） |
| 解压比 > 100x 或总大小 > 50MB | 拒绝安装（SecurityError） |
| 用户取消安装确认 | 清理隔离区，不产生副作用 |
| skill 已禁用 | match_command 跳过，前端列表仍可见 |
| DB 不可达（读 content_hash） | ActivationContextBuilder 返回空 content_hash，skill 仍可激活但永久许可功能降级（每次弹卡） |

---

## 三、Interface Definition（接口定义）

### 3.1 对外暴露接口（运行时注册层）

#### UnifiedSkillRegistry.match_command()

- **调用方**：ChatService（消息入口）
- **语义**：根据 `/name` 命令匹配已注册的 skill
- **输入**：`command_name: str`（不含斜杠前缀）
- **输出**：`SkillManifest | None`
  - 命中：返回 `SkillManifest(system_prompt_addition, tools=[])` + 附带 `SkillContext`
  - 未命中：返回 None（ChatService 按普通消息处理）
- **同步/异步**：同步（内存查表 + DB 读 content_hash）

#### ActivationContextBuilder.build()

- **调用方**：ConfigSkillProvider（命中时调用）
- **语义**：构造激活 prompt 与 SkillContext
- **输入**：`skill_name: str`
- **输出**：`(system_prompt_addition: str, SkillContext)`
  - `SkillContext.name` — skill 名称
  - `SkillContext.content_hash` — 当前内容哈希（从 DB 读取）
  - `SkillContext.scripts_dir` — 固定 "/skill/scripts"
  - `SkillContext.work_dir_mount` — 固定 "/work"

### 3.2 对外暴露接口（管理层 REST API）

| 端点 | 方法 | 语义 | 关键输入 | 关键输出 |
|------|------|------|---------|---------|
| `/api/skills` | GET | 列出所有 skill | — | `[{name, enabled, source, content_hash, description}]` |
| `/api/skills/install` | POST | 安装 skill | `{source: "github"\|"local"\|"upload", url/path/file}` | `{manifest, content_hash}` |
| `/api/skills/<name>/preview` | GET | 查看隔离区预览 | `name` | `{frontmatter, file_tree, scripts, content_hash, scopes}` |
| `/api/skills/<name>` | DELETE | 级联卸载 | `name` | `{success: true}` |
| `/api/skills/<name>/toggle` | POST | 启停切换 | `name, enabled: bool` | `{enabled: bool}` |

### 3.3 对外暴露接口（供其他模块调用）

#### ContentHasher.calculate()

- **调用方**：SkillInstaller（安装完成后）
- **语义**：计算 skill 目录的 tree hash
- **输入**：`skill_dir: str`（如 "configs/skills/my-skill/"）
- **输出**：`content_hash: str`（SHA-256 的 hex 字符串）
- **算法**：递归遍历（按路径排序），每文件 SHA-256，所有 hash 拼接后再 SHA-256

#### SkillLifecycle.uninstall()

- **调用方**：前端控制面板 API、手动维护
- **语义**：级联卸载（五步）
- **输入**：`skill_name: str`
- **副作用**：见路径三

### 3.4 内部组件接口（供架构理解，外部不调用）

- `ManifestParser.parse(skill_md_path) -> ManifestMeta` — SKILL.md frontmatter 解析
- `SkillInstaller.install_from_github / install_from_local / install_from_zip` — 三通道
- `SkillInstaller._install_from_staging(staging_path)` — 统一的隔离区到正式目录流程
- `safety.py` 中的校验函数：`check_zip_slip / check_zip_bomb / check_file_size / check_no_git`

---

## 四、Data Ownership & Responsibility（数据归属与责任）

### 数据创建责任

| 数据 | 创建者 | 说明 |
|------|--------|------|
| `configs/skills/<name>/` 目录内容 | skills (SkillInstaller) | 安装时从隔离区移入 |
| `skills.<name>.content_hash` DB 记录 | skills (ContentHasher) | 安装完成时计算并写入 |
| `skills.<name>.enabled` DB 记录 | skills (SkillLifecycle) | 安装后默认启用 |
| `SkillContext` | skills (ActivationContextBuilder) | 每次激活时构造 |
| `SkillManifest` | skills (ConfigSkillProvider) | 每次命中时构造 |
| 激活 prompt | skills (ActivationContextBuilder) | 仅含 description + 读取指令 |

### 数据更新与销毁责任

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| skill 目录删除 | skills (SkillLifecycle) | 卸载时 rm -rf |
| `skills.<name>.*` DB 记录 | skills (SkillLifecycle) | 卸载时清除 |
| 永久 allow 记录（关联该 skill） | permission | skills 卸载时调用 permission.clear_skill_permissions |
| content_hash 变更 | skills (ContentHasher) | 重装/覆盖安装时重算并更新 DB |

### 当前模块不负责的数据

| 数据 | 责任模块 | 说明 |
|------|----------|------|
| capability_signature | policy | skills 只提供 SkillContext（含 name + content_hash） |
| permanent allow 记录 | permission | skills 只在卸载时触发清理 |
| skill 脚本执行结果 | core/tools/Bash + sandbox | skills 不参与执行路径 |
| 通用工具（Read/Glob/Grep/Bash） | core/tools | skills 不实现任何工具 |
| run_dir 创建 | core/tools/Bash | skills 不创建 tmp/skill-runs/ |
| 内置 skill 实现 | newbee_notebook/skills/（原 Python provider） | 保持原状 |

---

## 五、与其他模块 dfd-interface 的交叉引用

| 本文档描述的流向 | 对应模块文档 | 衔接点 |
|------------------|-------------|--------|
| SkillContext 经 agent_loop 传给 policy | [policy/dfd-interface.md](../policy/dfd-interface.md) | policy 用 SkillContext 构造 capability_signature |
| uninstall 时调 clear_skill_permissions | [permission/dfd-interface.md](../permission/dfd-interface.md) | permission 级联清理永久 allow + session 内存 |
| skill 脚本经 Bash → sandbox 执行 | [sandbox/dfd-interface.md](../sandbox/dfd-interface.md) | Bash 组装挂载清单（含 skill 目录） |
| ChatService 路由 /command | ChatService | match_command 返回 SkillManifest |

---

## 六、自检清单

- [x] 可以清楚说明每条数据从哪里来、到哪里去（激活：用户输入 → match_command → SkillManifest + SkillContext → agent_loop → policy；安装：三通道 → 隔离区 → 检验 → 预览 → 确认 → 正式目录 + DB；卸载：五步级联）
- [x] 所有接口都服务于明确的数据流（match_command 服务于激活，REST API 服务于管理，uninstall 服务于级联清理）
- [x] 不存在数据责任不清或重复处理的风险（skills 不生成 signature、不写 allow 记录、不执行脚本、不管理 run_dir）
- [x] 与 goals-duty.md 的 Non-Duties 一致（不实现通用工具、不实现沙箱、不做权限决策、不生成 signature、不在 system prompt 注入全文、不创建 run_dir）
- [x] 与 architecture.md 的子组件划分一致（UnifiedSkillRegistry / ConfigSkillProvider / ActivationContextBuilder 服务注册层；SkillInstaller / ManifestParser / ContentHasher / SkillLifecycle 服务管理层）
