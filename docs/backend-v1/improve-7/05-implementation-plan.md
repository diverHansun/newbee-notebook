# 实施计划: improve-7 任务拆分与验收标准

本文档将 improve-7 的所有改造任务拆分为具体步骤，明确依赖关系和验收标准。

---

## 1. 任务总览

```
Phase 1: LLM Registry Pattern 基础设施
  ├── Task 1.1: 创建 LLM Registry 模块
  ├── Task 1.2: 改造 llm.yaml 配置
  ├── Task 1.3: 改造 config.py (新增 get_llm_provider)
  ├── Task 1.4: 改造 zhipu.py + openai.py (添加装饰器)
  └── Task 1.5: 改造 __init__.py (统一工厂)

Phase 2: Qwen LLM 接入
  ├── Task 2.1: 实现 QwenOpenAI 类
  ├── Task 2.2: 实现 build_qwen_llm 工厂
  └── Task 2.3: 验证 Qwen LLM 功能

Phase 3: Qwen Embedding 接入
  ├── Task 3.1: 下载 Qwen3-Embedding-0.6B 模型
  ├── Task 3.2: 实现 QwenLocalEmbedding
  ├── Task 3.3: 实现 QwenAPIEmbedding
  ├── Task 3.4: 改造 embeddings.yaml
  └── Task 3.5: 改造 embeddings/__init__.py

Phase 4: Qwen VL Embedding 接入 (可选)
  ├── Task 4.1: 实现 QwenVLAPIEmbedding
  ├── Task 4.2: 实现 QwenVLLocalEmbedding (可选)
  └── Task 4.3: 验证多模态 Embedding

Phase 5: 集成验证与清理
  ├── Task 5.1: 端到端验证
  ├── Task 5.2: BioBERT 弃用标记
  ├── Task 5.3: 环境配置更新
  └── Task 5.4: 向量维度迁移 (如需)
```

---

## 2. Phase 1: LLM Registry Pattern 基础设施

### Task 1.1: 创建 LLM Registry 模块

**文件**: `core/llm/registry.py` (新增)

**内容**:
- `_LLM_REGISTRY` 全局字典
- `register_llm(name)` 装饰器
- `get_registered_providers()` 查询函数
- `get_builder(provider)` 获取构建函数

**依赖**: 无

**验收标准**:
- [ ] `register_llm("test")` 装饰器能注册 builder
- [ ] `get_builder("test")` 返回已注册的 builder
- [ ] `get_builder("unknown")` 抛出 ValueError 并列出可用 providers
- [ ] 重复注册同名 provider 抛出 ValueError

---

### Task 1.2: 改造 llm.yaml 配置

**文件**: `configs/llm.yaml` (修改)

**改动**:
- 新增顶层 `provider` 字段，默认值 `zhipu`
- 将现有配置嵌套在 `zhipu` key 下
- 新增 `qwen` section (留空或基本配置)
- 新增 `openai` section

**依赖**: 无

**验收标准**:
- [ ] `llm.yaml` 包含 `provider` 字段
- [ ] `zhipu`, `qwen`, `openai` 三个 section 均存在
- [ ] 现有代码不受影响 (向后兼容)

---

### Task 1.3: 改造 config.py

**文件**: `core/common/config.py` (修改)

**改动**:
- 新增 `get_llm_provider()` 函数
- 优先级: `LLM_PROVIDER` 环境变量 > `llm.yaml` `provider` 字段 > 默认 `"zhipu"`

**依赖**: Task 1.2 (需要 yaml 中有 provider 字段)

**验收标准**:
- [ ] 无环境变量时，从 yaml 读取 provider
- [ ] 设置 `LLM_PROVIDER=qwen` 环境变量时，返回 `"qwen"`
- [ ] yaml 中无 provider 字段时，返回默认值 `"zhipu"`

---

### Task 1.4: 改造 zhipu.py + openai.py

**文件**: `core/llm/zhipu.py`, `core/llm/openai.py` (修改)

**改动**:
- 在各自的 `build_llm()` / `build_openai_llm()` 函数上添加 `@register_llm("zhipu")` / `@register_llm("openai")` 装饰器
- Import `register_llm` from registry

**依赖**: Task 1.1

