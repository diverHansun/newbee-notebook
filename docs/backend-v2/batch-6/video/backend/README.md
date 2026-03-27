# Video 模块 -- 后端设计文档

## 模块定位

Video 模块是 Studio 工作区中与 Note、Diagram 同级的内置 Skill 板块，为用户提供视频内容获取、总结和管理能力。第一阶段聚焦 Bilibili 平台，架构上预留 YouTube 等平台的扩展空间。

## 核心场景

1. 用户在 Studio 的 Video 面板中输入视频 URL 或 BV 号，触发独立的总结 pipeline，不占用 main 面板的 agent 资源
2. 用户在 main 面板通过 `/video` slash 命令或对话触发 agent 调用 video skill 工具，总结结果同步展示在 Video 面板
3. 视频总结可选择性地关联到当前 notebook 和 documents，纳入 RAG 知识体系

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| 02 | [architecture.md](02-architecture.md) | 架构设计与模块结构 |
| 03 | [data-model.md](03-data-model.md) | 数据模型与存储设计 |
| 04 | [bilibili-infrastructure.md](04-bilibili-infrastructure.md) | Bilibili 基础设施层 |
| 05 | [service-layer.md](05-service-layer.md) | 应用服务层与总结 Pipeline |
| 06 | [skill-provider.md](06-skill-provider.md) | VideoSkillProvider 与工具定义 |
| 07 | [api-layer.md](07-api-layer.md) | REST API 与 SSE 端点 |
| 08 | [test.md](08-test.md) | 验证策略 |

## 参考项目

- `bilibili-cli/bili_cli` -- Bilibili CLI 工具，提供视频信息查询、搜索、字幕获取等能力，本模块的 BilibiliClient 从中移植核心逻辑
- `bilibili-summary/` -- Bilibili 视频总结器，提供完整的字幕提取、ASR 转录、AI 总结 pipeline，本模块的 VideoService.summarize() 从中移植核心流程

## 与其他 batch 的关系

| Batch | 关联 |
|-------|------|
| batch-2 | 复用 core/engine 的 AgentLoop、ToolRegistry、ModeConfig 等运行时基础设施 |
| batch-3 | 沿用 SkillManifest、SkillRegistry、SkillProvider、ConfirmationGateway 等 skill 抽象 |
| batch-4 | 与 DiagramSkillProvider 同级，共享 skill 注册和 slash 命令匹配机制 |
