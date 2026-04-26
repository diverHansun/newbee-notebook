# Backend MinerU 3.0 GPU 模式优化方案（improve-3-gpu）

本文档目录记录 MinerU 3.0 在本项目 GPU 本地模式下的第三批优化方案。

本轮目标不是继续扩展默认云端 API 模式，也不是提前做多机多卡，而是聚焦于单用户、单机、单卡 NVIDIA GPU 场景下，让当前 `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` 这条链路与 MinerU 官方 3.x 本地能力更一致。

---

## 本轮目标

1. 明确区分云端 API 模式与本地 GPU 模式的能力边界。
2. 全面对齐官方本地支持集：
   - `PDF`
   - 图片
   - `DOCX`
   - `PPTX`
   - `XLSX`
3. 保持当前项目自己的 Celery 队列与任务编排，不引入 `mineru-router`。
4. 在单机单卡场景下修正 GPU compose、配置、converter、测试与文档的不一致。
5. 为后续实施准备清晰的范围文档与问题清单。

---

## 明确不做

本轮不进入以下范围：

- 不做多机多卡
- 不做 `mineru-router`
- 不接入官方 `/tasks` 异步任务接口替换现有 Celery 队列
- 不改造成多服务统一路由入口
- 不把本地能力扩到 `DOC`、`PPT`、`HTML`
- 不讨论 CPU 本地模式恢复

---

## 关键结论

### 1. 本地模式不应照搬云端 API 模式

云端 API 模式当前在仓库里已经支持：

- `PDF / DOC / DOCX / PPT / PPTX / HTML / 图片`

但本地 GPU 模式的目标应按官方本地支持集收口为：

- `PDF / image / DOCX / PPTX / XLSX`

因此 improve-3-gpu 的设计原则是：

- 本地模式只补齐官方明确支持的本地类型
- `DOC / PPT / HTML` 继续保留在云端链路或 fallback 链路
- 不对用户承诺“本地与云端完全同能力”

### 2. 当前 GPU 模式已经完成运行时升级，但能力面仍停留在 PDF

目前仓库已经完成的部分：

- GPU 镜像升级到适配 MinerU 3.x 的运行时
- `/health` 探针已经切换
- 本地 converter 已经接入 `parse_method / formula_enable / table_enable`

但当前本地 converter 仍只真正处理 PDF，因此“GPU 本地模式已适配 3.0”这句话只在运行时层面成立，在文件类型能力层面并不成立。

### 3. 本轮重点是“单机单卡稳定可用”

官方 3.x 同时提供了：

- 同步 `/file_parse`
- 异步 `/tasks`
- `mineru-router`
- `--enable-vlm-preload`

但对本项目而言，当前最稳妥的路径仍是：

- 继续让外层使用 Celery 队列
- Worker 调本地 `mineru-api`
- 优先走同步 `/file_parse`
- 先把单机单卡 GPU 模式做完整

---

## 文档索引

| 文件 | 内容 |
|---|---|
| [README.md](./README.md) | 本文档，目标、边界、关键结论与索引 |
| [01-change-overview.md](./01-change-overview.md) | 本轮优化总览、问题清单与优先级 |
| [02-official-local-baseline.md](./02-official-local-baseline.md) | 基于官方本地文档与本地源码的能力基线整理 |
| [03-current-gpu-gap-analysis.md](./03-current-gpu-gap-analysis.md) | 当前仓库 GPU 模式的缺口分析 |
| [04-adaptation-scope.md](./04-adaptation-scope.md) | 本轮实施范围、设计取舍与不做项 |
| [05-implementation-steps.md](./05-implementation-steps.md) | 建议实施顺序、测试重点与验收口径 |

---

## 主要依据

### 官方公开资料

- [MinerU 本地使用文档](https://opendatalab.github.io/MinerU/usage/quick_usage/)
- [MinerU Docker 部署文档](https://opendatalab.github.io/MinerU/quick_start/docker_deployment/)
- [MinerU API 文档](https://mineru.net/apiManage/docs)

### 已拉取到本地的 MinerU 源码资料

- `mineru/README.md`
- `mineru/README_zh-CN.md`
- `mineru/docs/zh/usage/quick_usage.md`
- `mineru/docs/zh/quick_start/docker_deployment.md`
- `mineru/docker/compose.yaml`

其中：

- 本轮 GPU 本地模式的主依据是本地使用文档与本地源码仓内容
- 云端 API 文档仅用于和当前默认模式做边界区分
- `mineru-router` 与 `/tasks` 虽然已经纳入官方本地能力，但本轮明确不做
