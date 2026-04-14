# 导出模块 -- 前端设计文档

## 模块定位

本目录描述 newbee-notebook 导出功能的前端设计。导出分为两个层级：

1. Studio 内的即时单条导出 -- 用户在 Studio 中浏览某条内容时，一键下载为文件。
2. Settings 数据面板的 Notebook 归档导出 -- 用户在控制面板中选择一个 Notebook，将其全部或部分内容作为 ZIP 压缩包下载。

两个层级各自独立，不共享组件，但遵循一致的交互语言（icon、触发方式、文件格式）。

## 当前结论

1. Studio 即时导出覆盖三种内容：Diagram（PNG，已实现）、Video Summary（MD，待实现）、Note（MD，待实现）。
2. 即时导出使用纯 icon 按钮（向下箭头 SVG），不带文字，放在内容卡片区域内。
3. Settings 数据面板从当前的"笔记导出"重构为"Notebook 归档导出"，围绕 Notebook 而非 Note 设计。
4. 归档导出通过后端 API 生成 ZIP 压缩包（包含 manifest.json），前端负责选择 Notebook、选择导出内容类型、触发下载和进度展示。
5. 现有 notes-export-panel.tsx 重构为 notebook-export-panel.tsx。单条笔记导出功能迁移至 Studio Note detail 视图。

## 与现有代码的真实差距

- video-detail.tsx 没有任何导出按钮。
- studio-panel.tsx 的 renderNoteDetail 没有单条导出按钮。
- notes-export-panel.tsx 目前围绕全局笔记列表设计，不支持按 Notebook 维度操作。
- 前端没有调用后端 ZIP 导出 API 的逻辑（该 API 尚不存在）。
- uiStrings 中缺少导出相关的 i18n key。

## 设计原则

- Studio 即时导出完全在前端完成，不依赖后端新接口。
- Notebook 归档导出依赖后端打包能力，前端只负责触发和下载。
- 不为导出功能引入新的全局状态管理或 Context。
- 导出按钮样式在三个 Studio 子模块间保持一致。

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [01-goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| 02 | [02-architecture.md](02-architecture.md) | 组件结构与状态设计 |
| 03 | [03-dfd-interface.md](03-dfd-interface.md) | 数据流、接口与事件约定 |
| 04 | [04-test.md](04-test.md) | 测试策略 |

## 与后续导入功能的关系

本版的导出功能产出包含 manifest.json 的 ZIP 包，后续的导入功能将消费该格式。导入功能在前端的关键交互点：

- Notebook 列表页面底栏新增"导入 Notebook"按钮
- 支持两种上传方式：选择 ZIP 文件或选择文件夹（文件夹由前端 JSZip 打包后上传）
- 上传后先展示导入预览（由后端校验 manifest 返回），用户确认后执行导入
- 导入的文档写入 Library 并关联到新 Notebook 的 Sources，但不自动触发 embedding/ES 流水线，由用户在 Sources 面板中手动触发

导入功能的实现不在本版范围内，将在独立设计文档中描述。

## 关联文档

- 后端设计文档：[../backend/README.md](../backend/README.md)
