# Backend-v2 阶段概览

## 阶段定位

backend-v2 是对现有后端系统的再加工与功能增强。在 backend-v1 完成了基础 RAG 对话引擎、文档管理、会话管理等核心功能后，backend-v2 将从三个维度推进系统演进：基础设施升级、AI 能力扩展、用户交互增强。

## 现有系统基线

backend-v2 在以下已稳定运行的系统基础上开展：

- **4 种对话模式**: chat (FunctionAgent) / ask (ReActAgent) / explain / conclude
- **文档处理流水线**: MinerU Cloud/Local + MarkItDown 转换链，Celery 异步任务
- **RAG 引擎**: pgvector 语义检索 + Elasticsearch 关键词检索 + RRF 融合
- **配置体系**: YAML 配置 (configs/*.yaml)，支持环境变量覆盖
- **API 接口**: 47 个 REST 端点，覆盖笔记本、文档、会话、对话、管理全生命周期
- **前端**: 三栏布局 (Sources / Chat+Reader / Studio)，Studio Panel 为占位符

## 需求清单

本阶段共 10 项需求，按实施批次组织：

### 第一批：基础设施层

| 编号 | 需求 | 对应模块文档 | 已有设计文档 |
|------|------|-------------|-------------|
| 9 | MinerU-cloud 流水线加入 docx 处理 | 01-batch1 | minerU-cloud/03-docx-extension.md |
| 7 | LLM 和 Embedding 模型配置验证 | 01-batch1 | -- |
| 6/10 | Markdown 文档按原始页码分页查看 | 01-batch1 | -- |
| 8 | MinIO 替代本地文档存储 | 01-batch1 | MinIO/*.md (5份完整设计) |

### 第二批：AI 能力升级层

| 编号 | 需求 | 对应模块文档 | 已有设计文档 |
|------|------|-------------|-------------|
| 5 | Agent 模式重构 (chat -> Agent) | 02-batch2 | chatagent/ (待补充) |
| 2 | Skill 功能实现 | 02-batch2 | skills/ (待补充) |
| 3 | MCP 功能实现 | 02-batch2 | mcp/ (待补充) |
| 4 | 对话中的图片接口 (Vision) | 02-batch2 | -- |

### 第三批：交互增强层

| 编号 | 需求 | 对应模块文档 | 已有设计文档 |
|------|------|-------------|-------------|
| 1 | Studio Panel 笔记 + 书签功能 | 03-batch3 | -- |

## 批次间依赖关系

```
第一批 (基础设施)
  ├── docx 扩展: 无依赖
  ├── 模型配置: 无依赖
  ├── 分页系统: 无依赖
  └── MinIO 迁移: 无依赖
         │
第二批 (AI 升级)
  ├── Agent 重构: 无依赖 (可与第一批并行)
  ├── Skill 系统: 依赖 Agent 重构
  ├── MCP 适配: 依赖 Agent 重构
  └── 图片接口: 依赖 MinIO (图片存储)
         │
第三批 (交互增强)
  └── Studio 笔记/书签: 依赖分页系统 (书签需页码定位)
```

