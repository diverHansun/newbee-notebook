# Video Module Improve-2: 优化目标

## 背景

improve-1 完成后，video 模块已具备完整的字幕/ASR 转录链路、BilibiliClient 全量方法、
ASR 配置面板、B站 AI 总结 agent 工具，以及工具数从 12 精简到 9 的合并。

在实际使用和代码审查中，发现以下遗留问题:

1. 前端 VideoList 组件缺少"返回 Studio"按钮，与 Notes/Diagrams 列表交互不一致
2. tools.py 中旧的独立工具构建函数已被合并工具取代，但死代码未清理
3. Agent 缺少修改视频总结内容的能力，无法在会话中编辑已有总结
4. LLM 总结提示词未明确输出格式为 markdown，且未指定输出语言

---

## 优化目标

### O1: VideoList 返回按钮修复

VideoList 组件缺少返回 Studio 主页的按钮。Notes 列表和 Diagrams 列表在 header 的
`row-between` 容器第一个位置放置了 `backToHome` 按钮，VideoList 需要对齐。

- 涉及文件: `frontend/src/components/studio/video-list.tsx`、`studio-panel.tsx`
- 参考: `renderNotesList()` (studio-panel.tsx:417)、`renderDiagramsList()` (studio-panel.tsx:602)

详见: [02-frontend-video-list.md](02-frontend-video-list.md)

### O2: tools.py 死代码清理

improve-1 将 12 个工具合并为 9 个后，5 个旧的独立工具构建函数不再被任何地方引用，
需要删除以保持代码整洁。

- 涉及文件: `newbee_notebook/skills/video/tools.py`

详见: [03-dead-code-cleanup.md](03-dead-code-cleanup.md)

### O3: 新增 update_summary Agent 工具

当前 agent 可以读取和删除视频总结，但无法修改总结内容。需要新增 `update_summary`
工具，允许 agent 在会话中编辑已有总结的 markdown 内容。该操作需要 ConfirmCard 确认。

- 涉及文件: `video_service.py`、`tools.py`、`provider.py`

详见: [04-update-summary-tool.md](04-update-summary-tool.md)

### O4: 总结内容 Markdown 格式规范

当前 summary_content 的格式没有明确约定。LLM 实际输出 markdown，但 system prompt
未明确要求。需要在提示词中规范输出格式为 markdown，并统一相关代码的格式处理。

- 涉及文件: `video_service.py`

详见: [05-summary-format.md](05-summary-format.md)

---

## 范围边界

### 纳入范围

- 前端 VideoList 返回按钮修复
- tools.py 5 个死代码函数删除
- VideoService 新增 `update_summary_content` 方法
- Agent 新增 `update_summary` 工具 + ConfirmCard
- LLM 总结提示词明确 markdown 格式输出

### 不纳入范围

- i18n 系统提示词国际化 (后续单独处理)
- Studio 面板 UI 改版
- 视频总结的重新生成/覆盖功能
- 前端 markdown 渲染器调整

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-goals.md](01-goals.md) | 本文件: 优化目标、范围边界 |
| [02-frontend-video-list.md](02-frontend-video-list.md) | VideoList 返回按钮修复方案 |
| [03-dead-code-cleanup.md](03-dead-code-cleanup.md) | tools.py 死代码清理清单 |
| [04-update-summary-tool.md](04-update-summary-tool.md) | update_summary 工具设计 |
| [05-summary-format.md](05-summary-format.md) | 总结内容 markdown 格式规范 |
