# 01 路线变更总览

本文汇总 improve-3-gpu 这一轮需要解决的问题、目标修改点与优先级。

---

## 变更总览表

| # | 变更区域 | 目标文件 | 变更类型 | 优先级 |
|---|---|---|---|---|
| 1 | 本地文件类型支持 | `mineru_local_converter.py`、`processor.py` | 从仅 PDF 扩展到官方本地支持集 | 高 |
| 2 | 本地请求构造 | `mineru_local_converter.py` | 区分 PDF 与非 PDF 的请求参数和 MIME | 高 |
| 3 | GPU compose 一致性 | `docker-compose.gpu.yml` | 修正 `MINERU_BACKEND`、依赖关系、启动时序 | 高 |
| 4 | 本地配置层 | `document_processing.yaml` | 保持本地默认后端与 GPU 模式一致 | 高 |
| 5 | 单元测试 | `tests/unit/infrastructure/document_processing/` | 覆盖 DOCX/PPTX/XLSX/图片 的本地路径 | 高 |
| 6 | smoke / compose 测试 | `tests/smoke/` | 覆盖 GPU override 的关键断言 | 中 |
| 7 | 文档说明 | `quickstart.md` | 重写 GPU 模式说明，明确能力边界 | 中 |
| 8 | 配置面板增强 | `config.py`、前端 panel | 是否开放 backend/parse_method 等可调项 | 低，本轮可不做 |

---

## 当前问题清单

### 问题 1：本地 converter 仍然只支持 PDF

当前 `MinerULocalConverter` 的 `can_handle()` 只接受 `.pdf`，并且上传时 MIME 写死为 `application/pdf`。

这带来的直接结果是：

- GPU 本地模式目前真正能走本地 MinerU 的只有 PDF
- `DOCX / PPTX / XLSX / 图片` 即使官方支持，本仓库也不会走本地链路

这是本轮最核心的问题。

### 问题 2：本地请求实现带着明显的 PDF 专属假设

当前本地请求实现无条件携带：

- `start_page_id`
- `end_page_id`

并且整个 converter 的批处理逻辑建立在“按页切分 PDF”上。

这个思路适合 PDF，但不适合：

- 图片
- `DOCX`
- `PPTX`
- `XLSX`

因此本轮需要把本地 converter 拆成：

- PDF 路径：保留分页与批量处理能力
- 非 PDF 路径：单请求直接上传，不套用 PDF 分页参数

### 问题 3：GPU compose 的 backend 配置不一致

当前 GPU override 中：

- `celery-worker` 显式写了 `MINERU_BACKEND=hybrid-auto-engine`
- `api` 没有显式写
- 而默认配置文件里 `MINERU_BACKEND` 的默认值仍是 `pipeline`

这意味着：

- Worker 处理文档时大概率走 GPU 路径
- API 进程或宿主机调试路径可能仍会回到 `pipeline`

这会造成“同样是 local 模式，不同入口行为不一致”的问题。

### 问题 4：GPU 栈缺少对 mineru-api ready 状态的明确依赖

GPU 覆盖栈虽然新增了 `mineru-api`，但 `api` / `celery-worker` 当前没有基于其健康状态的显式依赖。

在以下场景下会放大问题：

- 首次启动下载模型
- 本地 `mineru-api` 启动较慢
- 容器刚起来就立即触发转换任务

这会使前几次任务更容易因为服务未 ready 而失败。

### 问题 5：文档里对 GPU 模式的表述仍偏旧

当前 `quickstart.md` 对 GPU 模式的描述仍更偏向“运行时升级完成”，但没有完整反映：

- 本地只应支持官方本地支持集
- 当前仓库尚未补齐 `DOCX / PPTX / XLSX / 图片`
- 单机单卡与多机多卡的边界
- 我们继续使用 Celery，而不是切到 `mineru-router` / `/tasks`

### 问题 6：测试覆盖明显不足

目前本地单测主要验证：

- PDF 请求字段
- 3.0 新增的几个 form 参数

但缺少这些关键断言：

- 本地 `DOCX / PPTX / XLSX / 图片` 是否会路由到 `MinerULocalConverter`
- 非 PDF 本地请求是否不会携带分页参数
- GPU compose 是否对 `api` / `worker` 使用一致 backend
- GPU compose 是否建立了对 `mineru-api` 的合理依赖

---

## 本轮总体结论

improve-3-gpu 本质上不是“再升级一个版本号”，而是要把 GPU 本地模式从“运行时已经升到 3.x，但能力仍偏 PDF”推进到“单机单卡下可稳定覆盖官方本地支持集”。

因此本轮优先级排序应为：

1. 本地类型支持与请求构造
2. GPU compose 与配置一致性
3. 测试补齐
4. 文档更新

而不是先做：

- `mineru-router`
- `/tasks`
- 多机多卡
- 配置面板高级参数开放
