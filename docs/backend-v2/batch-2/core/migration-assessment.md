# 跨模块迁移评估

本文档从全局视角评估现有代码的处置方式和迁移路径。按新的四模块边界（context、engine、session、tools）组织。

## 1. 现有文件处置总览

### 1.1 core/engine/ -- 当前引擎层

| 文件 | 当前职责 | 处置 | 目标模块 |
|------|---------|------|---------|
| session.py | SessionManager（全能管理者） | 重构 | session/ |
| selector.py | ModeSelector（Mode 工厂 + 缓存） | 删除 | 被 engine/mode_config.py 取代 |
| modes/base.py | BaseMode 模板方法基类 | 删除 | 被 AgentLoop 取代 |
| modes/chat_mode.py | FunctionAgent 工具调用模式 | 删除 | 被 AgentLoop + Agent 配置取代 |
| modes/ask_mode.py | ReActAgent RAG 问答模式 | 删除 | 被 AgentLoop + Ask 配置取代 |
| modes/explain_mode.py | CondensePlusContext 解释模式 | 删除 | 被 AgentLoop + Explain 配置取代 |
| modes/conclude_mode.py | CondensePlusContext 总结模式 | 删除 | 被 AgentLoop + Conclude 配置取代 |
| modes/utils.py | 辅助工具 | 评估 | 如仅被 modes 使用则删除 |
| index_builder.py | 向量索引构建 | 保留 | 不移动 |
| notebook_context.py | Notebook 上下文管理 | 保留 | 不移动 |

### 1.2 core/agent/ -- 当前 Agent Runner 层

| 文件 | 当前职责 | 处置 |
|------|---------|------|
| base.py | AgentRunner 基类 | 删除 |
| agent.py | NewbeeNotebookAgent（测试用 facade） | 删除 |
| function_agent.py | FunctionAgentRunner | 删除 |
| react_agent.py | ReActAgentRunner | 删除 |

整个目录删除。AgentLoop 直接使用 LlamaIndex LLM 的 achat_with_tools，不需要中间 Agent Runner。

### 1.3 core/memory/ -- 当前记忆层

| 文件 | 当前职责 | 处置 |
|------|---------|------|
| chat_memory.py | ChatSummaryMemoryBuffer 工厂 | 废弃 |

被 context 模块（SessionMemory + Compressor）取代。如果 Compressor 的摘要生成复用了 ChatSummaryMemoryBuffer 的 summarize prompt 配置，可以保留配置读取逻辑。

### 1.4 core/tools/ -- 工具层

| 文件 | 当前职责 | 处置 |
|------|---------|------|
| tool_registry.py | 工具注册表 | 重构（重命名为 tool_builder.py 可选） |
| es_search_tool.py | ES BM25 搜索 | 改造（去掉 wrapper side-effect） |
| tavily_tools.py | Tavily Web 搜索 | 保留 |
| zhipu_tools.py | 智谱 Web 搜索 | 保留 |
| time.py | 时间工具 | 保留 |

新增文件：
- rag_tool.py -- knowledge_base FunctionTool 封装

### 1.5 core/prompts/ -- 提示词

| 文件 | 处置 |
|------|------|
| chat.md | 保留，可能微调 |
| ask.md | 保留，可能微调 |
| explain.md | 保留，增加检索指示段落 |
| conclude.md | 保留，增加检索指示段落 |
| __init__.py | 保留 |

### 1.6 core/rag/ -- 检索层

| 子模块 | 处置 |
|--------|------|
| retrieval/ | 全部直接复用 |
| postprocessors/ | 直接复用 |
| embeddings/ | 不涉及 |
| text_splitter/ | 不涉及 |
| indexing.py | 不涉及 |
| document_loader/ | 不涉及 |
| generation/chat_engine.py | 评估后废弃（不再被使用） |
| generation/query_engine.py | 评估后废弃（不再被使用） |

### 1.7 core/llm/ -- LLM Provider 层

不涉及改动。

### 1.8 core/common/ -- 通用工具

不涉及改动。

### 1.9 上游调用方

| 文件 | 影响 |
|------|------|
| api/routers/chat.py | 适配新 SSE 事件格式（新增 tool_call/tool_result） |
| api/models/requests.py | ChatRequest 扩展（rag_config、selected_text 提升） |
| application/services/chat_service.py | 适配 SessionManager 的新接口 |

