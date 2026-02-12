# 后端功能测试报告 - 记忆系统与上下文窗口

**测试日期**: 2026-02-11
**测试范围**: Chat/Ask/Explain/Conclude 四种模式的记忆系统、上下文窗口切换、Session 会话恢复
**测试执行人**: Claude Code
**测试环境**: Windows 11, Docker Desktop, Python 3.11, 后端运行于 localhost:8000

---

## 执行摘要

本次测试聚焦于四种对话模式的记忆系统完整性。通过注入唯一标识符（身份信息、关键词）并在不同模式间切换，验证记忆共享、隔离和会话恢复的正确性。

**核心结论**:
- Chat + Ask 共享记忆系统运行正常
- Explain 和 Conclude 均为完全无状态（与设计文档中"共享记忆"的意图存在差异）
- Session 间完全隔离，会话恢复功能正常
- 发现 `_load_session_history()` 存在跨模式消息泄漏问题
- 发现 `docker compose down -v` 后文档存储与数据库不一致问题
- 缺失 `GET /sessions/{id}/messages` API 端点

---

## 测试数据

### 数据库中的文档

| 文档 | Document ID | 状态 | 页数 | 分块数 | 文件大小 |
|------|------------|------|------|--------|---------|
| 美国反对美国（原版）.pdf | `393f579b-2318-42eb-8a0a-9b5232900108` | completed | 205 | 859 | 16.8 MB |
| 大模型基础 完整版.pdf | `ea0e140d-bd36-49ac-ae67-82287a25ed09` | completed | 1 | 635 | 22.2 MB |

### 测试资源

- **Notebook**: `73e1eada-7140-47b2-b157-f4bc52d38f8a` (Memory Test Notebook)
- **Session 1**: `00447fbe-a29e-4e22-9d1f-7c05724a9849` (主测试会话)
- **Session 2**: `a1368814-0bbc-441f-a674-4d2f337918e9` (隔离测试会话)
- 测试完成后所有 Session 和 Notebook 已删除，文档保留

---

## 代码分析: 记忆系统架构

### 实际实现

通过阅读源代码，确认了以下实际实现：

| 组件 | 代码位置 | 行为 |
|------|---------|------|
| `self._memory` | session.py:42-45 | Chat/Ask 共享的 `ChatMemoryBuffer` |
| `self._conclude_memory` | session.py:46-49 | 创建了独立缓冲区，但未被实际使用 |
| ChatMode | selector.py:118-123 | 接收 `self._memory`，多轮记忆 |
| AskMode | selector.py:125-131 | 接收 `self._memory`，多轮记忆 |
| ExplainMode | explain_mode.py:82-83 | 强制 `memory=None`，完全无状态 |
| ConcludeMode | conclude_mode.py:71,77 | 接收 `_conclude_memory` 但内部覆盖 `self._memory = None` |

### 与设计文档的差异

设计文档描述的双上下文系统:
- **系统A**: Chat + Ask 共享记忆 -- **实现一致**
- **系统B**: Conclude + Explain 共享记忆 -- **实现不一致**

实际代码中 Explain 和 Conclude 都强制将 memory 设为 None，它们之间没有任何记忆共享。`_conclude_memory` 虽然在 `SessionManager.__init__` 中创建并传递给 `ModeSelector`，但在 `ConcludeMode.__init__` 的第 77 行被 `self._memory = None` 覆盖，等于未生效。

---

## 测试用例与结果

### 测试一: Chat + Ask 共享记忆

**测试方法**: 在 Chat 模式建立身份锚点，切换到 Ask 模式验证记忆继承，再反向验证。

#### 步骤详情

| 步骤 | 模式 | 操作 | 预期 | 实际 | 结果 |
|------|------|------|------|------|------|
| Chat-1 | chat | 声明身份: "My name is XiaoMing, AI researcher, interested in Transformer" | 接受并记忆 | 正确记忆 | 通过 |
| Chat-2 | chat | 询问 "What is my name and interest?" | 回忆 XiaoMing + Transformer | 完整回忆 | 通过 |
| Ask-1 | ask | 询问 "Based on previous conversation, what is my name?" | 继承 Chat 记忆，回忆身份 | 正确回忆 XiaoMing + Transformer + AI researcher | 通过 |
| Ask-2 | ask | 添加新信息 "My project code is Project-Alpha-2026" | 记忆新信息 | 正确记忆 | 通过 |
| Chat-3 | chat | 询问 "Summarize everything about me" | 包含 Ask 中添加的信息 | 完整回忆: XiaoMing, AI researcher, Transformer, Project-Alpha-2026 | 通过 |

