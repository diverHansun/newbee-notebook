# Backend V4 Core Shell And Filesystem Tools Implementation Notes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development. Keep this file in UTF-8.

## Goal

实现 `core/shell` 的首批环境与路径策略，并把 `read_file`、`glob_files`、`grep_files`、`edit_file`、`write_file` 接入内置工具注册，使 agent/chat 模式具备受控文件系统能力。

## Scope

- `core/shell` 本批提供 `ShellEnvironment`、默认环境构造和 `PathPolicy`。
- `core/tools/filesystem` 本批提供文本文件读、glob、grep、字符串替换、overwrite/append 写入。
- 文件写入类工具只声明 `tool_class` 与 `risk_level`，实际是否需要确认仍由全局 `policy -> permission` 链路决定。
- `bash` 不在本批直接实现 host shell 执行；后续必须通过 `core/shell -> core/sandbox`。
- 本地参考仓库 `deepagents/`、`kimi-cli/` 只用于阅读设计，不纳入提交。

## Task List

- [X] F401 Add failing unit tests for shell path policy and filesystem tool contracts.
- [X] F402 Implement `ShellEnvironment` with cwd, workspace roots, optional roots, run dir, env, timeout, and output caps.
- [X] F403 Implement `PathPolicy` with relative path normalization, allowed read/write roots, and sensitive-file blocking.
- [X] F404 Implement `read_file` with line-numbered UTF-8 text output, line limits, byte limits, and binary rejection.
- [X] F405 Implement `glob_files` with sorted relative results, broad-pattern rejection, sensitive-file filtering, and workspace escape prevention.
- [X] F406 Implement `grep_files` with regex search, glob filtering, output modes, head/offset limits, and sensitive-file filtering.
- [X] F407 Implement `edit_file` with single/all replacement handling, CRLF-aware matching, text-only checks, and unified diff output.
- [X] F408 Implement `write_file` with overwrite/append modes, parent directory validation, text-only overwrite checks, and unified diff output.
- [X] F409 Register filesystem tools for agent/chat via `BuiltinToolProvider` while keeping ask/explain/conclude unchanged.
- [X] F410 Run targeted verification and update this implementation note before commit.

## Acceptance Criteria

- Relative file paths resolve against the configured `cwd`.
- Reads are limited to workspace/additional/skill/run roots; writes are limited to workspace/run roots.
- Sensitive filenames such as `.env`, private keys, token, secret, and credential paths are blocked or skipped.
- `read_file` returns stable line-numbered output and rejects binary content.
- `glob_files` cannot return matches outside the configured workspace even when the pattern contains `..`.
- `grep_files` does not include sensitive files in output.
- `edit_file` does not mutate files on no-match or ambiguous multiple-match input.
- `write_file` refuses missing parent directories and non-text existing targets.
- Filesystem tools expose policy metadata:
  - read/glob/grep: `ToolClass.READ`, `RiskLevel.SAFE`
  - edit: `ToolClass.EDIT`, `RiskLevel.MODERATE`
  - write: `ToolClass.WRITE`, `RiskLevel.MODERATE`
- Agent/chat modes include filesystem tools; ask/explain/conclude modes do not.

## Verification

Targeted gate:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\shell newbee_notebook\tests\unit\core\tools\filesystem newbee_notebook\tests\unit\core\tools\test_filesystem_tool_contracts.py newbee_notebook\tests\unit\core\tools\test_tool_registry.py -q
```

Broader safety gate:

```powershell
.\.venv\Scripts\python.exe -m pytest newbee_notebook\tests\unit\core\shell newbee_notebook\tests\unit\core\tools newbee_notebook\tests\unit\core\policy newbee_notebook\tests\unit\core\permission newbee_notebook\tests\unit\core\engine newbee_notebook\tests\unit\core\session newbee_notebook\tests\unit\application\services\test_chat_runtime_routing.py newbee_notebook\tests\unit\application\services\test_chat_service_guards.py -q
```

Current result: `176 passed, 3 warnings`; warnings are existing Pydantic V2 deprecation warnings in infrastructure config and third-party vector store code.

## Next Batch Handoff

下一批建议实现 `core/sandbox` 基础执行契约与 `core/tools/bash.py`，但仍保持禁止直接 host shell 执行。`bash` 的工具 contract 可以先用 fake sandbox runner 做 unit 测试，再引入 Docker 或容器 runner 的 integration/smoke 测试。
