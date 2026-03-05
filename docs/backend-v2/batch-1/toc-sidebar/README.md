# Markdown TOC 侧栏导航方案

## 1. 背景

在 backend-v1 阶段，文档阅读器 (`DocumentReader`) 以全量 Markdown 连续滚动的方式渲染文档内容，配合 chunk 懒加载优化大文档的首屏性能。但对于数百页的长文档，用户缺乏快速定位到特定章节的手段，只能通过手动滚动逐步查找。

原 batch-1 模块 3 规划了基于 PDF `page_idx` 的分页系统。经过详细分析，该方案存在以下根本缺陷:

1. **覆盖面不足**: `page_idx` 仅存在于 MinerU 处理的 PDF，MarkItDown 处理的 DOCX / XLSX / PPTX 无此数据，导致两套不同的阅读体验
2. **语义割裂**: PDF 物理页码对应的是排版边界而非内容结构，一个段落或表格可能跨页，按页截断会破坏阅读连贯性
3. **实现代价高**: 需要后端新增 API、数据库持久化页码映射、前端重写渲染流程

本方案改为 **TOC (目录) 侧栏导航**，利用 Markdown 标题的语义结构，为所有格式的文档提供统一的章节导航体验。

## 2. 设计原则

1. **纯前端实现**: 不新增后端 API，不修改数据模型，所有逻辑在前端完成。
2. **格式无关**: 对所有可渲染为 Markdown 的文档统一适用，不区分原始格式。
3. **最小侵入**: 不改动现有 Markdown 渲染管线 (`remark/rehype` 插件链)，不改动全局三栏布局。
4. **利用已有基础**: `rehype-slug` 已为所有标题生成锚点 `id`，TOC 跳转可直接复用。
5. **兼容懒加载**: 与现有 chunk 分段加载机制协同工作，未加载的章节在点击后按需展开。

## 3. 核心决策

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 导航方式 | TOC 侧栏 (弃用 PDF 分页) | 覆盖所有格式、语义导航更自然、纯前端实现 |
| TOC 放置位置 | DocumentReader 内部左侧可折叠侧栏 | 自包含于阅读组件，不影响全局布局 |
| Toggle 按钮位置 | Reader header 右侧，替代原 status badge | Status badge 与 Sources 面板重复，移除后释放位置给 TOC 按钮 |
| 标题提取方式 | Markdown 源码正则提取 | 可一次性获取完整标题列表，不受 chunk 懒加载限制 |
| 锚点 ID 生成 | 复用 rehype-slug 的 slugify 算法 | 确保 TOC 点击目标与渲染结果一致 |
| 滚动高亮机制 | IntersectionObserver 监听标题元素 | 性能优于 scroll 事件监听，与现有懒加载模式一致 |
| 默认展开状态 | 有标题时默认展开，无标题时隐藏 | 大多数文档有标题结构，默认提供导航价值 |
| TOC 侧栏宽度 | 固定 220px | 足够显示中文章节标题，不过度压缩内容区 |

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-current-analysis.md](./01-current-analysis.md) | 现状分析: 当前阅读器布局、渲染管线、懒加载机制的完整梳理 |
| 02 | [02-component-design.md](./02-component-design.md) | 组件设计: TOC 组件结构、布局方案、交互行为、样式规范 |
| 03 | [03-implementation-plan.md](./03-implementation-plan.md) | 实施计划: 分步任务拆解、验收标准 |

## 5. 与现有文档的关系

- **backend-v2/original/01-batch1-infrastructure.md**: 批次一模块 3 "Markdown 文档 TOC 侧栏导航"，本方案是该模块的详细设计
- **前端 document-reader.tsx**: 主要改动文件，在其内部新增 TOC 侧栏和 toggle 控制
- **前端 markdown-viewer.tsx**: 不改动，但 TOC 需要与其 chunk 懒加载机制协同
- **前端 markdown-pipeline.ts**: 不改动，复用其 `rehype-slug` 生成的标题锚点 ID

## 6. 当前状态

- 文档状态: 设计评审中，待确认后进入实施阶段