**结论**: Chat 和 Ask 之间的双向记忆共享完全正常。

---

### 测试二: Explain 无状态行为

**测试方法**: 在 Explain 模式注入唯一关键词，第二次调用时验证是否遗忘。

| 步骤 | 操作 | 预期 | 实际 | 结果 |
|------|------|------|------|------|
| Explain-1 | 注入关键词 RAINBOW-UNICORN-42 并请求解释 attention mechanism | 回答解释内容 | 正常回答 | 通过 |
| Explain-2 | 询问 "What is my special keyword?" | 不记得关键词 | 不包含 RAINBOW/UNICORN，纯粹回答 attention 相关内容 | 通过 |

**结论**: Explain 模式确认为完全无状态，每次调用独立。

---

### 测试三: Conclude 无状态行为

**测试方法**: 同上，使用不同关键词。

| 步骤 | 操作 | 预期 | 实际 | 结果 |
|------|------|------|------|------|
| Conclude-1 | 注入关键词 GOLDEN-DRAGON-99 并请求总结 | 回答总结内容 | 正常回答 | 通过 |
| Conclude-2 | 询问 "What was my secret code?" | 不记得关键词 | 不包含 GOLDEN/DRAGON | 通过 |

**结论**: Conclude 模式确认为完全无状态，每次调用独立。

---

### 测试四: 跨组上下文隔离

**测试方法**: 经过多次 Explain/Conclude 调用后，验证 Chat/Ask 核心记忆是否被破坏或污染。

| 步骤 | 模式 | 操作 | 预期 | 实际 | 结果 |
|------|------|------|------|------|------|
| Chat-4 | chat | 经过 Explain/Conclude 后，询问 "Do you still remember my identity?" | 核心记忆完好 | 完整回忆 XiaoMing, AI researcher, Transformer, Project-Alpha-2026 | 通过 |
| Ask-3 | ask | 询问 "Do you know RAINBOW-UNICORN-42 and GOLDEN-DRAGON-99?" | 不应知道（理想情况） | **知道这两个关键词** | 需关注 |

**发现: DB 历史消息泄漏**

Chat/Ask 能够"看到" Explain/Conclude 中提及的关键词（RAINBOW-UNICORN-42, GOLDEN-DRAGON-99）。原因分析：

```
Explain/Conclude 调用 -> 消息持久化到 DB (chat_service.py:148,276)
         |
         v
下一次 Chat/Ask 调用 -> start_session() -> _load_session_history()
         |
         v
从 DB 加载最近 50 条消息 (session.py:106-108)
         |
         v
所有消息（含 explain/conclude）注入 self._memory
         |
         v
Chat/Ask 的 LLM 上下文中可见 explain/conclude 的对话内容
```

**根因**: `_load_session_history()` 加载消息时不按 `mode` 字段过滤，导致所有模式的消息混入 Chat/Ask 的记忆缓冲区。

**影响评估**: 中等。Explain/Conclude 自身仍然是无状态的（每次调用不记得上一次），但它们的历史消息会成为 Chat/Ask 上下文的一部分，可能导致：
- Chat/Ask 上下文被不相关的 explain/conclude 内容稀释
- token 消耗增加
- LLM 可能混淆不同模式间的语境

---

### 测试五: Session 会话恢复

**测试方法**: 创建 Session 2，验证 Session 间隔离；然后切回 Session 1，验证恢复。

| 步骤 | Session | 操作 | 预期 | 实际 | 结果 |
|------|---------|------|------|------|------|
| S2-Chat-1 | Session 2 | 询问 "Who is XiaoMing? What is Project-Alpha-2026?" | 不知道 Session 1 的上下文 | 将 XiaoMing 解读为黄晓明（演员），Project-Alpha-2026 解读为电视节目 | 通过 |
| S1-Chat-5 | Session 1 | 切回后询问 "Can you recall everything about me?" | 完整恢复记忆 | 正确回忆: XiaoMing, AI researcher, Transformer, Project-Alpha-2026 | 通过 |