**验收标准**:
- [ ] 导入 `zhipu` 模块后，`get_registered_providers()` 包含 `"zhipu"`
- [ ] 导入 `openai` 模块后，`get_registered_providers()` 包含 `"openai"`
- [ ] 现有 `build_zhipu_llm()` 和 `build_openai_llm()` 直接调用仍正常

---

### Task 1.5: 改造 __init__.py

**文件**: `core/llm/__init__.py` (修改)

**改动**:
- Import 所有 provider 模块 (触发注册)
- 新增统一 `build_llm()` 函数，走 registry + `get_llm_provider()`
- 导出 `build_llm`, `get_registered_providers`

**依赖**: Task 1.1, 1.3, 1.4

**验收标准**:
- [ ] `from newbee_notebook.core.llm import build_llm` 可正常导入
- [ ] `build_llm()` 根据 yaml provider 字段返回对应 LLM 实例
- [ ] 修改 yaml provider 为 `"openai"` 后，`build_llm()` 返回 OpenAI 实例

---

## 3. Phase 2: Qwen LLM 接入

### Task 2.1: 实现 QwenOpenAI 类

**文件**: `core/llm/qwen.py` (新增)

**内容**:
- `QwenOpenAI(OpenAI)` 类
- 覆写 `metadata` 属性 (QWEN_CONTEXT_WINDOWS 查表)
- 覆写 `_tokenizer` 属性 (避免 tiktoken 报错)

**依赖**: Phase 1 完成

**验收标准**:
- [ ] `QwenOpenAI(model="qwen-plus", api_key="sk-xxx", api_base="...")` 可实例化
- [ ] `metadata.context_window` 对 `qwen-plus` 返回 1000000
- [ ] `metadata.is_chat_model` 返回 True
- [ ] `_tokenizer` 不抛出异常

---

### Task 2.2: 实现 build_qwen_llm 工厂

**文件**: `core/llm/qwen.py` (同上)

**内容**:
- `@register_llm("qwen")` 装饰 `build_qwen_llm()`
- 读取 `llm.yaml` 的 `qwen` section
- 支持 `DASHSCOPE_API_KEY` / `QWEN_API_KEY` 环境变量
- 支持 `enable_search`, `enable_thinking` 特有参数

**依赖**: Task 2.1

**验收标准**:
- [ ] `get_registered_providers()` 包含 `"qwen"`
- [ ] 设置 `DASHSCOPE_API_KEY` 后，`build_qwen_llm()` 返回 QwenOpenAI 实例
- [ ] 未设置 API Key 时，抛出 ValueError
- [ ] yaml 中配置 `enable_search: true` 时，`additional_kwargs` 包含该参数

---

### Task 2.3: 验证 Qwen LLM 功能

**依赖**: Task 2.2, 需要有效的 DASHSCOPE_API_KEY

**验收标准**:
- [ ] 非流式对话: `llm.chat([...])` 返回有效响应
- [ ] 流式对话: `llm.stream_chat([...])` 逐 token 返回
- [ ] 通过 `build_llm()` (provider=qwen) 创建的 LLM 可正常工作
- [ ] 在 ChatService 中替换 LLM 后，对话功能正常

---

## 4. Phase 3: Qwen Embedding 接入

### Task 3.1: 下载 Qwen3-Embedding-0.6B 模型

**操作**:

```bash
cd newbee-notebook
git lfs install
git clone https://huggingface.co/Qwen/Qwen3-Embedding-0.6B models/Qwen3-Embedding-0.6B
```

**依赖**: 无

**验收标准**:
- [ ] `models/Qwen3-Embedding-0.6B/config.json` 存在
- [ ] `models/Qwen3-Embedding-0.6B/model.safetensors` 存在
- [ ] `.gitignore` 已排除 models 目录的大文件

---

### Task 3.2: 实现 QwenLocalEmbedding

**文件**: `core/rag/embeddings/qwen_embedding.py` (新增)

**内容**:
- `QwenLocalEmbedding(BaseEmbeddingModel)` 类
- 使用 `sentence-transformers` 加载模型
- 支持 MRL 维度控制 (默认 1024)
- L2 归一化

**依赖**: Task 3.1, `sentence-transformers` 安装

