# 02 官方本地能力基线

本文用于明确 MinerU 官方 3.x 本地能力的基线，避免把云端 API 能力误投射到本地 GPU 模式。

---

## 基线结论

基于以下资料：

- `mineru/README.md`
- `mineru/README_zh-CN.md`
- `mineru/docs/zh/usage/quick_usage.md`
- `mineru/docs/zh/quick_start/docker_deployment.md`
- `mineru/docker/compose.yaml`

可以得到本轮最重要的基线结论：

### 1. 官方本地支持集

官方本地模式当前支持：

- `PDF`
- 图片
- `DOCX`
- `PPTX`
- `XLSX`

这也是本轮 GPU 本地适配应对齐的上限。

### 2. 官方本地服务形态

官方本地 3.x 已提供多种入口：

- `mineru-api`
- `mineru-router`
- `mineru-gradio`
- `mineru-openai-server`
- CLI

其中和我们当前项目直接相关的是：

- `mineru-api`
- `mineru-router`

### 3. 官方本地接口形态

官方本地文档明确提到：

- `GET /health`
- `POST /file_parse`
- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/result`

这说明官方 3.x 已经同时提供同步和异步两类服务能力。

### 4. 官方已经引入 router

`mineru-router` 的定位是：

- 统一入口
- 多服务编排
- 多 GPU 自动负载
- 与 `mineru-api` 接口兼容

这属于官方 3.x 面向更高并发、更复杂部署形态的能力。

### 5. 官方 Docker 部署基线

官方 Docker 文档当前强调：

- Docker 部署主要面向 Linux 与支持 WSL2 的 Windows
- 本地镜像基于 vLLM 路线
- 单机 GPU 需要满足显存与驱动前提
- `compose.yaml` 中可直接启动 `mineru-api`、`mineru-router` 等服务

---

## 对本项目的直接含义

### 含义 1：本地模式和云端模式必须拆开描述

云端 API 模式支持范围更宽，当前仓库也已经补到了：

- `PDF / DOC / DOCX / PPT / PPTX / HTML / 图片`

但官方本地支持集并不包含：

- `DOC`
- `PPT`
- `HTML`

因此 GPU 本地模式文档、测试、代码都必须单独维护其支持范围，不能简单复用 cloud 的能力表述。

### 含义 2：我们可以继续使用 `mineru-api`

虽然官方已经提供 `/tasks` 和 `mineru-router`，但本项目外层本来就已经有：

- Celery 队列
- 后端任务状态
- 现有 worker 生命周期

所以本轮最合理的做法不是把外层任务系统推翻重做，而是继续：

- 让 Celery 管排队
- 让 Worker 调用本地 `mineru-api`
- 在单机单卡下优先使用 `/file_parse`

### 含义 3：`mineru-router` 是下一阶段，不是本轮前提

本轮如果把 `mineru-router` 一并引入，会直接带来新的复杂度：

- 单卡与多卡 worker 启动方式
- 本地 worker 自动拉起
- 路由层健康检查
- 统一入口设计
- 与现有 Celery 编排的边界重叠

因此虽然官方已经支持，但本轮文档应明确写成：

- 已调研
- 暂不纳入第一层适配
- 未来如要面向多机多卡再进入

### 含义 4：单机单卡需要优先稳态与一致性

官方能力不等于项目立刻应该全部接入。

对当前项目最实际的路线是：

1. 先让本地支持集补齐到 `PDF / image / DOCX / PPTX / XLSX`
2. 再让 compose、配置、测试、文档一致
3. 最后再评估 router / tasks / 多 GPU

---

## 本轮采用的官方能力边界

### 本轮采用

- `mineru-api`
- `/health`
- `/file_parse`
- 官方本地支持文件集
- 单机单卡 GPU Docker 部署方式

### 本轮不采用

- `mineru-router`
- `/tasks`
- 多机多卡编排
- openai server / http-client 路线
- `--enable-vlm-preload` 相关多服务预热编排

---

## 最终基线定义

本轮 improve-3-gpu 的官方对齐目标可以明确写成：

> 在单用户、单机、单卡 NVIDIA GPU 场景下，继续使用本项目现有 Celery 队列，调用本地 `mineru-api` 的同步 `/file_parse` 接口，使仓库 GPU 本地模式覆盖官方本地支持集 `PDF / image / DOCX / PPTX / XLSX`，并保证 compose、配置、测试与文档行为一致。
