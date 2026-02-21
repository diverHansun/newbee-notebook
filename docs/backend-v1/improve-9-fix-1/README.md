# Improve-9-Fix-1: MinerU 批处理内存/显存泄漏修复

## 1. 阶段背景

在 improve-8（流水线模块化拆分）完成后，项目进入文档处理的实际验收阶段。使用 MinerU Local（GPU 模式）处理大型 PDF 时，发现批次间内存和 GPU 显存无法释放，导致 WSL2 VM 的 OOM Killer 终止 MinerU 容器进程。

前序修复已引入分批处理机制（通过 `start_page_id` / `end_page_id` 参数将大 PDF 分批发送给 MinerU API），但批次间没有任何内存清理动作，实际效果受限。

本阶段目标是定位并修复内存/显存泄漏的根因，使批大小可从 20 页提升至 60 页，减少总请求次数，加快处理速度。

## 2. 核心问题

1. MinerU 内置的 `clean_vram()` 使用硬编码阈值 8 GB，RTX 5060 Ti（16 GB）上永远不触发清理。
2. MinerU FastAPI 端点 `/file_parse` 在请求完成后不执行 `gc.collect()` 或 `torch.cuda.empty_cache()`。
3. 后端 Converter 批循环中没有释放上一批次的结果引用，也没有执行本地 GC。
4. 运行态配置未对齐：容器重建前，`MINERU_VIRTUAL_VRAM_SIZE=8` 未实际注入运行中 `mineru-api` 进程。
5. Celery 实际并发过高：worker 进程实际为 `prefork concurrency=16`，远高于 PDF-GPU 场景可承受并发。
6. 前端大文档渲染卡顿：`View` 页面一次性渲染超长 markdown 且图片占位动画持续重绘，导致滚动严重掉帧。
7. 图片显示稳定性不足：部分文档的图片路径可能是 `images/...` 相对路径，前端缺少统一兜底转换。

## 3. 修复策略

- 通过 `MINERU_VIRTUAL_VRAM_SIZE=8` 环境变量绕过 MinerU 的显存阈值判断，使其内部 `clean_vram()` 在每个推理阶段后正常触发。
- 在后端 Converter 的批循环中加入 `gc.collect()` 和显式 `del result`。
- 保留 MinerU 元数据（`content_list/model_output`）默认开启，支持通过配置按需关闭。
- 将 Celery worker 并发参数显式化（并发、prefetch、max-tasks-per-child），避免默认 CPU 核数并发导致的资源放大。
- 在后端 Admin API 中新增系统内存诊断与清理端点，提供运维可观测性。
- 删除错误的 wrapper 注入方案（`mineru_wrapper.py`），恢复 Dockerfile 使用官方 `mineru-api` 入口。
- 前端 markdown 改为分段渐进渲染，图片动画改为“仅未加载时生效”，并增加图片相对路径兜底转换。

## 4. 并发说明（面向运维）

文档处理链路有三层并发：

1. **Celery 并发**：同一时刻可执行的任务进程数（同机可并行处理的文档任务上限）。
2. **MinerU API 并发**：`mineru-api` 同时接受的 `/file_parse` 请求数。
3. **单文档分批**：一份 PDF 内部的分页批处理（通常串行），影响单任务峰值内存和总请求次数。

若第 1 层过高（例如 16）且第 2 层 > 1，内存/显存压力会被指数放大，即使单批大小本身合理也可能 OOM。

## 5. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-problem-analysis.md](./01-problem-analysis.md) | 问题分析：MinerU 内存管理机制的根因定位 |
| 02 | [02-fix-plan.md](./02-fix-plan.md) | 修复方案：环境变量修正、Converter 清理、Admin API 设计、代码变更清单 |
