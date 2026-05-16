# Filesystem Tools Non-Functional Requirements

## Quality Priorities

1. 安全边界优先：任何文件读写或命令执行都必须经过 policy/permission 和路径范围校验。
2. 输出可预测：工具返回内容必须有明确的行数、字节数、时间和匹配数量上限，避免一次调用吞掉上下文窗口。
3. 行为可审计：写入类工具和 bash 工具必须返回足够信息，让日志、确认卡和测试可以还原发生了什么。
4. 实现可演进：首版优先清晰的 Python 实现与稳定接口，性能优化如 ripgrep 后端、后台 shell、sandbox-backed 文件操作可在后续批次替换。

## Operational Constraints

- `read_file` 应限制单次最大行数、最大行长和最大总字节数。
- `glob_files` 应限制最大返回数量，并拒绝默认从 workspace 顶层执行过宽 `**` 搜索。
- `grep_files` 应限制执行时间和输出大小；若后端支持部分结果，应明确标记 partial/truncated。
- `edit_file` 和 `write_file` 应只处理文本文件，不处理图片、视频、二进制和未知编码文件。
- `bash` 应有前台执行超时和最大输出限制；命令 stdin 应关闭或显式不可交互，防止挂起。
- `bash` 不应直接在 host shell 中执行；真实执行需要 `core/shell -> core/sandbox`。
- 敏感文件保护应至少覆盖 `.env`、密钥、凭证、SSH key、token 配置等常见模式。
- 路径解析必须处理相对路径、绝对路径、`~`、符号链接和 `..`，并以规范化后的路径做范围判断。
- 工具不得默认访问网络；网络能力只属于 sandbox 的显式执行配置。

## Reliability & Observability

- 所有失败都应返回结构化错误，不应抛出未处理异常给 `AgentLoop`。
- 错误信息应区分 empty path、outside workspace、file not found、not a file、not text、sensitive file、permission denied、timeout、output truncated。
- 写入类工具应在执行前构建 diff 预览，执行后返回替换数量或写入大小。
- bash 结果应区分成功退出、非零退出、超时、sandbox 启动失败、输出截断。
- 关键路径应记录结构化日志字段：session id、tool name、capability signature、normalized path、run id、exit code、duration、truncated。
- 日志不得包含完整敏感文件内容或未截断的大型 stdout/stderr。

## Trade-offs & Deferred Requirements

- 首版不追求最快 grep 性能，优先保证跨平台和可测试；ripgrep 后端可以作为后续优化策略接入。
- 首版不实现后台 bash 任务的完整生命周期，避免在 permission、session lock、SSE 恢复和任务取消之间引入过早复杂性。
- 首版不提供 AST 级编辑、patch 文件应用或多文件批量重构工具；先用字符串替换和写入工具覆盖最小可审计闭环。
- 首版不直接读取图片、视频、PDF、Office 文档等媒体内容；这些应由已有专用工具或后续媒体读取工具处理。
- 首版不把文件工具作为 sandbox 的唯一文件 API；先保持 `core/tools` 工具契约稳定，再按 sandbox 能力逐步迁移后端。
