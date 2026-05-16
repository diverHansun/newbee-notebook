# skills 模块 non-functional.md

本文档说明 skills 模块在功能正确性之外必须满足的工程约束。设计基于 [goals-duty.md](goals-duty.md) 与 [architecture.md](architecture.md)。

skills 模块处于 newbee 能力扩展的**入口边界**：它接收外部来源（GitHub / 本地 / zip）的代码并在隔离区完成校验后放入系统。安装安全是首要非功能约束，其次才是激活延迟与存储空间。

---

## 一、Quality Priorities（质量优先级）

按优先级从高到低：

1. **安装安全 > 用户体验**
   zip slip 防御、zip bomb 防御、symlink 拒绝、`.git` 拒绝、文件大小上限等安全校验不可为了"装得快"或"少报错"而放松。宁可多拒绝一个合法 skill 也不放过一个恶意 skill。

2. **级联卸载完整性 > 卸载速度**
   卸载时必须完成五步（registry 移除 → 物理删目录 → 清 DB → 调 permission → 清 run_dir 残留）。任一步遗漏都意味着许可残留或路径残留，是不可接受的失败。

3. **Anthropic 规范严格性 > 灵活性**
   frontmatter 仅接受 name + description 两字段；不引入 `runtime` / `network` / `timeout` 等私有扩展字段。保持与 Anthropic skill 生态的规范对齐优先于便利性。

4. **激活延迟 < 内容哈希精度**
   激活时需从 DB 读 content_hash，延迟 < 5ms（DB 主键查询）。不因追求"更快"而缓存旧哈希——每次从 DB 读取确保热加载场景下的正确性。

5. **可移植性透明 > 无缝体验**
   skill 在 newbee 的可用性不等于在其他 skill host 的可移植性。预览面板显式声明此限制，不隐瞒 script 级的不兼容性。

---

## 二、Operational Constraints（运行约束）

### 调用频次

- **激活路径**（运行时高频）：用户每次输入 `/skill-name` 触发一次 match_command + build SkillContext，与对话节奏一致，每分钟数次
- **安装路径**（管理时低频）：用户主动操作，日均可能数次至数十次
- **卸载/启停路径**：更低频

### 延迟目标

- `match_command`：内存查表，< 1ms
- `ActivationContextBuilder.build`：含一次 DB 读（`app_settings.key` 主键匹配），< 5ms p99
- 安装（含下载/解压/校验）：不设硬上限（受网络带宽与解压大小主导），用户体验通过预览-确认两步分流

### 存储约束

- 单个 skill 目录：总大小 ≤ 50MB，单文件 ≤ 10MB（安装期硬性拒绝）
- `configs/skills/` 总大小：不设上限（由用户自行管理），但列表 API 返回每 skill 的目录大小供面板展示
- 隔离区 `tmp/skill-installs/`：安装完成/取消后清理；残留由周期性清理任务回收（48h TTL）

### 资源占用

- 进程内存：UnifiedSkillRegistry 中注册的 skill 数量决定内存占用；预计 < 100 个 skill，每个 skill 在内存中仅 name + description + content_hash（< 2KB），总计 < 200KB
- DB：`skills.*` 配置项，每个 skill 约 3~5 条 key（enabled / content_hash / sandbox_policy / source 等），< 1KB/skill

### 外部依赖稳定性

- GitHub API（codeload）：不可达时 `install_from_github` 返回 NetworkError，不阻塞、不重试
- AppSettingsService（DB）：不可达时激活失败（降级：content_hash 为空，permission 后续查 allow 时 scope 恰好不命中视为未允许）；安装/卸载拒绝执行
- 文件系统：`configs/skills/` 目录不可写时安装失败；不可读时所有 skill 激活失败

---

## 三、Reliability & Observability（可靠性与可观测性）

### 失败容忍

