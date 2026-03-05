# 实施计划: 分步任务拆解与验收标准

本文档将模型配置切换方案拆解为可执行的任务序列，明确每步的验收标准、依赖关系和风险评估。

---

## 1. 任务概览

共分为 5 个阶段，按依赖顺序执行:

```
阶段 1: 数据层 (DB 模型 + Service)
   |
   v
阶段 2: 配置层 (config_db + 优先级改造)
   |
   v
阶段 3: API 层 (路由 + 单例重置)
   |
   v
阶段 4: 前端 (UI 组件 + API 对接)
   |
   v
阶段 5: Worker 同步 + 集成测试
```

预估总工时: 5-6 天

---

## 2. 阶段 1: 数据层

**目标**: 建立 `app_settings` 表和 CRUD 服务

### 任务 1.1: ORM 模型

- 在 `infrastructure/persistence/models.py` 新增 `AppSettingModel`
- 字段: `key` (VARCHAR 128, PK), `value` (TEXT), `updated_at` (TIMESTAMP)

**验收标准**:
- `AppSettingModel` 类定义完整，继承 `Base`
- 类型注解使用 `Mapped[]` 风格，与现有模型一致

### 任务 1.2: Schema 迁移

- 在 `database.py` 的 `_ensure_runtime_schema()` 中追加 `CREATE TABLE IF NOT EXISTS app_settings` 语句

**验收标准**:
- 服务启动后 `app_settings` 表自动创建
- 重复启动不报错 (IF NOT EXISTS)
- 不影响现有表

### 任务 1.3: AppSettingsService

- 新建 `application/services/app_settings_service.py`
- 实现: `get()`, `get_many()`, `set()`, `set_many()`, `delete()`, `delete_prefix()`
- 使用 PostgreSQL 的 `INSERT ON CONFLICT DO UPDATE` (upsert)

**验收标准**:
- 单元测试覆盖所有 6 个方法
- `set()` 幂等: 重复 set 同一 key 不报错，更新 value 和 updated_at
- `delete_prefix("llm.")` 删除所有以 `llm.` 开头的条目

**预估工时**: 0.5 天

---

## 3. 阶段 2: 配置层

**目标**: 实现 DB-first 配置优先级链

### 任务 2.1: 系统默认值常量

- 新建 `core/common/config_db.py`
- 定义 `SYSTEM_DEFAULTS` 字典，包含 LLM 和 Embedding 的默认配置
- LLM 默认: provider=qwen, model=qwen3.5-plus, temperature=0.7, max_tokens=32768, top_p=0.8
- Embedding 默认: provider=qwen3-embedding, mode=api, api_model=text-embedding-v4

**验收标准**:
- 常量定义完整，值与 YAML 配置文件中的默认值一致
- 其他模块可通过 `from config_db import SYSTEM_DEFAULTS` 引用

### 任务 2.2: 异步配置读取函数

- 在 `config_db.py` 中实现异步版本的 getter:
  - `get_llm_provider_async(session)` -> str
  - `get_llm_config_async(session)` -> dict (完整 LLM 配置)
  - `get_embedding_provider_async(session)` -> str
  - `get_embedding_config_async(session)` -> dict
- 每个函数实现四级 fallback: DB > env > YAML > SYSTEM_DEFAULTS

**验收标准**:
- DB 有值时返回 DB 值
- DB 无值时降级到 env (已有逻辑)
- env 无值时降级到 YAML (已有逻辑)
- YAML 无值时降级到 SYSTEM_DEFAULTS
- DB 查询异常时 catch 并降级，不阻塞

**预估工时**: 1 天

---

## 4. 阶段 3: API 层

**目标**: 实现配置读写端点和单例重置

### 任务 3.1: 单例重置函数

- 在 `api/dependencies.py` 新增:
  - `reset_llm_singleton()`: 将 `_llm` 置为 `None`
  - `reset_embedding_singleton()`: 将 `_embed_model` 和 `_pgvector_index` 同时置为 `None`
- 添加日志记录

**验收标准**:
- 调用 `reset_llm_singleton()` 后，下次 `get_llm_singleton()` 重建新实例
- 调用 `reset_embedding_singleton()` 后，`_embed_model` 和 `_pgvector_index` 均被重置
- SessionManager 无需修改 (已验证其每次请求重建 LLM)

