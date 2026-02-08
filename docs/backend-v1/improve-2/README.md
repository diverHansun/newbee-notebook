# MinerU 云服务集成改进方案

## 改进概述

### 当前问题

MediMind Agent 的文档处理流程目前完全依赖本地 Docker 部署的 MinerU 服务：

1. **处理速度慢**：即使在性能较好的 CPU 上，处理大型 PDF 文档仍需要很长时间
2. **资源占用高**：MinerU 容器常驻内存，即使不处理文档也占用系统资源
3. **启动复杂**：默认 `docker-compose up` 必须启动 MinerU 容器，增加启动时间
4. **缺乏灵活性**：无法根据场景选择最优的处理方式

### 改进目标

本次改进引入 MinerU 官方云服务，并重构为三种灵活部署模式：

| 目标 | 描述 |
|------|------|
| 云服务优先 | 默认使用 MinerU 官方云服务，快速处理文档，节省本地资源 |
| 保留本地选项 | 支持 CPU 和 GPU 本地部署，满足离线或自主可控需求 |
| 简化默认启动 | 默认 docker-compose 不启动 MinerU 容器，按需启用 |
| 统一接口 | 三种模式通过统一的 Converter 接口调用，对上层透明 |

## 核心设计

### 三种部署模式

| 模式 | 使用场景 | 优势 | 要求 |
|------|----------|------|------|
| **cloud** | 生产环境，快速处理 | 处理速度快，无本地资源占用 | 需要 Pipeline ID |
| **local-cpu** | 离线环境，无 GPU | 完全自主可控，无外部依赖 | 处理速度慢 |
| **local-gpu** | 高性能要求，有 GPU | 本地高速处理 | 需要 NVIDIA GPU |

### 技术方案

1. **SDK 集成**：基于官方 `mineru-kie-sdk` 实现云服务调用
2. **异步处理**：云服务采用上传+轮询模式，适配现有 Celery 任务
3. **Fallback 机制**：保持现有降级逻辑，云服务失败自动降级到 PyPDF
4. **配置驱动**：通过环境变量 `MINERU_MODE` 切换模式，无需修改代码

## 快速开始

### 云服务模式（推荐）

```bash
# 1. 配置 Pipeline ID（在 mineru.net 创建）
export MINERU_MODE=cloud
export MINERU_PIPELINE_ID=your-pipeline-id-here

# 2. 启动服务（不包含 MinerU 容器）
docker-compose up -d

# 3. 使用文档处理功能
```

### 本地 CPU 模式

```bash
# 1. 配置本地模式
export MINERU_MODE=local

# 2. 启动服务（包含 MinerU CPU 容器）
docker-compose --profile mineru-local up -d

# 3. 首次启动会下载模型，需要等待几分钟
```

### 本地 GPU 模式

```bash
# 1. 配置本地模式
export MINERU_MODE=local

# 2. 启动服务（包含 MinerU GPU 容器）
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile mineru-local up -d

# 3. 需要 NVIDIA GPU 和 nvidia-container-toolkit
```

## 文档索引

| 文档 | 描述 |
|------|------|
| [01-architecture.md](./01-architecture.md) | 三模式架构设计、工作流程、错误处理 |
| [02-configuration.md](./02-configuration.md) | 配置文件说明、环境变量、模式切换 |
| [03-sdk-integration.md](./03-sdk-integration.md) | MinerU KIE SDK 集成细节、API 调用 |
| [04-docker-changes.md](./04-docker-changes.md) | Docker Compose 配置变更、依赖调整 |
| [05-migration-guide.md](./05-migration-guide.md) | 从本地模式迁移到云服务的步骤 |
| [06-implementation-plan.md](./06-implementation-plan.md) | 实施计划、任务分解、验收标准 |

## 影响范围

### 需要修改的文件

**配置文件**：
- `medimind_agent/configs/document_processing.yaml`
- `.env` / `.env.example`
- `docker-compose.yml`
- `docker-compose.gpu.yml`

**代码文件**：
- `medimind_agent/infrastructure/document_processing/converters/mineru_converter.py`（重命名为 `mineru_local_converter.py`）
- `medimind_agent/infrastructure/document_processing/converters/mineru_cloud_converter.py`（新增）
- `medimind_agent/infrastructure/document_processing/processor.py`

**依赖**：
- `requirements.txt`（新增 `mineru-kie-sdk`）

### 不涉及的部分

本次改进**不影响**以下部分：
- API 端点和接口
- 数据模型和数据库结构
- 文档存储结构
- RAG 检索逻辑
- 前端调用方式

## 关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| SDK vs 自行实现 | 使用官方 SDK | 稳定可靠，自动处理重试和错误 |
| 同步 vs 异步 | 异步（上传+轮询） | 适配云服务 API，避免长时间阻塞 |
| 模式切换方式 | 环境变量 | 配置简单，支持容器化部署 |
| 默认模式 | cloud | 性能最优，资源占用最少 |
| Fallback 策略 | 保持现有机制 | 确保可用性，降低风险 |

## 版本信息

- **文档版本**：1.0
- **创建日期**：2026-02-08
- **状态**：设计完成，待实施
- **兼容性**：向后兼容，现有本地部署可无缝切换
