# 架构设计与模块结构

## 1. 总体架构

归档导出不构成独立的领域模块，而是作为 Application 层的一个编排服务存在。它不拥有自己的 Repository 或 Domain Entity，仅组合调用已有 Service 获取数据，构建 manifest.json，并将内容写入 ZIP。

```
API 层
  └── routers/export.py          -- 路由端点，参数校验，响应构造

Application 层
  └── services/export_service.py -- 编排逻辑，manifest 构建，ZIP 打包

已有 Service（被调用方）
  ├── NotebookService            -- Notebook 元信息
  ├── NotebookDocumentService    -- 文档列表
  ├── DocumentService            -- 文档 Markdown 内容与元数据
  ├── NoteService                -- 笔记列表和内容
  ├── MarkService                -- 书签列表
  ├── DiagramService             -- 图表列表和源码
  └── VideoService               -- 视频总结列表和内容
```

## 2. 设计模式与理由

### 2.1 服务编排模式

ExportService 是一个纯编排者，不包含业务规则。它的职责是：
1. 获取 Notebook 元信息
2. 根据 types 参数决定要调用哪些 Service
3. 依次获取数据，同步构建 manifest 数据结构
4. 将文本内容写入 ZIP
5. 将 manifest.json 写入 ZIP 根目录

选择编排模式的原因：导出逻辑本身是"取数据 + 组织结构 + 打包"，不存在需要协调的事务或复杂的状态转换，使用一个平铺的 async 方法即可。

### 2.2 不使用后台任务队列

初版不引入 Celery 或类似的任务队列。原因：
- Notebook 关联的内容数量通常在百级以下，聚合耗时在秒级
- 文档 Markdown 已经存在于 MinIO，Service 层的 get_document_content 只是一次对象存储读取
- 引入任务队列需要额外的基础设施（Redis/RabbitMQ），增加部署复杂度

如果后续出现超大 Notebook（关联数百个文档）导致请求超时，可以在那时引入异步任务 + 轮询/WebSocket 通知机制。

## 3. 模块结构与文件组织

### 3.1 新增文件

```
newbee_notebook/
  api/
    routers/
      export.py              -- 新增，导出路由
  application/
    services/
      export_service.py      -- 新增，导出编排服务
```

### 3.2 修改文件

```
newbee_notebook/
  api/
    routers/__init__.py      -- 注册 export router
  configs/
    di.py (或等效文件)        -- 注册 ExportService 的依赖
```

### 3.3 不修改的文件

- Domain 层：不新增 Entity、Repository 接口
- Infrastructure 层：不新增存储后端或外部服务集成
- 已有 Service 层：不修改现有 Service 的接口签名

## 4. ZIP 包结构

### 4.1 目录布局

```
{notebook_title}-export-{YYYY-MM-DD}.zip
│
├── manifest.json                                  -- 包内容清单与关联关系
│
├── documents/
│   ├── {safe_title}_{document_id}.md              -- 解析后的文档 Markdown
│   └── ...
│
├── notes/
│   ├── {safe_title}_{note_id}.md                  -- 笔记内容
│   └── ...
│
├── marks/
│   └── marks.json                                 -- 全部书签的结构化数据
│
├── diagrams/
│   ├── {safe_title}_{diagram_id}.mmd              -- Mermaid 格式图表
│   ├── {safe_title}_{diagram_id}.json             -- ReactFlow JSON 格式图表
│   └── ...
│
├── video-summaries/
│   ├── {safe_title}_{summary_id}.md               -- 视频总结 Markdown
│   └── ...
│
├── sessions/                                      -- 本版预留，不写入内容
│
└── export-errors.txt                              -- 仅在有条目获取失败时生成
```

### 4.2 manifest.json 规范

manifest.json 是整个 ZIP 包的索引，也是后续导入功能的唯一入口。导入程序通过解析 manifest 即可了解包内全部内容、格式和关联关系。

```json
{
  "version": "1.0",
  "exported_at": "2026-04-14T20:53:00Z",
  "exporter": "newbee-notebook",
  "notebook": {
    "title": "我的笔记本",
    "description": "读书"
  },
  "documents": [
    {
      "document_id": "uuid-1",
      "title": "荣格心理学入门",
      "content_type": "pdf",
      "page_count": 256,
      "chunk_count": 142,
      "file": "documents/荣格心理学入门_uuid-1.md"
    }
  ],
  "notes": [
    {
      "note_id": "uuid-2",
      "title": "卡尔·荣格的主要心理学理论",
      "file": "notes/卡尔·荣格的主要心理学理论_uuid-2.md",
      "document_ids": ["uuid-1"],
      "mark_ids": ["uuid-m1"]
    }
  ],
  "marks": {
    "file": "marks/marks.json",
    "count": 5
  },
  "diagrams": [
    {
      "diagram_id": "uuid-3",
      "title": "心理学流派关系图",
      "diagram_type": "concept_map",
      "format": "mermaid",
      "file": "diagrams/心理学流派关系图_uuid-3.mmd",
      "document_ids": ["uuid-1"]
    }
  ],
  "video_summaries": [
    {
      "summary_id": "uuid-4",
      "title": "台湾旅行vlog",
      "platform": "bilibili",
      "video_id": "BV1RvDjBcEX6",
      "file": "video-summaries/台湾旅行vlog_uuid-4.md"
    }
  ],
  "sessions": []
}
```