**结论**: Session 间完全隔离，会话恢复机制通过 DB 持久化+重新加载实现，功能正常。

---

## 发现的问题

### 问题一: Conclude/Explain 共享记忆未实现

**严重程度**: 设计偏差

**描述**: 设计文档规定 Conclude 和 Explain 应共享独立的记忆上下文（系统B），但代码中两者都强制 `memory=None`。`SessionManager` 中创建的 `_conclude_memory` 缓冲区虽然传递到了 `ModeSelector`，但在 `ConcludeMode.__init__` 中被覆盖为 None。

**涉及代码**:
- `conclude_mode.py:77` - `self._memory = None` 覆盖了传入的 memory
- `explain_mode.py:83` - `super().__init__(llm=llm, memory=None, ...)` 强制 None
- `session.py:46-49` - `_conclude_memory` 创建但未生效

**建议**: 如果需要实现 Conclude/Explain 共享记忆:
1. 移除 `conclude_mode.py:77` 的 `self._memory = None`
2. 修改 `ExplainMode.__init__` 接受并使用 `_conclude_memory`
3. 在 `selector.py:142-149` 中将 `_conclude_memory` 传给 ExplainMode
4. 在 `_load_session_history()` 中按 mode 分别加载到对应的 memory 缓冲区

### 问题二: DB 历史消息跨模式泄漏

**严重程度**: 中等

**描述**: `_load_session_history()` 从数据库加载消息时不过滤 `mode` 字段，导致 Explain/Conclude 产生的消息被注入到 Chat/Ask 的 `self._memory` 中。

**涉及代码**:
- `session.py:102-115` - `_load_session_history()` 加载所有消息
- `session.py:110` - `self._memory.reset()` 只重置 chat/ask 的 memory
- `chat_service.py:148,276` - 所有模式的消息都执行持久化

**建议**: 在加载历史时按 mode 分流:
```python
async def _load_session_history(self) -> None:
    messages = await self._message_repo.list_by_session(...)
    self._memory.reset()
    self._conclude_memory.reset()
    for msg in messages:
        role = ...
        if msg.mode in (ModeType.CHAT, ModeType.ASK):
            self._memory.put(...)
        elif msg.mode in (ModeType.CONCLUDE, ModeType.EXPLAIN):
            self._conclude_memory.put(...)
```

### 问题三: 缺失消息历史 API 端点

**严重程度**: 功能缺失

**描述**: `GET /sessions/{session_id}/messages` 端点未实现。底层 `MessageRepository.list_by_session()` 已就绪，但无 API 路由暴露。前端无法获取历史对话记录。

**涉及代码**:
- `message_repo_impl.py:48-55` - `list_by_session()` 已实现
- `sessions.py` - 无对应路由
- `responses.py` - 无 `MessageResponse` / `MessageListResponse` 模型

**建议**: 需要新增:
1. `MessageResponse` 和 `MessageListResponse` 响应模型
2. `GET /sessions/{session_id}/messages` 路由（支持分页）
3. 对应的 Postman Collection 条目

### 问题四: docker compose down -v 后文档存储不一致

**严重程度**: 高 -- 数据一致性问题

**描述**: 执行 `docker compose down -v` 删除数据卷后，PostgreSQL 和 Elasticsearch 中的文档元数据、索引数据全部丢失，但存储在本机 `data/documents/` 目录下的 PDF 原文件、Markdown 转换结果、图片资产等仍然存在。这导致了"孤儿文件"问题：

- **数据库端**: 文档记录消失，library_id、notebook 关联、处理状态等全部丢失
- **文件系统端**: 以 document_id 命名的目录及其内容（original/、markdown/、assets/）继续占用磁盘

当前本机 `data/documents/` 目录结构：

