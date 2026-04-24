# Backend MinerU 3.0 优化方案（improve-2）

本目录记录 MinerU 3.0 在 **默认 API 模式** 下的第二批优化方案。本轮不再聚焦版本升级，而是补全当前 cloud 接入的能力边界，让默认 `docker compose up -d` 这条主路径与官方最新接口能力更接近。

---

## 本轮目标

1. 补全默认 cloud 模式支持的文件类型：
   - `pdf`
   - `doc` / `docx`
   - `ppt` / `pptx`
   - 常见静态图片
   - `html`
2. 对 `html` 做特殊路由：
   - 上传 cloud API 时强制使用 `model_version=MinerU-HTML`
   - 非 HTML 文件不误用 `MinerU-HTML`
3. 支持“多文件一次处理，共用一个 MinerU batch”：
   - 前端仍保持单选 / 多选文档的现有交互
   - 后端在同一次批处理里按官方限制聚合成一个或多个 cloud batch
4. 对官方限制补齐工程处理：
   - 文件大小超过 `200 MB`
   - PDF 页数超过 `200 页`
   - 超限后启动现有 fallback 链路（优先落回 MarkItDown）
5. 升级 smoke 验证与使用文档：
   - 更新 `quickstart.md`
   - 清理遗留脚本 `scripts/up-mineru.ps1`
   - 升级 MinerU cloud smoke 验证工具 / 测试

---

## 明确不做

- 不做 CPU 本地 MinerU 正式接入
- 不做 GPU 本地模式的文件类型扩展（下一批再讨论）
- 不做 KIE SDK 接入
- 不做大文件 / 大页数的主动切分上传，只做调查与边界记录
- 不改前端上传交互形态，只改后端编排与支持范围

---

## 关键约束

### 1. 官方 cloud 限制

依据 2026-04-24 查阅的官方页面：

- [MinerU API 文档](https://mineru.net/apiManage/docs)
- [MinerU API 限流说明](https://mineru.net/apiManage/limit)

当前需要按以下约束设计：

- 单文件大小上限：`200 MB`
- 单文件页数上限：`200 页`
- `file-urls/batch` 单次申请上传链接：按 `50` 个文件为安全上限

### 2. HTML 是单独路由

官方文档中的 HTML 能力依赖 `MinerU-HTML`。因此不能把 `model_version` 当作一个对所有文件一视同仁的全局常量；至少在实现层要按文件类型做解析。

### 3. 图片超限 fallback 不是完全闭环

当前仓库中的 MarkItDown fallback 能覆盖 `pdf/doc/docx/ppt/pptx/html` 这类文本/文档格式，但**并不直接处理图片 OCR**。因此：

- 文档类文件的超限 fallback 是明确可落地的
- 图片文件纳入 cloud 主路径没有问题
- 但“图片超限后完全等价回退”目前不是一条成熟能力，本轮会在文档和错误提示中明确说明这一点

这不是阻塞项，但需要诚实记录。

---

## 文档索引

| 文件 | 内容 |
|---|---|
| [README.md](./README.md) | 本文件，总览、目标、边界、文档索引 |
| [01-change-overview.md](./01-change-overview.md) | 本轮变更总览、官方依据、范围说明 |
| [02-cloud-api-expansion.md](./02-cloud-api-expansion.md) | 默认 cloud 模式扩容、HTML 特殊路由、超限 fallback 设计 |
| [03-batch-orchestration.md](./03-batch-orchestration.md) | 多文件共用 MinerU batch 的后端编排方案 |
| [04-smoke-and-docs.md](./04-smoke-and-docs.md) | smoke 工具升级、`quickstart.md` 与脚本文档整理 |
| [05-implementation-steps.md](./05-implementation-steps.md) | 实施顺序、测试范围、风险与回滚 |

---

## 官方资料来源

- [MinerU API 文档](https://mineru.net/apiManage/docs)
- [MinerU API 限流说明](https://mineru.net/apiManage/limit)
- [MinerU KIE SDK](https://mineru.net/apiManage/kie-sdk)
- [MinerU 本地 FastAPI Quick Usage](https://opendatalab.github.io/MinerU/usage/quick_usage/)

其中：

- `apiManage/docs` 是本轮默认 cloud 模式的主要依据
- `kie-sdk` 已确认不属于当前文档转 Markdown 主链路
- 本地 FastAPI 文档主要用于校对“GPU 本地模式未来能否扩展文件类型”，不作为本轮 cloud 方案的直接实现依据