**验收标准**:
- [ ] `QwenLocalEmbedding("models/Qwen3-Embedding-0.6B")` 可实例化
- [ ] `get_text_embedding("测试文本")` 返回 1024 维向量
- [ ] `get_text_embeddings(["文本1", "文本2"])` 返回 2 个 1024 维向量
- [ ] 向量已 L2 归一化 (norm ≈ 1.0)
- [ ] CPU 推理速度可接受 (< 200ms/句)

---

### Task 3.3: 实现 QwenAPIEmbedding

**文件**: `core/rag/embeddings/qwen_embedding.py` (同上)

**内容**:
- `QwenAPIEmbedding(BaseEmbeddingModel)` 类
- 使用 OpenAI SDK 调用 DashScope `/v1/embeddings`
- `dimensions=1024` 参数

**依赖**: `DASHSCOPE_API_KEY` 环境变量

**验收标准**:
- [ ] `QwenAPIEmbedding(model="text-embedding-v4")` 可实例化
- [ ] `get_text_embedding("测试文本")` 返回 1024 维向量
- [ ] 未设置 API Key 时，抛出 ValueError

---

### Task 3.4: 改造 embeddings.yaml

**文件**: `configs/embeddings.yaml` (修改)

**改动**:
- 修改 `provider` 默认值为 `qwen-embedding`
- 新增 `qwen-embedding` section
- 新增 `qwen-vl-embedding` section
- 设置 `biobert.enabled: false`

**依赖**: 无

**验收标准**:
- [ ] yaml 可正常解析
- [ ] `qwen-embedding` section 包含 mode, model_path, dim 等字段
- [ ] `biobert.enabled` 为 false

---

### Task 3.5: 改造 embeddings/__init__.py

**文件**: `core/rag/embeddings/__init__.py` (修改)

**改动**:
- 新增 `import qwen_embedding` 和 `import qwen_vl_embedding`

**依赖**: Task 3.2, 3.3

**验收标准**:
- [ ] `from newbee_notebook.core.rag.embeddings import build_embedding` 可正常导入
- [ ] `get_registered_providers()` 包含 `"qwen-embedding"`
- [ ] `build_embedding()` (provider=qwen-embedding, mode=local) 返回 QwenLocalEmbedding 实例

---

## 5. Phase 4: Qwen VL Embedding 接入 (可选)

### Task 4.1: 实现 QwenVLAPIEmbedding

**文件**: `core/rag/embeddings/qwen_vl_embedding.py` (新增)

**内容**:
- `QwenVLAPIEmbedding(BaseEmbeddingModel)` 类
- 使用 `dashscope` SDK 调用 MultiModalEmbedding API
- `embed_image(image_url, text)` 方法
- 文本输入走 `_get_text_embeddings()`

**依赖**: `dashscope` SDK 安装, DASHSCOPE_API_KEY

**验收标准**:
- [ ] `QwenVLAPIEmbedding()` 可实例化
- [ ] 纯文本 embedding 返回 1024 维向量
- [ ] 图片 URL embedding 返回 1024 维向量
- [ ] 文本+图片混合 embedding 返回 1024 维向量

---

### Task 4.2: 实现 QwenVLLocalEmbedding (可选)

**文件**: `core/rag/embeddings/qwen_vl_embedding.py` (同上)

**说明**: 2B 模型在 CPU 上推理较慢，此任务为可选。优先确保 API 模式可用。

**依赖**: 下载 Qwen3-VL-Embedding-2B 模型

**验收标准**:
- [ ] 本地模型加载成功
- [ ] 文本 embedding 返回 1024 维

---

### Task 4.3: 验证多模态 Embedding

**依赖**: Task 4.1

**验收标准**:
- [ ] 文本查询能检索到相关图片
- [ ] 图片查询能检索到相关文本
- [ ] 与 pgvector 的 cosine similarity 操作正常

---

## 6. Phase 5: 集成验证与清理

### Task 5.1: 端到端验证

**验收标准**:
- [ ] **LLM 切换**: 修改 `llm.yaml` provider 为 `qwen`，对话功能正常
- [ ] **LLM 切换**: 通过 `LLM_PROVIDER=qwen` 环境变量切换，功能正常
- [ ] **LLM 流式**: Qwen 流式对话在所有 mode_engine 中正常 (chat, ask, explain, conclude)
- [ ] **Embedding 切换**: 修改 `embeddings.yaml` provider 为 `qwen-embedding`，RAG 检索正常
- [ ] **向量维度**: 所有新 embedding 输出 1024 维
- [ ] **回退测试**: 切换回 zhipu provider，所有功能不受影响