```
data/documents/
  393f579b-.../          <-- 美国反对美国
    original/            <-- PDF 原文件
    markdown/            <-- MinerU 转换后的 Markdown
    assets/images/       <-- 提取的图片
    assets/meta/         <-- 元数据 JSON
  ea0e140d-.../          <-- 大模型基础
    ...
  3bebffae-.../          <-- 历史残留的孤儿目录
  aac6ccd4-.../          <-- 历史残留的孤儿目录
```

**根因分析**:

当前的存储架构中存在两层分离：

1. **Docker 卷内（可被 `-v` 删除）**: PostgreSQL 数据、Elasticsearch 索引、Redis 缓存
2. **宿主机绑定挂载（不受 `-v` 影响）**: `data/documents/` 通过 `./:/app` 挂载映射

`docker-compose.yml` 中 celery-worker 配置为 `- ./:/app`（整个项目目录挂载），`DOCUMENTS_DIR` 默认值为 `data/documents`（相对于 `/app`），这意味着文档实际写入宿主机的项目目录下而非 Docker 命名卷中。

**影响**:
- `docker compose down -v` 后重新启动，系统显示空的文档库，但磁盘上可能有数 GB 的孤儿文件
- 无法通过 API 访问或管理这些遗留文件
- 长期累积会浪费磁盘空间
- 若反复重建环境会导致文档 ID 冲突（概率极低但理论存在）

**建议方案**:

方案A -- 文档存储迁移至 Docker 命名卷:
```yaml
volumes:
  document_data:

services:
  celery-worker:
    volumes:
      - document_data:/app/data/documents
```
优点: `docker compose down -v` 时所有数据一致性销毁；备份和迁移更容易
缺点: 开发调试时不便直接在宿主机查看文档文件

方案B -- 启动时自动清理孤儿文件:
在应用启动时扫描 `data/documents/` 目录，对比数据库记录，清理不存在于数据库中的目录。
优点: 不改变现有存储架构
缺点: 需要额外的清理逻辑，且清理时机需要谨慎处理

方案C -- 混合方案（推荐）:
1. 保持当前宿主机挂载方式（开发友好）
2. 在 `docker compose down -v` 之前提供清理脚本 `scripts/cleanup_documents.sh`
3. 在应用启动时增加孤儿文件检测日志警告
4. 在 README 或运维文档中明确说明 `down -v` 的影响和清理步骤

---

## 测试结果汇总

### 按功能分类

| 功能 | 测试数 | 通过 | 需关注 | 未通过 |
|------|--------|------|--------|--------|
| Chat 自身记忆 | 2 | 2 | 0 | 0 |
| Chat -> Ask 记忆继承 | 1 | 1 | 0 | 0 |
| Ask -> Chat 记忆回传 | 2 | 2 | 0 | 0 |
| Explain 无状态 | 2 | 2 | 0 | 0 |
| Conclude 无状态 | 2 | 2 | 0 | 0 |
| 跨组隔离（核心记忆保护） | 1 | 1 | 0 | 0 |
| 跨组隔离（历史消息泄漏） | 1 | 0 | 1 | 0 |
| Session 间隔离 | 1 | 1 | 0 | 0 |
| Session 会话恢复 | 1 | 1 | 0 | 0 |
| **合计** | **13** | **12** | **1** | **0** |

### 问题追踪

| 编号 | 问题 | 严重程度 | 状态 |
|------|------|---------|------|
| P-01 | Conclude/Explain 共享记忆未实现（与设计偏差） | 设计偏差 | 待确认方向 |
| P-02 | `_load_session_history()` 跨模式消息泄漏 | 中等 | 待修复 |
| P-03 | `GET /sessions/{id}/messages` 端点缺失 | 功能缺失 | 待实现 |
| P-04 | `docker compose down -v` 后文档存储不一致 | 高 | 待确认方案 |

---

## 总体评价

后端四种对话模式的核心功能运行正常。Chat/Ask 共享记忆是系统最重要的功能，测试表明其工作稳定可靠。Session 会话恢复机制通过数据库持久化实现，隔离性和恢复完整性均符合预期。

需要重点关注的是 P-02（历史消息泄漏）和 P-04（文档存储一致性）两个问题，前者影响对话质量，后者影响数据完整性和运维体验。P-01 需要确认是否仍需按原设计实现 Conclude/Explain 共享记忆。