| 失败类型 | 行为 | 用户感知 |
|---------|------|---------|
| GitHub 下载失败 | `install_from_github` 返回错误，提示检查 URL 或网络 | 安装失败，重试 |
| zip 校验失败（slip/bomb/大小） | SecurityError，拒绝安装 | 安装被拒，提示原因 |
| ManifestParser 校验失败 | InvalidManifestError，拒绝安装 | 安装被拒，提示 frontmatter 具体问题 |
| name 冲突 | SkillNameConflict，拒绝安装 | 提示改名或卸载同名 skill |
| DB 不可达（读 content_hash） | ActivationContextBuilder 返回空 content_hash | skill 仍可激活，但永久许可功能降级（每次弹卡） |
| DB 不可达（写） | 安装/卸载/启停操作拒绝执行 | 操作失败，重试 |
| 文件系统不可写 | 安装失败 | 操作失败，重试 |
| 卸载中任一步失败 | 继续执行后续步骤（best-effort），不因一步失败中止全部 | 管理员需手动检查残留 |

### 不可接受的失败

- **静默通过安全校验**：zip slip/bomb 被绕过
- **卸载残留**：skill 目录已删但 DB config 或 permission allow 仍存在（导致重装后旧许可意外生效）
- **content_hash 碰撞**：两个不同内容的 skill 产出同一 hash（SHA-256 概率极低，但若发现需立即修复算法）
- **内置 skill 被误停**：用户 skill 的注册/卸载影响内置 skill 的 `/note` `/diagram` `/video` 路由

### 结构化日志

- 每次安装记录 INFO：source 类型、skill_name、content_hash、文件数、总大小
- 每次卸载记录 INFO：skill_name、删除文件数、DB 记录数、permission 清除条目数
- 每次激活记录 DEBUG：skill_name、content_hash
- 每次安全拒绝记录 WARN：skill_name（若有）、拒绝原因（zip_slip/zip_bomb/...）、具体触发值

### 安全测试要求

- CI 必须跑恶意 zip 样本集（zip slip / zip bomb / symlink / hardlink / .git 嵌套）的自动化拦截测试
- ManifestParser 的保留词/长度/格式校验必须覆盖所有 Anthropic 规范边界条件

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 当前阶段不做

1. **skill 签名验证（GPG/ed25519）**
   当前不验证 skill 来源的加密签名。
   原因：skill 的信任边界由 sandbox 隔离保证（host :ro + 网络隔离 + 硬化），签名验证是额外一层保证但非必需。ContentHasher 的 tree hash 已能检测内容篡改。

2. **skill 依赖声明（A 依赖 B）**
   SKILL.md 无 `requires` 字段。
   原因：当前 skill 复杂度下，依赖管理收益小；未来需要时可通过 ManifestParser 的可选字段扩展。

3. **skill 热更新（不卸载直接覆盖）**
   只支持先卸载再重装。
   原因：覆盖安装与级联卸载的交互边界复杂（需决定"覆盖时是否保留永久许可"）；先卸后装的语义最简单清晰。

4. **skill 市场 / 远程索引**
   只支持用户手动输入 GitHub URL / 本地路径 / 上传 zip。
   原因：YAGNI——无足够 skill 生态驱动；未来 Anthropic Skills API 成熟后再接。

5. **skill 运行统计**
   不统计"哪个 skill 被调了多少次""哪些 script 最耗时"。
   原因：sandbox 的 exec.json 落盘已提供单次运行信息；聚合统计可在 v2 通过日志分析实现。

6. **多用户 skill 隔离**
   所有 skill 安装在全局 `configs/skills/`，所有用户可见。
   原因：newbee v1 是单用户本地工具假设。

### 已接受的代价

- 本地安装仅支持 copy（不支持 symlink），开发者迭代需重装——安全代价必须付
- 安装前必须经过"预览-审查-确认"两步，非一键安装——安全保证优先于便利
- content_hash 绑定许可导致 skill 每次更新后需重新确认——安全代价正确
- 级联卸载五步可能较慢（需等 DB 操作 + permission 清理）——完整性优先于速度
- 不支持覆盖安装，同名 skill 必须卸载重装——最简单的语义
