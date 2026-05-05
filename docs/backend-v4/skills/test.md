# skills 模块 test.md

本文档说明如何验证 `newbee_notebook/core/skills/`（升级）与 `configs/skills/`（存储根）协同构成的 skills 模块在真实协作环境中的正确性。设计基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[dfd-interface.md](dfd-interface.md)。

skills 是一个**混合原型模块**：管理层（SkillInstaller / SkillLifecycle）是服务编排，注册层（UnifiedSkillRegistry / ConfigSkillProvider）是桥接/适配（将 `/command` 路由映射到 mellow 可消费的 SkillManifest + SkillContext）。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：混合原型（服务编排 + 桥接/适配）
- **主要测试类型**：
  - 管理层（安装/卸载/生命周期）：unit + integration
  - 注册层（命令匹配/激活上下文）：unit + contract
  - REST API（/api/skills）：contract
- **Mock 边界**：
  - AppSettingsService（DB）：integration 用内存 SQLite；unit 用 mock
  - 文件系统：unit 用 tmp_path fixture；integration 用真实 `configs/skills/` 测试目录
  - permission.clear_skill_permissions：unit 用 mock 验证调用
  - GitHub API / multipart upload：unit 用 mock
  - 前端控制面板 / SlashCommandHint：不 mock（前端测试范围）
- **测试归属目录**：`tests/unit/core/skills/` + `tests/integration/core/skills/` + `tests/contract/api/skills/`

---

## 二、Test Scope（测试范围）

### 覆盖

#### 管理层（unit + integration 侧重）

- SkillInstaller：三通道安装（GitHub URL / 本地路径 / zip 上传）的正确性与安全性
- 安全校验：zip slip / zip bomb / 大小上限 / 嵌套 .git 拒绝 / symlink 拒绝
- ManifestParser：SKILL.md frontmatter 解析与 Anthropic 规范校验（name/description/length/保留词/唯一性）
- ContentHasher：tree hash 的稳定性（同一目录两次计算同哈希、内容变更哈希变更）
- SkillLifecycle：enable/disable 的启停正确性；uninstall 的五步级联完整性

#### 注册层（unit + contract 侧重）

- UnifiedSkillRegistry：命令匹配（命中/未命中/禁用时的行为）、双轨共存（内置 skill + 用户 skill 不冲突）
- ConfigSkillProvider：frontmatter 只读（不读正文）、tools 返回空列表
- ActivationContextBuilder：激活 prompt 格式（仅含 description + 读取指令，不嵌入正文）、SkillContext 字段完整性

#### REST API（contract test 侧重）

- `GET /api/skills`：列表字段完整性
- `POST /api/skills/install`：三通道入口
- `GET /api/skills/<name>/preview`：隔离区预览 manifest
- `DELETE /api/skills/<name>`：级联卸载（断言调了 permission.clear_skill_permissions）
- `POST /api/skills/<name>/toggle`：启停切换

### 不覆盖

- mellow 如何使用 Read/Glob/Grep/Bash 消费 skill 内容（属于工具链/agent_loop 测试范围）
- sandbox 如何隔离执行脚本（属于 sandbox 测试范围）
- policy 如何用 SkillContext 构造 signature（属于 policy 测试范围）
- permission 的 clear_skill_permissions 实现细节（属于 permission 测试范围）
- 前端 SlashCommandHint 动态渲染与控制面板 UI（属于前端测试范围）
- 内置 skill（note/diagram/video）的实现逻辑（已有各自测试）

---

## 三、Critical Scenarios（关键场景）

### ManifestParser 校验

| # | 场景 | 预期结果 |
|---|------|---------|
| 1 | SKILL.md 含 name + description 标准 frontmatter | 解析成功，返回 ManifestMeta(name, description) |
| 2 | name 含大写字母 | InvalidManifestError |
| 3 | name 长度 > 64 | InvalidManifestError |
| 4 | name 为 "anthropic" 或 "claude" | InvalidManifestError（保留词） |
| 5 | description 为空 | InvalidManifestError |
| 6 | description 长度 > 1024 | InvalidManifestError |
| 7 | frontmatter 含多余字段（如 version） | 解析成功但警告（非致命），多余字段忽略 |
| 8 | name 与已装 skill 重复 | SkillNameConflict（拒绝安装） |
| 9 | name 与内置 skill（note/diagram/video）重复 | SkillNameConflict（拒绝安装） |
| 10 | name 含连接号开头（如 "-my-skill"） | InvalidManifestError |
| 11 | name 含下划线或点号 | InvalidManifestError |
| 12 | name 长度为 1 字符（最小有效） | 解析成功 |
| 13 | name 长度为 64 字符（最大有效） | 解析成功 |
| 14 | name 为空或缺失 | InvalidManifestError |
| 15 | name 或 description 含 XML 标签 | InvalidManifestError（Anthropic 规范禁 XML） |
| 16 | description 含 XML 标签 | InvalidManifestError |

