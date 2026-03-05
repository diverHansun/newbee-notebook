# 第一批：基础设施层

本批次包含 4 个模块，均无外部依赖，可独立实施或并行推进。

---

## 模块 1: MinerU docx 处理扩展

### 目标

让 MinerU Cloud 转换链支持 Office 文档格式 (.doc / .docx / .ppt / .pptx)，扩展文档处理能力覆盖面。

### 职责

- 扩展 `MinerUCloudConverter` 的格式识别范围
- 保持转换链逻辑不变 (MinerUCloud -> MarkItDown fallback)
- 确保 Office 格式在 Cloud 模式下走 MinerU，在 Local 模式下走 MarkItDown

### 非职责

- 不改动转换链架构或 fallback 机制
- 不涉及 Local Docker 服务的 Office 支持 (服务端本身不支持)

### 改动范围

仅 `mineru_cloud_converter.py` 的 `can_handle()` 方法及相关格式常量。

### 已有设计文档

详见 `docs/backend-v2/minerU-cloud/03-docx-extension.md`

---

## 模块 2: LLM / Embedding 模型配置验证

### 目标

确认现有的 YAML 配置 + Provider Registry 机制是否满足模型切换需求。若满足则无需改动；若需运行时热切换，再补充 Admin API。

### 职责

- 验证当前 `configs/llm.yaml` 和 `configs/embeddings.yaml` 的切换流程
- 确认 Registry 初始化时机 (是否需要重启)
- 若需要运行时切换，设计 Admin API 端点

### 非职责

- 不更换配置格式 (YAML 已满足需求)
- 不改动 Provider Registry 架构

### 当前状态

已有完整的多 Provider 支持：
- LLM: Qwen / ZhipuAI / OpenAI，通过 `configs/llm.yaml` 的 `provider` 字段选择
- Embedding: Qwen3-Embedding / ZhipuAI，通过 `configs/embeddings.yaml` 的 `provider` 字段选择
- 环境变量可覆盖 YAML 配置

### 预期结论

大概率无需改动，仅做验证和文档补充。

---

## 模块 3: Markdown 文档 TOC 侧栏导航

### 目标

为文档阅读器提供基于 Markdown 标题结构的目录 (Table of Contents) 侧栏导航，支持快速定位和滚动跟随高亮，提升长文档的阅读体验。

### 设计决策

原方案为基于 PDF `page_idx` 的分页系统。经分析后改为 TOC 导航方案，理由如下:

1. **覆盖面**: TOC 适用于所有文档格式 (PDF / DOCX / XLSX 等)，而 `page_idx` 仅存在于 MinerU 处理的 PDF
2. **语义导航 > 物理翻页**: 用户在 Markdown 中按章节结构定位比按 PDF 物理页码更自然
3. **实现成本**: 纯前端方案，无需新增后端 API 或数据库存储
4. **技术基础**: 现有 Markdown 管线已集成 `rehype-slug`，所有标题元素均已生成锚点 `id`

### 职责

**纯前端实现**:
- 从 Markdown 源码提取标题层级，生成完整 TOC 数据结构
- 在文档阅读器 Main 面板内实现可折叠的 TOC 侧栏
- 点击 TOC 条目滚动到对应标题位置
- 滚动内容时高亮当前可见标题对应的 TOC 条目
- 兼容现有的 chunk 懒加载机制

### 非职责

- 不改动后端 API 或数据模型
- 不改动 Markdown 渲染管线 (remark/rehype 插件链)
- 不改动全局三栏布局 (Sources / Main / Studio)

### 已有设计文档

详见 `docs/backend-v2/batch-1/toc-sidebar/`

---

## 模块 4: MinIO 对象存储迁移

### 目标

将文档存储从本地 Bind Mount (`data/documents/`) 迁移到 MinIO 对象存储，消除 FastAPI 作为文件代理的性能瓶颈。

### 职责

- 实现 StorageBackend 抽象层 (LocalStorage / MinIOStorage)
- Docker Compose 集成 MinIO 服务
- Celery Worker 使用 StorageBackend API 存取文件
- ContentService 实现 Markdown 中图片路径替换为 Presigned URL
- 数据迁移工具和回退机制

### 非职责

- 不改动文档处理逻辑 (MinerU 转换链)
- 不改动前端渲染逻辑 (Presigned URL 对前端透明)

### 实施策略

按已有设计文档的 5 阶段执行：
1. Phase 0: StorageBackend 抽象层
2. Phase 1: MinIO Docker 集成
3. Phase 2: Celery Worker 适配
4. Phase 3: ContentService 路径替换
5. Phase 4: 数据迁移与切换

通过环境变量 `STORAGE_BACKEND=local` 可随时回退到本地存储。

### 已有设计文档

详见 `docs/backend-v2/MinIO/` 下的 5 份设计文档。
