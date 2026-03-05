# LLM / Embedding 模型配置切换方案

## 1. 背景

在 backend-v1 阶段，LLM 和 Embedding 模型的选择通过 YAML 配置文件 (`configs/llm.yaml`, `configs/embeddings.yaml`) 和环境变量 (`.env`) 实现。切换模型需要修改配置文件并重启服务，这对开发者友好但不适合最终用户。

随着前端 Control Panel 的建设，模型配置面板 (当前标记为"即将推出") 需要支持用户在界面上直接切换 LLM Provider、模型名称、推理参数以及 Embedding 模式，且切换后立即生效，无需重启服务。

本方案实现 **模型配置的运行时热切换**，通过 DB 持久化用户偏好、后端 API 暴露配置读写能力、前端 Control Panel 提供直观的模型配置界面。

## 2. 设计原则

1. **DB 持久化用户意图**: 用户通过前端 UI 设定的模型偏好存入数据库，配置文件作为不可变的系统默认值。
2. **分层优先级**: DB 用户设定 > 环境变量 > YAML 默认值 > 代码硬编码，各层职责清晰互不覆盖。
3. **恢复默认**: 用户可随时清除 DB 中的自定义设定，回退到系统默认配置。
4. **Embedding 安全切换**: Embedding 模型切换仅影响后续新文档的索引，已索引文档通过 pgvector 多表机制保持可用。
5. **最小侵入**: 不改动现有 Registry 模式和 Builder 工厂函数的架构，仅在配置读取层插入 DB 查询。

## 3. 核心决策

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 运行时持久化方式 | PostgreSQL `app_settings` 表 | 复用现有 DB 基础设施，支持多实例共享 |
| 配置覆盖机制 | DB > env > YAML 分层读取 | 避免内存态 override 重启丢失 |
| API 路由归属 | `/api/v1/config/*` | 普通用户功能，不放在 `/admin` 下 |
| LLM 模型选择 | 预设 + 自由输入 | 预设 `glm-4.7-flash` / `qwen3.5-plus`，支持用户填入任意模型名 |
| Embedding 维度 | 固定 1024 | 当前所有 provider 均为 1024 维，不暴露给用户 |
| 系统默认 LLM | qwen, qwen3.5-plus | 性能与成本平衡 |
| 系统默认 Embedding | API 模式, text-embedding-v4 | 云端 API 无需本地 GPU，开箱即用 |
| 配置文件 `index_dir` | 标记废弃，计划移除 | pgvector 迁移后本地文件索引不再使用 |

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-current-analysis.md](./01-current-analysis.md) | 现状分析: 当前配置加载链、单例管理、优先级机制的完整梳理 |
| 02 | [02-backend-api.md](./02-backend-api.md) | 后端 API 设计: 配置读写端点、数据模型、单例重置机制 |
| 03 | [03-frontend-ui.md](./03-frontend-ui.md) | 前端 UI 设计: Control Panel 模型面板的交互设计与组件结构 |
| 04 | [04-implementation-plan.md](./04-implementation-plan.md) | 实施计划: 分步任务拆解、验收标准、风险评估 |

## 5. 与现有文档的关系

- **backend-v2/original/01-batch1-infrastructure.md**: 批次一模块 2 "LLM / Embedding 模型配置验证"，本方案是该模块的详细设计。
- **configs/llm.yaml, configs/embeddings.yaml**: 系统默认配置文件，本方案不修改其内容，仅调整读取优先级。
- **前端 control-panel.tsx**: 当前 "model" 标签为 `is-disabled` 状态，本方案将其激活并实现完整功能。

## 6. 当前状态

- 文档状态: 设计评审中，待确认后进入实施阶段