### 安装安全性

| # | 场景 | 预期结果 |
|---|------|---------|
| 17 | zip 含 `../` 路径（zip slip） | SecurityError，拒绝 |
| 18 | zip 含绝对路径（如 `/etc/passwd`） | SecurityError，拒绝 |
| 19 | zip 含 symlink entry | SecurityError，拒绝 |
| 20 | zip 含 hardlink entry | SecurityError，拒绝 |
| 21 | 解压比 > 100x（zip bomb） | SecurityError，拒绝 |
| 22 | 目录总大小 > 50MB | SecurityError，拒绝 |
| 23 | 单文件 > 10MB | SecurityError，拒绝 |
| 24 | 含嵌套 `.git` 目录 | SecurityError，拒绝 |
| 25 | 本地路径安装含 symlink | SecurityError，拒绝（lstat 检测） |
| 26 | 本地路径安装正常目录（无 symlink） | copy 成功，进入隔离区 |

### ContentHasher 稳定性

| # | 场景 | 预期结果 |
|---|------|---------|
| 27 | 同一目录两次计算 hash | 两次结果完全一致（路径排序稳定 + SHA-256 确定性） |
| 28 | 目录中任一文件内容变更 | hash 与变更前不同 |
| 29 | 目录中新增文件 | hash 与新增前不同 |
| 30 | 目录中删除文件 | hash 与删除前不同 |
| 31 | 仅文件修改时间变更（内容不变） | hash 不变 |

### 级联卸载

| # | 场景 | 预期结果 |
|---|------|---------|
| 32 | uninstall 完整执行五步 | (1) registry 移除 (2) 物理目录删除 (3) DB config 清除 (4) permission.clear_skill_permissions 被调用 (5) run_dir 残留清理 |
| 33 | uninstall 后 /name 不再命中 | UnifiedSkillRegistry.match_command 返回 None |
| 34 | uninstall 后重新安装同名 skill | 允许安装（DB 与物理目录均已清除） |
| 35 | 卸载不存在的 skill | SkillNotFoundError（不乱删、不抛内部异常） |

### 激活上下文

| # | 场景 | 预期结果 |
|---|------|---------|
| 36 | ActivationContextBuilder 生成 prompt | prompt 含 description + "use Read tool to open configs/skills/<name>/SKILL.md" + 不含 SKILL.md 正文 |
| 37 | SkillContext 字段完整性 | name、content_hash、scripts_dir="/skill/scripts"、work_dir_mount="/work" 四个字段全部存在 |
| 38 | content_hash 从 DB 读取 | 调用 ActivationContextBuilder.build 前写入 DB skills.<name>.content_hash，断言读取值等于写入值 |
| 39 | DB 不可达时 content_hash 为空 | ActivationContextBuilder.build 返回 SkillContext(content_hash="")，不抛异常（降级行为） |

### 命令匹配与双轨

| # | 场景 | 预期结果 |
|---|------|---------|
| 40 | /my-skill 匹配已注册用户 skill | 返回 SkillManifest + SkillContext |
| 41 | /note 匹配内置 Python skill | 返回内置 provider 的 SkillManifest（tools 非空） |
| 42 | /unknown-skill 未匹配 | 返回 None |
| 43 | /my-skill 但 skill 已禁用 | 返回 None（match_command 跳过禁用项） |
| 44 | ConfigSkillProvider.get_manifest().tools | 恒为空列表（通用工具不在此声明） |

### REST API 契约

| # | 场景 | 预期结果 |
|---|------|---------|
| 45 | GET /api/skills 返回列表 | 每项含 name、enabled、source、content_hash、description |
| 46 | POST /api/skills/install 合法请求 | 隔离区预览 manifest 返回，等待确认 |
| 47 | GET /api/skills/<name>/preview | 返回文件树 + 每文件 SHA-256 + scripts 清单 + content_hash + scopes |
| 48 | DELETE /api/skills/<name> 卸载 | 成功删除 + 调了 permission.clear_skill_permissions |
| 49 | POST /api/skills/<name>/toggle enabled=false | DB 记录更新 + match_command 跳过 |

---

## 四、Contract Specification（契约规约）

### GET /api/skills

- **响应体**：`{ "skills": [{ "name", "enabled", "source", "content_hash", "description" }] }`
- **状态码**：200

### POST /api/skills/install

