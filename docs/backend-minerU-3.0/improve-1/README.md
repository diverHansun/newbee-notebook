# Backend MinerU 3.0 升级与优化方案（improve-1）

本目录记录 MinerU 从 v2.7.x 升级到 v3.0+ 的完整适配方案。本轮（improve-1）聚焦于**本地模式的版本迁移**与**云端 v4 API 的参数增强**两部分，不涉及 v1 轻量 API 的接入。

---

## 本轮目标

1. **让本地 GPU 模式与 MinerU v3.0+ 的新推理链路对齐**（vLLM 0.11.2 + mineru core 3.0）。
2. **修复基础设施层的历史遗留问题**（healthcheck 端点错误）。
3. **补全 MinerU 的新参数**（本地 `parse_method`/`formula_enable`/`table_enable`；云端 `model_version`/`enable_formula`/`enable_table`/`is_ocr`/`language`），通过 YAML 配置与环境变量暴露给运维。
4. **保证 ZIP 结构变化的前向兼容性**（代码分析后确认无需修改，仍要在实施步骤中做回归验证）。

明确不做的事情：

- 不引入 v1 Agent Lightweight API 的 fallback 链路（v1 只返回 markdown、无图片资产，处理降级语义复杂，延后到后续迭代）。
- 不把新参数的配置项接入前端 Settings Panel（仅配置文件可改，管理员侧操作）。
- 不改动 `_parse_result_zip` 的解析逻辑（已通过代码审查验证其对新 ZIP 结构兼容）。
- 不改动 circuit breaker 与 MarkItDown fallback 语义。

---

## 分支策略

所有变更在独立分支 `backend-minerU-3.0` 上完成，开发验证通过后以 PR 形式合并回 `main`。

### 创建并切换到工作分支

```bash
cd d:/Projects/NotebookLM/newbee-notebook

# 确认当前在最新 main
git checkout main
git pull origin main

# 创建并切换到新分支
git checkout -b backend-minerU-3.0

# 推送到远端（首次）
git push -u origin backend-minerU-3.0
```

### 后续开发节奏

- 每个变更域（Docker / 本地转换器 / 云端转换器 / 配置层）建议一个独立 commit，便于后续 review 与 cherry-pick。
- 每次 commit 前运行相关测试（见 [06-implementation-steps.md](./06-implementation-steps.md) 的验收章节）。
- 完成全部改动并通过 smoke test 后，合并回 `main`：

```bash
# 合并回 main 前确保分支同步
git checkout backend-minerU-3.0
git rebase main

# 通过 PR 合并（推荐）或直接 merge
git checkout main
git merge --no-ff backend-minerU-3.0
git push origin main
```

---

## 文档结构

本目录采用**分域文档 + 总 index**的组织方式，每份文档对应一个独立的变更域，阅读顺序为编号递增：

| 文件 | 内容 |
|---|---|
| [README.md](./README.md) | 本文件 — 总览、目标、分支策略、文档索引 |
| [01-change-overview.md](./01-change-overview.md) | 所有变更点的汇总表、MinerU 官方文档依据 |
| [02-docker-infrastructure.md](./02-docker-infrastructure.md) | `Dockerfile.gpu` / `Dockerfile.cpu` 版本升级；`docker-compose.gpu.yml` healthcheck 修复 |
| [03-local-converter.md](./03-local-converter.md) | `MinerULocalConverter` 新参数设计与代码 diff |
| [04-cloud-converter.md](./04-cloud-converter.md) | `MinerUCloudConverter` 新参数设计、`model_version` 三种模式详解 |
| [05-config-layer.md](./05-config-layer.md) | `document_processing.yaml` 新增配置项、`processor.py` 透传逻辑 |
| [06-implementation-steps.md](./06-implementation-steps.md) | 分阶段实施顺序、每一步的验证方式、回滚预案 |

---

## 官方资料来源

本次设计所依据的 MinerU 官方资料：

- **本地 API 源码**：仓库 [opendatalab/MinerU](https://github.com/opendatalab/MinerU) v3.1.2-released，已下载到 `mineru/` 目录下；关键文件 `mineru/mineru/cli/fast_api.py`（新版 `/file_parse` 表单定义与 `/health` 端点）、`mineru/docker/global/Dockerfile`（官方最新 GPU 镜像）、`mineru/docker/compose.yaml`（官方 compose 配置）。
- **云端 v4 API 文档**：<https://mineru.net/apiManage/docs> — 本次重点关注 `/api/v4/file-urls/batch`（batch 上传）、`/api/v4/extract-results/batch/{batch_id}`（结果查询）、各接口的新参数（`model_version`、`enable_formula`、`enable_table`、`is_ocr`、`language`、`page_ranges` 等）。
- **KIE SDK**：<https://mineru.net/apiManage/kie-sdk> — 已评估，属于独立的知识信息抽取服务（需要 `pipeline_id`），与本项目的文档转 Markdown 场景不相关，不在本轮适配范围内。

---

## 风险提示

1. **mineru 3.0 对 vLLM 的升级是 breaking 级别**，首次拉起容器会触发模型重新下载（约 10+ GB），需预留时间与网络带宽。持久化缓存卷 `mineru_cache:/root/.cache` 保证后续重启无需重复下载。
2. **CPU 镜像同步升级到 3.0 有风险**，pipeline 后端在 3.0 内部依赖有调整，需要在升级后做一次完整的 smoke test（跑一份已知样本 PDF，比对输出）。
3. **不推荐在生产环境直接合并**，建议先在 staging 环境跑至少 24 小时的真实样本回归再决定。
