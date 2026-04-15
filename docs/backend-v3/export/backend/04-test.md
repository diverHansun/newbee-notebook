# 测试与验证策略

## 1. 测试范围

后端导出功能的测试分为三个层级：ExportService 单元测试、API 端点集成测试、边界条件验证。

## 2. ExportService 单元测试

### 2.1 测试策略

- mock 所有依赖的 Service（NotebookService、DocumentService、NoteService 等）
- 验证 ExportService 的编排逻辑、manifest 生成和 ZIP 输出

### 2.2 测试用例

| 测试项 | 输入 | 预期输出 |
|------|------|------|
| 全量导出 | types = 全部五种 | ZIP 包含 manifest.json 和 documents/、notes/、marks/、diagrams/、video-summaries/ 五个目录 |
| 选择性导出 | types = {"notes", "marks"} | ZIP 只包含 notes/ 和 marks/，manifest 中其他类型为空数组 |
| 空 Notebook | Notebook 无关联内容 | ZIP 包含 manifest.json（各列表为空），仍可正常解压 |
| 文件名格式 | 标题为 "荣格心理学" | 文件名为 `荣格心理学_{uuid}.md`，manifest.file 字段与之匹配 |
| 文件名安全 | 标题包含 `<>:"/\|?*` | 特殊字符被替换为下划线 |
| 文件名过长 | 标题超过 80 字符 | safe_title 截断至 80 字符 |
| 单条获取失败 | 某文档 get_content 抛异常 | 跳过该文档，ZIP 生成成功，包含 export-errors.txt，manifest 中不含该文档 |
| 全部获取失败 | 所有文档均抛异常 | ZIP 包含 export-errors.txt 和 manifest.json（documents 为空），无实际内容文件 |
| marks 导出格式 | Notebook 有多个书签 | marks/marks.json 为合法 JSON 数组，每项含 mark_id、anchor_text、document_id 等字段 |
| diagram 扩展名 | format 为 mermaid | 文件扩展名为 .mmd |
| diagram 扩展名 | format 为 reactflow_json | 文件扩展名为 .json |

### 2.3 manifest.json 验证

| 测试项 | 预期结果 |
|------|------|
| manifest 存在 | ZIP namelist 包含 "manifest.json" |
| version 字段 | 值为 "1.0" |
| exported_at | 为合法 ISO 8601 时间戳 |
| exporter | 值为 "newbee-notebook" |
| notebook 元信息 | title 和 description 与 NotebookService 返回值一致 |
| documents 列表 | 每项的 file 字段指向 ZIP 内实际存在的文件 |
| notes 关联 | 每个 note 的 document_ids 中的 ID 均出现在 documents 列表中（如 documents 也被导出） |
| sessions 字段 | 为空数组 |

### 2.4 ZIP 内容验证方式

使用 Python 标准库 `zipfile.ZipFile` 读取生成的 BytesIO，验证：
- `namelist()` 包含预期的文件路径
- manifest.json 可被 json.loads 解析且结构正确
- 对应文件的内容与 mock 数据一致
- UTF-8 编码正确

## 3. API 端点集成测试

### 3.1 测试策略

- 使用 httpx.AsyncClient + FastAPI TestClient
- mock ExportService 的 export_notebook 方法

### 3.2 测试用例

| 测试项 | 输入 | 预期结果 |
|------|------|------|
| 正常导出 | 有效 notebook_id，无 types 参数 | 200，Content-Type: application/zip，Content-Disposition 包含文件名 |
| 指定类型 | types=notes,marks | 200，ExportService 收到 {"notes", "marks"} |
| Notebook 不存在 | 无效 notebook_id | 404 |
| 非法类型 | types=notes,invalid | 422 |
| 空 types | types= (空字符串) | 200，导出全部类型 |

### 3.3 响应头验证

- Content-Type 为 application/zip
- Content-Disposition 为 attachment，filename 包含 notebook 标题和日期
- filename 中的非 ASCII 字符使用 RFC 5987 编码（filename*=UTF-8''...）

## 4. 边界条件

| 场景 | 验证方式 |
|------|------|
| 大量文档（50+） | 单元测试中 mock 生成 50 个文档，验证 ZIP 包含全部，manifest.documents 长度为 50 |
| 文档内容为空字符串 | 验证 ZIP 中对应文件存在但内容为空，manifest 中正常记录 |
| 笔记标题为空 | 验证文件名回退为 `untitled_{id}.md` |
| 视频总结未完成（status=processing） | 验证跳过该条目，记录到 export-errors.txt |

## 5. 不测试的内容

- 浏览器下载行为（前端职责）
- 各 Service 的内部实现正确性（各 Service 有各自的测试）
- ZIP 压缩算法的正确性（依赖 Python 标准库）
- 大文件场景的内存峰值（留待性能测试阶段）
- 导入功能对 manifest 的消费（属于导入模块的测试范围）
