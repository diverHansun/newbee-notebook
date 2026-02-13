# Improve-7: 模型扩展与多供应商支持

## 1. 阶段背景

在 improve-6 完成记忆架构和存储机制后，项目开始准备前后端联调。此阶段需要解决模型层的两个核心问题:

1. **LLM 供应商锁定**: 当前只支持智谱 GLM 系列，缺乏供应商切换能力。需要接入阿里云百炼 (DashScope) 的 Qwen 系列模型。
2. **Embedding 模型不适配**: BioBERT 不支持中文、最大 512 tokens、768 维度，不适合通用中英文文档的 RAG 检索。需要引入 Qwen3-Embedding (文本) 和 Qwen3-VL-Embedding (多模态) 两类新模型。

本阶段目标是在不破坏现有功能的前提下，通过 Registry Pattern 统一 LLM 和 Embedding 的供应商管理，实现模型的可切换、可扩展。

## 2. 本阶段已确认决策

1. LLM 模块引入 Registry Pattern，与 Embedding 模块架构统一，通过 `llm.yaml` 中的 `provider` 字段切换供应商。
2. 新增 Qwen LLM 供应商 (`QwenOpenAI`)，接入阿里云百炼 DashScope 的 OpenAI 兼容 API。
3. 新增 Qwen3-Embedding-0.6B 本地 embedding 供应商，下载到 `models/` 目录，CPU 推理。
4. 新增 Qwen3-VL-Embedding 供应商，API 模式 (qwen3-vl-embedding) 优先，本地模式 (Qwen3-VL-Embedding-2B) 作为可选扩展。
5. 所有 embedding 模型统一输出 **1024 维度** (Qwen3 系列支持 MRL 自定义维度)，与现有智谱 embedding-3 兼容，pgvector 索引无需迁移。
6. BioBERT 标记为 deprecated，不再投入维护，但保留代码以备回退。
7. 流式输出 (streaming) 通过 LlamaIndex `astream_chat` 机制统一处理，Qwen 和智谱在 OpenAI 兼容模式下均原生支持。

## 3. 设计约束

1. 与 improve-1 ~ improve-6 的 RAG 管线、对话引擎、文档处理流程兼容。
2. LLM Registry 与 Embedding Registry 遵循相同的设计模式 (装饰器注册 + 工厂函数)。
3. Qwen LLM 走 DashScope OpenAI 兼容 API (`/compatible-mode/v1`)，不引入 DashScope 原生 SDK 依赖。
4. Qwen3-VL-Embedding API 模式需使用 DashScope 原生 MultiModalEmbedding API (非 OpenAI 兼容)，需引入 `dashscope` SDK。
5. 开发环境为 CPU-only，本地模型选型以轻量为原则。
6. 向量维度统一为 1024，切换模型不需要重建索引。

## 4. 文档索引

| 序号 | 文档 | 职责 |
|------|------|------|
| 01 | [01-llm-registry.md](./01-llm-registry.md) | LLM Registry Pattern: 架构设计、QwenOpenAI 实现、llm.yaml 改造、流式输出支持 |
| 02 | [02-embedding-expansion.md](./02-embedding-expansion.md) | Embedding 扩展: Qwen3-Embedding 本地部署、Qwen3-VL-Embedding API/本地双模式 |
| 03 | [03-qwen-api-reference.md](./03-qwen-api-reference.md) | 阿里云百炼 API 参考: LLM 和 Embedding 的请求/响应结构、认证方式、模型矩阵 |
| 04 | [04-dimension-strategy.md](./04-dimension-strategy.md) | 向量维度策略: 统一 1024 维、MRL 机制、BioBERT 弃用方案、pgvector 兼容性 |
| 05 | [05-implementation-plan.md](./05-implementation-plan.md) | 实施计划: 任务拆分、依赖关系、验收标准 |

## 5. 当前状态

- 文档状态: 设计规划阶段
- 创建日期: 2026-02-13
- 阶段版本: v1.0
- 前置依赖: improve-6 已完成