### 4.3 manifest 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| version | string | manifest 格式版本，当前为 "1.0"。后续格式变更时递增，导入程序据此做兼容 |
| exported_at | string (ISO 8601) | 导出时间戳 |
| exporter | string | 导出程序标识，固定为 "newbee-notebook" |
| notebook | object | Notebook 元信息：title、description |
| documents[].document_id | string | 包内引用 ID。导入时生成新 ID，建立 old -> new 映射 |
| documents[].content_type | string | 原始文档格式（pdf/docx/epub 等），导入时用于创建 Document 记录 |
| documents[].page_count | int | 页数，导入时直接写入记录 |
| documents[].chunk_count | int | chunk 数，导入时作参考（重新 embedding 后可能变化） |
| documents[].file | string | ZIP 内的相对路径 |
| notes[].document_ids | list[string] | 关联的文档 ID（引用 documents 中的 document_id） |
| notes[].mark_ids | list[string] | 引用的书签 ID（引用 marks 中的 mark_id） |
| diagrams[].format | string | "mermaid" 或 "reactflow_json"，决定文件扩展名和导入时的解析方式 |
| sessions | list | 本版为空数组，预留给后续会话导出 |

### 4.4 文件名规则

文件名格式：`{safe_title}_{id}.{ext}`

safe_title 处理规则：
1. 将 `< > : " / \ | ? *` 替换为下划线
2. 截断至 80 字符（避免路径过长）
3. 去除首尾空白
4. 空字符串回退为 "untitled"

重名处理：由于文件名包含 ID 后缀，不会产生重名。

### 4.5 目录与内容格式汇总

| 目录 | 内容 | 文件格式 | 数据来源 |
|------|------|------|------|
| documents/ | 解析后的文档 | .md | DocumentService.get_document_content |
| notes/ | 笔记 | .md | Note.content |
| marks/ | 书签 | .json | MarkService.list_by_notebook，JSON 数组，每项含 mark_id、anchor_text、context_text、char_offset、document_id |
| diagrams/ | 图表源码 | .mmd 或 .json | DiagramService.get_diagram_content |
| video-summaries/ | 视频总结 | .md | VideoSummary.summary_content |
| sessions/ | 会话消息与图片 | 本版为空 | 预留 |

## 5. 不导出的数据

| 数据类型 | 不导出原因 |
|------|------|
| 原始文档文件（PDF/DOCX/EPUB） | 体积大，且已有解析后的 Markdown 可供阅读和导入 |
| embedding 向量 | 与具体 embedding model 绑定，跨版本不兼容；可从 Markdown 重建 |
| ES 索引数据 | 运行时产物，依赖 ES 配置；可从 Markdown 重建 |
| chunk 分片数据 | embedding 的中间产物，重新 embedding 时会重新生成 |

导入时，文档写入 Library 后处于"已转换但未处理"状态（有 Markdown 内容但无向量/索引），用户可在 Sources 面板中手动触发 embedding + ES 流水线。

## 6. 约束与权衡

### 内存模式 vs 流式写入

ZIP 构造使用 `zipfile.ZipFile(BytesIO(), "w", zipfile.ZIP_DEFLATED)`，即先在内存中构造完整 ZIP，再通过 StreamingResponse 返回。

放弃的方案：使用 `zipstream` 等库做真正的边构造边发送。原因是 Python 标准库的 zipfile 不支持流式写入，第三方库维护状态不确定，且初版场景下 Notebook 的总数据量通常不超过几十 MB，内存模式完全可行。

如果后续出现 ZIP 超过 100MB 的场景，可以考虑：
1. 切换为服务端临时文件 + FileResponse
2. 引入流式 ZIP 库
3. 对文档内容做分页获取而非一次全量加载

### 书签导出为 JSON 而非 Markdown

书签（Mark）的核心数据是结构化的（mark_id + anchor_text + char_offset + context_text + document_id），导出为 JSON 的理由：
- 保留了完整的结构化信息，导入时可以精确重建
- document_id 引用关系在 JSON 中清晰表达
- char_offset 等定位信息在 Markdown 格式中无自然表达方式

### 图表导出源码而非 PNG

图表的 PNG 渲染依赖浏览器 DOM 环境（ReactFlow 需要节点布局，Mermaid 需要 SVG 渲染器），在后端做 PNG 生成需要 headless browser，复杂度过高。导出源码（Mermaid 文本或 ReactFlow JSON）的优势：
- 导入时可直接重建图表
- 用户可用其他 Mermaid 工具重新渲染
- 体积远小于 PNG

### manifest 中使用包内 ID 而非全局 ID

manifest 中的 document_id、note_id 等来自导出时刻的系统 ID，仅用于包内互相引用（如 note.document_ids 指向 documents 列表中的条目）。导入时系统必须为所有内容生成新 ID，通过 old_id -> new_id 映射表重建关联关系。这保证同一个 ZIP 可以在同一系统中重复导入而不产生 ID 冲突。