### 任务 3.2: 配置路由

- 新建 `api/routers/config.py`，前缀 `/config`
- 实现 6 个端点:
  1. `GET /config/models` - 当前配置
  2. `GET /config/models/available` - 可用选项
  3. `PUT /config/llm` - 更新 LLM
  4. `PUT /config/embedding` - 更新 Embedding
  5. `POST /config/llm/reset` - 恢复 LLM 默认
  6. `POST /config/embedding/reset` - 恢复 Embedding 默认
- Pydantic 请求/响应模型定义

### 任务 3.3: 路由注册

- `api/routers/__init__.py` 导出 `config` 模块
- `api/main.py` 添加 `app.include_router(config.router, prefix="/api/v1", tags=["Config"])`

### 任务 3.4: 参数校验

- LLM: provider 存在于 Registry, temperature 0-2, top_p 0-1, max_tokens 1-131072
- Embedding: provider 存在于 Registry, mode in (local, api), local 模式需检查 models/ 目录
- 错误返回 HTTP 400 + 清晰消息

**验收标准**:
- 所有端点可通过 Postman 调用
- PUT 成功后 GET 返回更新值
- Reset 后 GET 返回系统默认值
- 无效参数返回 400 + 具体错误信息
- 连续切换 provider 不报错

**预估工时**: 1.5 天

---

## 5. 阶段 4: 前端

**目标**: 实现 Control Panel 模型配置面板

### 任务 4.1: API 客户端

- 新建 `src/lib/api/config.ts`
- 定义 TypeScript 接口: `ModelsConfig`, `AvailableModels`, `UpdateLLMPayload`, `UpdateEmbeddingPayload`, `ResetResponse`
- 实现 API 函数: `getModelsConfig()`, `getAvailableModels()`, `updateLLMConfig()`, `updateEmbeddingConfig()`, `resetLLMConfig()`, `resetEmbeddingConfig()`

### 任务 4.2: i18n 扩展

- 在 `src/lib/i18n/strings.ts` 追加模型配置相关字符串 (中英双语)
- 涵盖: 标题、标签、提示、确认对话框、成功/错误消息

### 任务 4.3: UI 组件开发

- 新建 `ModelComboBox` 组件: 输入框 + 预设下拉
- 新建 `SliderField` 组件: 标签 + Slider + 数值显示
- 新建 `ModelConfigPanel` 组件:
  - `LLMConfigCard`: Provider SegmentedControl + ModelComboBox + SliderField (temperature) + NumberInput (max_tokens) + SliderField (top_p)
  - `EmbeddingConfigCard`: Provider SegmentedControl + 条件显示 (mode/model) + 切换警告

### 任务 4.4: Control Panel 集成

- `control-panel.tsx` 类型变更: `ControlPanelTab` 加入 `"model"`
- 导航分组调整: model 从 DISABLED_ITEMS 移入 ACTIVE_ITEMS
- 渲染逻辑: `activeTab === "model"` 时渲染 `<ModelConfigPanel />`

### 任务 4.5: 样式

- `control-panel.css` 追加模型面板相关样式
- 涵盖: card header (含恢复默认按钮)、slider、number input、combo box、warning、readonly row

**验收标准**:
- 点击"模型"标签正常打开面板，无 "Coming soon" 标记
- LLM 配置: 可切换 provider、输入/选择模型名、调整参数，变更后自动保存
- Embedding 配置: 可切换 provider 和 mode，显示确认提示
- "恢复默认"按钮工作正常，表单回到系统默认值
- 中英文切换时所有文案正确
- 深色/浅色主题下样式正常

**预估工时**: 2 天

---

## 6. 阶段 5: Worker 同步与集成测试

**目标**: Celery Worker 感知配置变更，端到端测试

### 任务 5.1: Worker 配置同步

- 改造 `document_tasks.py` 的 `_get_embed_model()`:
  - 每次任务调用时检查 DB 中的 `embedding.provider`
  - 若 provider 变更，重建 `_EMBED_MODEL`
  - 添加同步 DB 读取辅助函数

**验收标准**:
- 通过 API 切换 Embedding 后，新提交的文档索引任务使用新 provider
- Worker 无需重启
- 不影响正在执行的任务 (仅影响后续任务)

