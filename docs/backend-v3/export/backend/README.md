# 导出模块 -- 后端设计文档

## 模块定位

本目录描述 newbee-notebook 为 Notebook 归档导出功能新增的后端能力。核心任务是提供一个 API 端点，将指定 Notebook 关联的多种内容聚合为 ZIP 压缩包返回给前端，并通过 manifest.json 清单文件保证导出包是自描述的，可供后续导入功能消费。

Studio 内的即时单条导出（Video Summary MD、Note MD）完全在前端完成，不涉及后端改动。本文档只覆盖 Notebook 归档导出的后端部分。

## 当前结论

1. 新增一个 GET 端点 `/api/notebooks/{notebook_id}/export`，返回 ZIP 二进制流。
2. ZIP 根目录包含 manifest.json，描述包内全部内容及其关联关系。
3. ZIP 内容按类型分目录组织：documents/、notes/、marks/、diagrams/、video-summaries/，预留 sessions/ 目录。
4. 文件名格式为 `{safe_title}_{id}.{ext}`，保证可读性与唯一性。
5. 用户可通过查询参数 `types` 选择导出哪些类型，默认导出全部。
6. 打包过程在内存中完成（使用 Python zipfile 模块的 BytesIO 模式），ZIP 构造完成后以 StreamingResponse 返回。
7. 不新增数据库表，不新增持久化逻辑，所有数据经由已有的 Service 层方法获取。
8. 不导出 embedding 向量或 ES 索引数据。这些是可重建的派生数据。
9. 本版不实现 Session 会话导出和 Notebook 导入功能，但导出格式已为其预留扩展空间。
10. 后端导出 API 以单 Notebook 为粒度；前端多选导出时通过批量调用该端点实现。

## 与现有代码的真实边界

- NotebookDocumentService.list_documents 可获取 Notebook 关联的文档列表
- DocumentService.get_document_content 可获取文档解析后的 Markdown 内容
- NoteService.list_by_notebook 可获取 Notebook 下的笔记
- MarkService.list_by_notebook 可获取 Notebook 下的书签
- DiagramService.list_diagrams + get_diagram_content 可获取图表元信息和源码
- VideoService（通过现有 list 接口按 notebook_id 筛选）可获取视频总结
- NotebookService.get 可获取 Notebook 元信息（标题、描述）
- SessionService.list_by_notebook / list_messages / list_message_images 已存在（供后续 Session 导出使用）
- GeneratedImageService.get_binary 已存在（供后续 Session 图片导出使用）

以上 Service 方法均已存在，归档导出只需要编排调用顺序并将结果写入 ZIP。

## 设计原则

- 复用已有 Service 层，不绕过 Service 直接访问 Repository 或存储层。
- ZIP 打包在 Application 层完成，不污染 Domain 层。
- 导出格式面向 round-trip 设计：导出的 ZIP 包含足够信息，供后续导入功能重建完整 Notebook。
- 对于大型 Notebook，优先保证正确性，性能优化留待实际使用中发现瓶颈后再做。
- 单个导出请求的超时上限由 Web 服务器/反向代理控制，后端不做内部超时截断。

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [01-goals-duty.md](01-goals-duty.md) | 设计目标、职责边界、非目标 |
| 02 | [02-architecture.md](02-architecture.md) | 架构设计、ZIP 结构与 manifest 规范 |
| 03 | [03-dfd-interface.md](03-dfd-interface.md) | 数据流与 API 接口定义 |
| 04 | [04-test.md](04-test.md) | 测试与验证策略 |

## 与后续导入功能的关系

本版导出功能的格式设计已为后续导入做好准备：

- manifest.json 是导入程序的读取入口，包含完整的内容索引和关联关系
- 文件名中的 ID 用于包内互引用，导入时由系统生成新 ID 并建立 old_id -> new_id 映射
- 导入时文档写入 Library 并关联到新 Notebook 的 Sources，但不自动触发转换和 embedding/ES 流水线，由用户手动触发
- manifest.version 字段支持后续格式演进时做兼容处理
- sessions/ 目录预留给后续版本的会话导出，当前为空

导入功能的详细设计不在本文档范围内，将在独立的设计文档中描述。

## 关联文档

- 前端设计文档：[../frontend/README.md](../frontend/README.md)