## 2. 新增文件总览

| 目标模块 | 新增文件 | 职责 |
|---------|---------|------|
| core/context/ | session_memory.py | SessionMemory 双轨容器 |
| core/context/ | context_builder.py | 消息链组装 + 分层压缩 |
| core/context/ | token_counter.py | Token 统计 |
| core/context/ | budget.py | 预算分配策略 |
| core/context/ | compressor.py | 压缩器（截断、首段提取、摘要） |
| core/engine/ | agent_loop.py | AgentLoop 执行引擎 |
| core/engine/ | mode_config.py | ModeConfigFactory + 配置数据类 |
| core/engine/ | stream_events.py | StreamEvent 类型定义 |
| core/session/ | session_manager.py | SessionManager（重构自 engine/session.py） |
| core/session/ | lock_manager.py | 会话级 AsyncLock |
| core/tools/ | rag_tool.py | knowledge_base FunctionTool |

## 3. 迁移顺序

迁移按以下顺序执行，每步可独立验证。后一步依赖前一步的产出。

### 第一步：新增 context 模块

新增 context/ 目录下全部文件。这些是纯数据结构和计算逻辑，无外部依赖（除 LLM tokenizer），可独立编写和测试。

验证标准：SessionMemory 双轨读写正确、ContextBuilder 在 mock 数据上产出符合预算的消息链、Compressor 截断和首段提取正确。

### 第二步：新增 engine 模块核心

新增 stream_events.py、mode_config.py、agent_loop.py。依赖第一步的 context 模块接口（仅类型签名依赖）。使用 mock LLM 和 mock 工具做单元测试。

验证标准：AgentLoop 在 mock 环境下完成工具调用循环，产出正确的 StreamEvent 序列。ModeConfigFactory 为四种模式生成预期配置。

### 第三步：新增 RAG Tool

新增 tools/rag_tool.py。依赖 rag/retrieval/ 的 HybridRetriever。改造 tool_registry.py 增加 RAG Tool 注册。改造 es_search_tool.py 去掉 side-effect。

验证标准：knowledge_base 工具正确封装 HybridRetriever，三种 search_type 路由正确，返回包含 Source 的结果，质量反馈文本正确生成。

### 第四步：新增 session 模块

新增 session/ 目录下文件。将 engine/session.py 的编排逻辑重构到 session/session_manager.py，委托 context 和 engine 模块。

验证标准：SessionManager 可以编排四种模式的请求，双轨上下文正确隔离，并发控制正确。

### 第五步：适配上游

改造 api/routers/chat.py 的 SSE 事件转换。改造 api/models/requests.py 的请求模型。改造 application/services/chat_service.py 的 SessionManager 调用。

验证标准：端到端流式请求返回新格式 SSE 事件，ChatRequest 支持 rag_config 参数。

### 第六步：清理废弃代码

删除 core/engine/modes/ 目录、core/engine/selector.py、core/agent/ 目录。评估并处理 core/rag/generation/ 和 core/memory/。更新 __init__.py 导出。

验证标准：删除后项目正常启动，所有端点正常访问。

## 4. 风险评估

### 4.1 LlamaIndex achat_with_tools 兼容性

AgentLoop 核心依赖 LlamaIndex LLM 的 achat_with_tools 方法。需在第二步用实际 Qwen LLM 验证 tool_choice=auto/required 的行为。

### 4.2 Explain/Conclude 检索质量回归

当前使用 CondensePlusContextChatEngine，其 condense 步骤对多轮 query 优化有价值。重构后改为 LLM 自行提炼 query。第四步完成后需对比测试检索质量。

### 4.3 SSE 前端兼容

新增 tool_call/tool_result 事件、start 改为 phase。过渡期可保留旧事件格式的兼容映射。

### 4.4 token 预算的初始参数

分层压缩的各层预算需要实际测试确定。初始值参考当前配置（CA memory 64K tokens、EC memory 2K tokens），可能需要多轮调优。

### 4.5 并发请求安全

当前无并发控制。新增的 SessionLockManager 需要确保不引入死锁（如锁获取超时机制）。

## 5. 变更统计

| 类别 | 文件数 |
|------|--------|
| 新增 | 11 |
| 重构/改造 | 5 |
| 删除 | 12 |
| 保留不变 | 其余全部 |