### 任务 5.2: 集成测试

- 编写端到端测试:
  1. GET 初始配置 -> 返回系统默认值
  2. PUT LLM 配置 -> GET 返回更新值
  3. PUT Embedding 配置 -> GET 返回更新值，pgvector index 已重置
  4. POST reset -> GET 返回默认值
  5. 切换 Embedding 后上传文档 -> 文档使用新 provider 索引
- 测试 DB 查询异常降级

### 任务 5.3: index_dir 废弃标记

- `configs/embeddings.yaml` 中 `index_dir` 字段增加注释: `# [deprecated] 已废弃，pgvector 迁移后不再使用`
- `config.py` 中 `get_index_directory()` 函数增加 deprecation 日志警告

**验收标准**:
- 调用 `get_index_directory()` 时输出 deprecation 警告日志
- 不影响现有功能

**预估工时**: 1 天

---

## 7. 依赖关系图

```
任务 1.1 ──> 任务 1.2 ──> 任务 1.3
                              |
                              v
              任务 2.1 ──> 任务 2.2
                              |
              ┌───────────────┤
              v               v
          任务 3.1         任务 3.2 ──> 任务 3.3 ──> 任务 3.4
              |               |
              v               v
          任务 5.1         任务 4.1 ──> 任务 4.2 ──> 任务 4.3 ──> 任务 4.4 ──> 任务 4.5
              |                                                                   |
              v                                                                   v
          任务 5.2 <──────────────────────────────────────────────────────────────-┘
              |
              v
          任务 5.3
```

可并行的任务:
- 任务 2.1 和 任务 1.3 可部分并行
- 任务 3.1 和 任务 3.2 可并行
- 任务 4.1-4.5 (前端) 和 任务 5.1 (Worker) 可并行

---

## 8. 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Celery Worker 同步延迟 | 切换后短暂使用旧模型 | 中 | 按任务读取 DB，延迟仅为 DB 查询时间 |
| 用户输入不存在的模型名 | LLM API 调用失败 | 中 | 前端预设列表引导，API 失败时返回清晰错误 |
| 本地 Embedding 模型加载慢 | 切换到 local 模式卡顿 | 低 | 前端提示 "模型加载中"，异步加载 |
| 多浏览器并发修改配置 | DB 竞态 | 低 | 单用户场景，暂不处理并发 |
| pgvector Index 重置后首次查询慢 | 用户体验下降 | 低 | Index 重建为异步，首次查询自动触发 |

---

## 9. 不在本期范围内的工作

以下功能已识别但不在本期实施:

| 功能 | 原因 | 建议时间 |
|------|------|----------|
| OpenAI provider 支持 | 暂无 API Key 需求 | 后续有需求时添加 |
| Embedding 维度可配置 | 当前所有 provider 均 1024 | 引入非 1024 维度模型时 |
| 配置变更历史记录 | 单用户场景优先级低 | 多用户协作阶段 |
| `index_dir` 字段完全移除 | 存在测试引用，需谨慎 | 下一个清理批次 |
| YAML 配置文件的 Pydantic 验证 | 非阻塞，可渐进引入 | 后续批次 |
| RAG / MCP / Skills 面板 | 独立功能，独立设计 | 后续 batch |

---

## 10. 验收流程

最终验收需完成以下检查:

1. **冷启动**: 全新数据库，启动服务，GET `/config/models` 返回系统默认值
2. **LLM 切换**: 在前端切换 provider 到 zhipu，输入 glm-4.7-flash，确认对话功能正常
3. **LLM 自由输入**: 输入自定义模型名，确认保存并在配置中显示
4. **LLM 恢复默认**: 点击恢复默认，确认回到 qwen + qwen3.5-plus
5. **Embedding 切换**: 切换到 zhipu，确认弹出确认对话框，确认后新上传文档写入 zhipu 表
6. **Embedding 恢复默认**: 恢复默认，确认回到 qwen3-embedding + api + text-embedding-v4
7. **重启持久化**: 修改配置后重启服务，确认配置从 DB 加载
8. **Worker 同步**: 切换 Embedding 后不重启 Worker，验证新任务使用新配置
9. **主题兼容**: 深色/浅色主题下模型面板显示正常
10. **i18n**: 中英文切换后所有文案正确
