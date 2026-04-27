# 03 · 多文件共用 MinerU Batch

本文描述“用户一次选择多个文档后，后端如何让它们共用一个或多个 MinerU cloud batch”。

---

## 现状

当前多文件链路其实只完成了一半：

### 已经具备的部分

- 前端上传接口本身支持 `File[]`
  - [frontend/src/lib/api/documents.ts](../../../frontend/src/lib/api/documents.ts)
- 后端 Library 上传接口支持 `List[UploadFile]`
  - [documents.py](../../../newbee_notebook/api/routers/documents.py)

### 还缺失的部分

当文档被加入笔记本后，后端仍然是逐个文档入队：

- [notebook_document_service.py](../../../newbee_notebook/application/services/notebook_document_service.py)
- [document_tasks.py](../../../newbee_notebook/infrastructure/tasks/document_tasks.py)

也就是说：

- 用户可以一次选多个文件上传
- 但后续转换阶段并没有共享 batch

---

## 目标行为

### 用户视角

前端仍保持当前交互：

- 可单选
- 可多选
- 不新增新的“批处理模式”按钮

### 后端视角

对同一次“加入笔记本并触发处理”的文档集合，后端应：

1. 先判断哪些文档需要真正的 full pipeline
2. 再判断哪些 full pipeline 文档适合进入 MinerU cloud batch
3. 按官方限制与模型路由，把它们拆成一个或多个 batch
4. 每个 batch 只做一次申请上传链接与一次轮询
5. batch 处理完成后，再把每个文档各自接回现有索引链路

---

## 推荐实现

## 1. 新增独立的 cloud batch 处理服务

不要把“多文件 batch”硬塞进现有单文件 `MinerUCloudConverter.convert(file_path)` 语义里，而是新增一个独立的 batch 服务，例如：

- `mineru_cloud_batch_service.py`

它的职责应是：

- 接收多个 `document_id + local_path + file_name`
- 为每个文件生成 cloud 请求条目
- 一次请求 `file-urls/batch`
- 批量上传
- 轮询 batch 结果
- 按 `data_id` 或等价字段回填每个文档的结果

### 为什么要独立服务

当前单文件 converter 关注的是：

- 单文件 payload
- 单文件 zip 下载
- 单文件 markdown 结果

而 batch 服务关注的是：

- 多文件请求构造
- 结果映射
- 批间拆分
- 局部失败处理

这是两种不同职责，拆开更清晰。

---

## 2. 使用 `data_id=document_id` 做结果映射

官方 batch 返回中，最稳妥的映射键不是“列表顺序”，而是我们主动传进去的业务主键。

因此建议：

- 每个文件条目都带上 `data_id=document_id`

这样在 batch 轮询结果时，可以稳定地把：

- cloud 返回结果
- 本地数据库文档
- 最终存储路径

三者一一对应起来。

这也方便后续日志与失败重试。

---

## 3. 按路由类型分组

同一次用户操作中的文档，不一定能进入同一个 batch。

### 分组规则

建议至少按以下维度分组：

1. `html_batch`
   - 只包含 `.html/.htm`
   - 强制 `model_version=MinerU-HTML`
2. `default_batch`
   - 包含 `pdf/doc/docx/ppt/pptx/图片`
   - 使用默认 cloud 模型策略（`pipeline` / `vlm` / API 默认）

### 再按数量切片

每组内部再按 `50` 个文件切片。

例如用户一次选中：

- 64 个普通文档
- 3 个 HTML

则后端应生成：

- `default_batch_1`：50 个
- `default_batch_2`：14 个
- `html_batch_1`：3 个

---

## 4. 推荐的任务编排方式

### 推荐方案

新增一个 batch 转换任务，例如：

- `process_document_cloud_batch_task(document_ids: list[str])`

该任务只负责：

1. 读取文档与源文件
2. 做 batch 级 cloud 转换
3. 对成功结果落库存储
4. 对每个成功转换的文档，继续派发现有 `index_document_task`

### 不建议的方案

不建议让一个 batch 任务同时负责“共享 cloud 上传 + 所有文档后续索引”，因为：

- 任务会很长
- 局部失败补偿更复杂
- 不利于复用现有 indexing 任务与监控

因此建议复用现有链路：

- batch 任务负责“共享转换”
- 索引仍沿用单文档任务

---

## 5. 与 `NotebookDocumentService` 的衔接

当前 [NotebookDocumentService.add_documents](../../../newbee_notebook/application/services/notebook_document_service.py) 是逐个决定 action 并逐个入队。

建议改成：

1. 仍逐个创建 notebook-document 关联
2. 仍逐个判断 action：
   - `none`
   - `index_only`
   - `full_pipeline`
3. 将 `full_pipeline` 文档收集起来
4. 若当前运行模式为 `cloud`，则优先走新的 batch 分发逻辑
5. 只有不适合 batch 的文档，才回退到原有单文档 `process_document_task`

这样前端响应结构可以尽量保持不变，只是后台调度方式升级了。

---

## 6. fallback 文档如何处理

### 可以在 batch 之前就判定的

- 文件大小超过 `200 MB`
- PDF 页数超过 `200`

这些文档不应进入 cloud batch，而应直接走 fallback 处理。

### 不能提前判定的

例如 Office / HTML 的内部页数限制，可能只能在 cloud API 侧暴露出来。

本轮建议：

- 先尽量做本地预检
- 若 cloud 返回限制型错误，则该文档退出 batch 主路径
- 对文档类文件直接转入 MarkItDown fallback

### 图片的残余风险

图片虽然会纳入 cloud batch，但如果图片在 cloud 侧因限制或格式问题失败：

- 目前没有与 MarkItDown 等价的图片 OCR fallback
- 因此这类失败先按“清晰报错”处理，不伪装成完全可恢复

---

## 7. 可观测性

建议在 `processing_meta` 中记录 batch 相关元信息，例如：

- `queued_by=batch_cloud`
- `batch_route=html|default`
- `batch_group_id=<uuid>`
- `batch_size=<n>`

目的：

- 方便排查某个文档属于哪次 batch
- 便于后续观察 batch 命中率、失败率、fallback 比例

---

## 验收标准

完成本节实现后，应满足：

1. 用户多选文档加入笔记本时，cloud eligible 文档不再逐个申请上传链接
2. HTML 与非 HTML 不会被混进同一个模型路由组
3. 单组文件数超过 `50` 时能自动拆成多个 batch
4. 结果能稳定映射回各自 `document_id`
5. batch 成功转换后，现有索引任务仍能复用
6. 不适合 batch 的文档不会阻塞整次用户操作