---

### Task 5.2: BioBERT 弃用标记

**文件**: `configs/embeddings.yaml`, `core/rag/embeddings/biobert.py`

**改动**:
- yaml 中 `biobert.enabled: false`
- biobert.py 文件头添加 deprecated 注释

**验收标准**:
- [ ] `build_embedding()` 默认不选择 biobert
- [ ] biobert 代码保留，可手动启用

---

### Task 5.3: 环境配置更新

**文件**: `.env.example`, `requirements.txt`

**改动**:
- `.env.example` 新增 `DASHSCOPE_API_KEY=`
- `requirements.txt` 新增 `sentence-transformers>=3.0.0`, `dashscope>=1.20.0`

**验收标准**:
- [ ] 新拉取项目的开发者能根据 `.env.example` 配置 Qwen
- [ ] `pip install -r requirements.txt` 安装所有依赖

---

### Task 5.4: 向量维度迁移 (如需)

**条件**: 仅当 pgvector 中存在 768 维 BioBERT 向量时执行

**步骤**:
1. 检查数据库中是否存在 768 维数据
2. 如有，用新的 1024 维模型重新编码
3. 修改列定义为 `vector(1024)`
4. 重建索引

**验收标准**:
- [ ] 所有向量维度统一为 1024
- [ ] pgvector 索引正常工作
- [ ] RAG 检索结果正确

---

## 7. 依赖关系图

```
Task 1.1 ──────────────────────────┐
Task 1.2 ──────────┐               │
                    ├─→ Task 1.3 ──┤
                    │              │
Task 1.1 ──────────┼─→ Task 1.4 ──┤
                    │              │
                    └──────────────┼─→ Task 1.5
                                   │
                                   ├─→ Task 2.1 ─→ Task 2.2 ─→ Task 2.3
                                   │
Task 3.1 ─────────────────────────────→ Task 3.2 ─┐
                                   │               ├─→ Task 3.5
                                   ├─→ Task 3.3 ──┘
                                   │               ┌─→ Task 4.3
                                   ├─→ Task 4.1 ──┘
                                   │
                                   └─→ Task 4.2 (可选)

Task 2.3 + Task 3.5 + Task 4.3 ──→ Task 5.1 (端到端验证)
Task 3.4 (独立)
Task 5.2 (独立)
Task 5.3 (独立)
Task 5.4 (条件性)
```

---

## 8. 可并行的任务组

以下任务组之间没有依赖，可以并行推进:

**并行组 A** (LLM 侧):
- Task 1.1 → 1.4 → 1.5 → 2.1 → 2.2

**并行组 B** (Embedding 侧):
- Task 3.1 (模型下载)
- Task 3.4 (yaml 改造)

**并行组 C** (配置侧):
- Task 1.2 (llm.yaml)
- Task 5.3 (.env, requirements)

---

## 9. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| DashScope API 不稳定 | Qwen LLM/Embedding 不可用 | 保留 zhipu 作为 fallback |
| Qwen3-Embedding-0.6B CPU 推理慢 | 文档处理瓶颈 | 切换 API 模式 |
| sentence-transformers 版本冲突 | 依赖安装失败 | 锁定版本号 |
| tiktoken 对 Qwen 模型名报错 | LLM 初始化失败 | _tokenizer try/except 已处理 |
| BioBERT 768 维旧数据 | 检索结果不正确 | Task 5.4 迁移脚本 |

---

## 10. 完成定义

improve-7 整体完成标准:

1. **LLM Registry**: `build_llm()` 可通过 yaml/环境变量切换 zhipu, qwen, openai
2. **Qwen LLM**: 流式对话在所有 mode_engine 中正常工作
3. **Qwen Embedding**: 本地模式 (0.6B) 可正常生成 1024 维向量
4. **维度统一**: 所有 embedding 输出 1024 维，pgvector 查询正常
5. **向后兼容**: 切换回 zhipu provider 后，所有功能不受影响
6. **BioBERT 弃用**: 标记为 disabled，代码保留
7. **文档+配置**: .env.example, requirements.txt, yaml 均更新
