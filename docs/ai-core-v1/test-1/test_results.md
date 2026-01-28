# MediMind Agent - Conclude/Explain Mode 测试报告

## 测试环境
- 日期: 2026-01-27
- API Base URL: http://localhost:8000/api/v1
- Notebook ID: 8776194a-a0a1-48a8-8ddb-ed6700a10c0f
- Session ID: 0ada165a-51f0-4761-bd44-e16abffd52dc

## 测试用例

### 1. 健康检查 ```bash
curl -X GET "http://localhost:8000/api/v1/health"
# Response: {"status":"ok"}

curl -X GET "http://localhost:8000/api/v1/info"
# Response: 支持的模式包括: chat, ask, explain, conclude
```

### 2. Chat模式（基础对话）```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello! What can you help me with?", "mode": "chat", "session_id": "{session_id}"}'
```
**结果**: 成功返回响应，功能正常

### 3. Explain模式 - 无文档/无Context  (预期失败)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is machine learning?", "mode": "explain", "session_id": "{session_id}"}'
```
**结果**:
- HTTP 400 Bad Request
- Error: "Conclude/Explain mode requires at least one processed document or a selected_text context."
- **验证通过** - 错误处理正确

### 4. Conclude模式 - 无文档/无Context  (预期失败)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Please summarize the key points", "mode": "conclude", "session_id": "{session_id}"}'
```
**结果**:
- HTTP 400 Bad Request
- Error: "Conclude/Explain mode requires at least one processed document or a selected_text context."
- **验证通过** - 错误处理正确

### 5. Explain模式 - 带Context  (部分问题)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is machine learning?",
    "mode": "explain",
    "session_id": "{session_id}",
    "context": {
      "selected_text": "Machine learning is a subset of artificial intelligence..."
    }
  }'
```
**结果**:
-  HTTP 200 - 请求成功
-  返回了解释性响应
-  **问题**: sources中的文档与用户提供的context无关
  - 返回的sources来自"Clean Code"软件开发书籍
  - 与用户提供的AI/机器学习文本不相关

### 6. Conclude模式 - 带Context  (部分问题)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Please summarize this text",
    "mode": "conclude",
    "session_id": "{session_id}",
    "context": {
      "selected_text": "Artificial Intelligence (AI) is revolutionizing healthcare..."
    }
  }'
```
**结果**:
-  HTTP 200 - 请求成功
-  返回了总结性响应
-  **问题**: sources中的文档与用户提供的context无关
  - 返回的sources来自"Clean Code"软件开发书籍
  - 与用户提供的医疗AI文本不相关

### 7. Streaming响应测试 ```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/notebooks/{notebook_id}/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "message": "What is AI?",
    "mode": "explain",
    "session_id": "{session_id}",
    "context": {"selected_text": "Artificial Intelligence refers to..."}
  }'
```
**结果**:
-  SSE流式传输正常工作
-  接收到start, content, sources, done事件
-  响应内容完整
-  sources问题同上

## 核心问题分析

### 问题1: Context与RAG检索的不一致

**期望行为**:
- 前端用户在文档阅读器中选中文本
- 发送`context.selected_text`到后端
- Conclude/Explain模式基于这段选中的文本进行总结或解释
- 返回的sources应该包含或关联到用户选中的文本

**实际行为**:
- Context参数可以绕过"需要文档"的验证
- 但RAG检索仍然从向量数据库中检索
- 返回的sources与用户context无关（如果数据库中有其他文档）

**代码位置**:
- `medimind_agent/application/services/chat_service.py:344-348` - 验证逻辑
- `medimind_agent/core/engine/modes/explain_mode.py:128-160` - Explain处理逻辑
- `medimind_agent/core/engine/modes/conclude_mode.py:121-156` - Conclude处理逻辑

### 问题2: 设计意图 vs 实现

**从代码注释可以看出设计意图**:

```python
# conclude_mode.py:1-9
"""Conclude mode implementation using ChatEngine.

This mode provides document summarization and conclusion generation:
- ChatEngine with condense_plus_context mode
- RAG for retrieving relevant documents
- Optimized for summarization tasks

No conversation memory - each query is treated independently.
"""
```

**但实际使用场景**:
1. **有文档的场景**:
   - Notebook中已上传并处理完成的文档
   - 使用RAG检索相关内容  正常工作

2. **前端选中文本场景** (当前有问题):
   - 用户在前端文档阅读器选中文本
   - 发送selected_text
   - 期望基于这段文本生成总结/解释
   -  但仍然会从向量数据库检索不相关内容

### 问题3: _get_context_chunks方法的问题

**代码分析** (`chat_service.py:360-413`):
```python
async def _get_context_chunks(self, context: dict) -> List[dict]:
    """Fetch chunk and neighbors by chunk_id for richer context."""
    if not context or not context.get("chunk_id") or not self._vector_index:
        return []
    # ... 使用chunk_id从向量数据库检索相邻chunks
```

**问题**:
- 如果context中没有chunk_id，方法返回空列表
- 前端发送的selected_text没有被直接使用
- 只有当文本已经在向量数据库中indexed时才能工作

## 建议的修复方案

### 方案1: 修改Explain/Conclude模式以支持纯Context模式

在`explain_mode.py`和`conclude_mode.py`中添加逻辑:
```python
async def _process(self, message: str, context: Optional[dict] = None) -> str:
    # 如果提供了context.selected_text但没有向量索引或文档
    if context and context.get("selected_text") and not self.allowed_doc_ids:
        # 直接基于selected_text + message生成响应
        # 不使用RAG检索
        prompt = f"Context: {context['selected_text']}\n\nQuestion: {message}"
        response = await self._llm.acomplete(prompt)
        return str(response)

    # 否则使用现有的RAG逻辑
    # ...
```

### 方案2: 在chat_service中改进Context处理

修改`_get_context_chunks`方法:
```python
async def _get_context_chunks(self, context: dict) -> List[dict]:
    """Fetch chunk and neighbors, or use selected_text directly."""
    if not context:
        return []

    # 如果有selected_text但没有chunk_id，直接返回selected_text作为chunk
    if context.get("selected_text") and not context.get("chunk_id"):
        return [{
            "document_id": context.get("document_id"),
            "chunk_id": "user_selection",
            "text": context.get("selected_text"),
            "title": "User Selected Text",
            "score": 1.0,
        }]

    # 否则使用现有的向量检索逻辑
    # ...
```

### 方案3: 添加新的"纯Context"模式

创建一个新的模式专门处理前端选中文本:
- `explain_selection` - 解释选中的文本
- `conclude_selection` - 总结选中的文本

这样可以:
- 保持现有explain/conclude的RAG功能不变
- 为前端文本选择提供专门的处理路径
- 更清晰的API语义

## 测试建议

### 短期测试（验证当前功能）:
1.  使用context.selected_text可以绕过"需要文档"的验证
2.  Streaming响应正常工作
3.  需要明确sources的来源和相关性

### 长期测试（集成测试）:
1. 上传真实文档到notebook
2. 等待文档处理完成
3. 测试基于已处理文档的explain/conclude
4. 验证前端集成时的完整工作流

## 总结

**功能状态**:
-  基本功能正常
-  错误处理正确
-  Streaming工作正常
-  Context使用存在设计不一致

**需要改进的地方**:
1. Explain/Conclude模式在只有context.selected_text时的行为
2. Sources的相关性和来源
3. 前端集成的清晰文档说明

**推荐行动**:
1. 确认产品需求: Context模式是为了什么场景?
2. 选择并实施上述修复方案之一
3. 添加单元测试覆盖context场景
4. 更新API文档说明context参数的使用
