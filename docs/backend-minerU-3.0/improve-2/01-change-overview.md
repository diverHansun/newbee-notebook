# 01 · 变更概览

本文列出 improve-2 的核心变更、涉及文件和设计取舍，供后续实施与 review 使用。

---

## 变更汇总表

| # | 变更域 | 目标文件 | 变更类型 | 紧迫度 |
|---|---|---|---|---|
| 1 | 上传类型支持 | `document_type.py`、`local_storage.py` | 扩展支持的文件扩展名与文档类型映射 | 高 |
| 2 | Cloud 转换器 | `mineru_cloud_converter.py` | 扩展文件类型、HTML 特殊路由、超限预检 | 高 |
| 3 | Cloud 批处理编排 | 新增 cloud batch 服务 / 任务 + `notebook_document_service.py` | 多文件共用一个或多个 MinerU batch | 高 |
| 4 | 任务调度 | `document_tasks.py` | 新增 cloud batch 处理任务，复用现有索引任务 | 高 |
| 5 | Fallback 语义 | `processor.py` 或批处理服务 | 对超限文档落回现有 fallback 链路 | 中 |
| 6 | smoke 验证 | `scripts/mineru_v4_smoke_test.py` 或等价 smoke 工具 | 支持更多文件类型与多文件 batch | 中 |
| 7 | 文档与脚本 | `quickstart.md`、`scripts/README.md`、删除 `up-mineru.ps1` | 说明与实际能力对齐 | 中 |
| 8 | 测试 | `newbee_notebook/tests/` | 单元测试 + smoke 测试补齐 | 高 |

---

## 官方依据

### 1. 默认 cloud 模式的主要接口

基于 [MinerU API 文档](https://mineru.net/apiManage/docs)，当前默认 API 模式应继续使用：

- `POST /api/v4/file-urls/batch`
- `GET /api/v4/extract-results/batch/{batch_id}`

也就是说，本轮不是切换协议，而是把当前“单文件 batch 调用”扩展成“真 batch 调用”。

### 2. 官方支持的 cloud 文件范围

按 2026-04-24 的官方文档解读，默认 cloud 精准解析能力已覆盖：

- `pdf`
- `doc` / `docx`
- `ppt` / `pptx`
- 图片
- `html`

其中 HTML 需要走 `MinerU-HTML` 路由。

### 3. 官方 batch 限制

按 [限流说明](https://mineru.net/apiManage/limit) 和 API 页面说明：

- 单文件大小限制：`200 MB`
- 单文件页数限制：`200 页`
- `file-urls/batch` 单次申请链接按 `50` 个文件为安全上限

因此“用户一次选中很多文档”并不意味着后端只会产生一个 batch；更准确的说法是：

- 同一次用户操作会被尽量聚合成若干个 batch
- 每个 batch 不超过官方安全上限

### 4. KIE SDK 不在本轮范围内

[KIE SDK](https://mineru.net/apiManage/kie-sdk) 需要 `pipeline_id`，语义是 parse / split / extract，并不是当前文档转 Markdown 主链路的替代物。本轮明确不接入。

---

## 设计结论

### 结论 1 · 默认 cloud 模式要做“能力补齐”，不是“链路重写”

当前仓库已经用了正确的官方 v4 async 链路，只是能力还停留在：

- 文件类型偏少
- 仍按单文件使用 batch 接口
- 没有把 HTML 路由和官方限制工程化

所以实现重点应放在“扩展”和“编排”，而不是推倒重来。

### 结论 2 · HTML 必须单独分组

如果一次用户操作里同时出现：

- `a.pdf`
- `b.docx`
- `c.html`

那么后端不能把它们全部放进同一个请求体并使用同一个 `model_version`。设计上必须至少拆成：

- 文档类 batch：按默认 cloud 模型策略处理
- HTML batch：强制 `model_version=MinerU-HTML`

### 结论 3 · 超限 fallback 先做“保守可用”，不做“主动切分”

面对官方从更高页数能力收紧到 `200 页` 的情况，本轮设计采用：

- 大小 / 页数可预检时，直接触发 fallback
- 无法预检的场景，接到官方限制报错后再 fallback
- 不主动拆分 PDF / Office / HTML 再上传

原因是主动切分会明显放大本轮实现复杂度，特别是多文件 batch 与切分叠加后，状态管理会变得很重。

### 结论 4 · 图片支持要诚实标注残余风险

图片会纳入默认 cloud 支持范围，但如果未来出现“图片超限或 cloud 拒绝”的边界情况：

- 当前仓库并没有和 MarkItDown 对等的本地图片 OCR fallback
- 因此这部分只能先以“主路径支持 + 边界清晰报错”为主

这不影响本轮推进，但需要在文档中写清楚，避免把“图片支持”误说成“图片全链路容灾完备”。