- **请求体**：`{ "source": "github" | "local" | "upload", "url": str, "path": str, "file": multipart }`（按 source 选填对应字段）
- **成功响应**：200，body 含 `{ "manifest": { "name", "description", "file_tree": [...], "scripts": [...], "content_hash", "scopes": ["/<name>"] } }`（隔离区预览，等待第二步确认——用户在前端审阅后点"确认安装"触发第二步移入正式目录）
- **安全拒绝**：400，body 含 `{ "error": "zip_slip" | "zip_bomb" | "file_too_large" | "nested_git" | "symlink_rejected" }`
- **manifest 无效**：400，body 含 `{ "error": "invalid_manifest", "details": "..." }`
- **name 冲突**：409，body 含 `{ "error": "name_conflict", "existing": "..." }`

### GET /api/skills/<name>/preview

- **响应体**：`{ "manifest": { "name", "description", "file_tree": [{ "path", "size", "sha256" }], "scripts": [...], "content_hash", "scopes": ["/<name>"] } }`
- **skill 未在隔离区**：404
- **状态码**：200

### DELETE /api/skills/<name>

- **成功**：200，body 含 `{ "success": true }`
- **skill 不存在**：404

### POST /api/skills/<name>/toggle

- **请求体**：`{ "enabled": bool }`
- **成功**：200，body 含 `{ "enabled": bool }`
- **skill 不存在**：404

---

## 五、Integration Points（集成点测试）

| 集成点 | 测试类型 | 验证重点 |
|--------|---------|---------|
| SkillInstaller → 文件系统（隔离区 ↔ configs/skills/） | integration | 隔离区文件 mv 到正式目录的原子性；权限正确（目录可读、文件可读） |
| ContentHasher → 文件系统 | unit（tmp_path） | tree hash 算法跨平台一致性（Windows/Linux 路径分隔符差异） |
| SkillLifecycle → AppSettingsService（DB） | integration | `skills.<name>.enabled` / `content_hash` 读写正确；卸载后 key 无残留 |
| SkillLifecycle → permission.clear_skill_permissions | integration | 卸载时 permission 被调用且传入正确的 skill_name |
| UnifiedSkillRegistry → 内置 Python provider | integration | 双轨共存：内置 skill 的 match 逻辑不受用户 skill 注册/卸载影响 |
| ConfigSkillProvider → DB（content_hash） | integration | 激活时从 DB 读取的 content_hash 与 ContentHasher 计算的一致 |

---

## 六、Verification Strategy（验证策略）

### 执行环境

- unit 测试：纯 Python + tmp_path fixture，无需 docker/DB/外部服务
- integration 测试：需要内存 SQLite + 临时 `configs/skills/` 测试目录
- contract 测试：需要 FastAPI TestClient + 内存 SQLite

### 测试组织

```
tests/unit/core/skills/
├── test_manifest_parser.py          # ManifestParser Anthropic 规范校验
├── test_safety.py                   # zip slip / bomb / 大小 / .git / symlink 校验
├── test_content_hasher.py           # ContentHasher 稳定性与变更检测
├── test_config_provider.py          # ConfigSkillProvider tools=[] + frontmatter 只读
└── test_activation.py               # ActivationContextBuilder prompt 格式与 SkillContext

tests/integration/core/skills/
├── test_install_flow.py             # 三通道安装完整流程（含安全校验）
├── test_uninstall_cascade.py        # 级联卸载五步验证
├── test_lifecycle.py                # enable/disable/uninstall
└── test_unified_registry.py         # 双轨匹配（内置 + 用户 skill 共存）

tests/contract/api/skills/
├── test_api_list.py                 # GET /api/skills 响应格式
├── test_api_install.py              # POST /api/skills/install 各 source 通道
├── test_api_preview.py              # GET /api/skills/<name>/preview
├── test_api_uninstall.py            # DELETE /api/skills/<name>
└── test_api_toggle.py               # POST /api/skills/<name>/toggle
```

### 关键测试模式

- **ContentHasher 稳定性**：用 tmp_path 创建固定文件树，调用两次 calculate，断言输出相同；再修改一个文件，断言输出不同
- **zip slip 防御**：手工构造恶意 zip（含 `../` 路径的 entry），断言 SkillInstaller 抛 SecurityError
- **级联卸载完整性**：安装 → 放行一次（permission 写 allow）→ 卸载 → 断言 permission.clear_skill_permissions 被调用 + DB skills.* 记录不存在 + 物理目录不存在
- **双轨不冲突**：安装名为 "note" 的 skill 被拒绝（与内置 skill 冲突）；内置 skill 的 /note 匹配不受其他用户 skill 注册影响
- **ActivationContextBuilder 不嵌入正文**：构造含 100KB 正文的 SKILL.md，运行 build()，断言返回的 prompt 长度 < 2KB（仅含 description + 指令）
- **REST API 字段完整**：用 TestClient 调 API，断言响应 JSON 的 key 集合与契约一致
