# Improve-6 测试计划

本文档定义每个改动项的测试用例、预期结果和回归检查策略。

---

## 1. 测试范围总览

| 改动项 | 对应任务 | 测试类型 |
|--------|---------|---------|
| MessageRepository 接口扩展 | T1 | 单元测试 |
| 分流加载 + 双记忆重命名 | T2 | 集成测试 |
| Messages API 端点 | T3 | API 测试 |
| ExplainMode 迁移 | T4 | 单元 + 集成 |
| ConcludeMode 迁移 | T5 | 单元 + 集成 |
| EC 上下文开关 | T6 | 端到端测试 |
| 删除逻辑拆分 | T7 | API + 集成测试 |
| make clean-doc + 孤儿检测 | T8 | 手动 + 脚本测试 |

---

## 2. T1: MessageRepository 接口扩展

### 2.1 list_by_session -- modes 过滤

```
TC-1.1: 传入 modes=[CHAT, ASK]，仅返回 chat 和 ask 消息
TC-1.2: 传入 modes=[EXPLAIN, CONCLUDE]，仅返回 explain 和 conclude 消息
TC-1.3: 传入 modes=None，返回所有消息(向后兼容)
TC-1.4: 传入 modes=[]，返回空列表
TC-1.5: 传入 modes=[CHAT]，只返回 chat 消息
```

### 2.2 list_by_session -- 分页

```
TC-1.6: limit=10, offset=0，返回前 10 条
TC-1.7: limit=10, offset=10，返回第 11-20 条
TC-1.8: limit=10, offset=超过总数，返回空列表
TC-1.9: offset=0 时与现有行为一致
```

### 2.3 count_by_session

```
TC-1.10: 无 modes 过滤，返回总消息数
TC-1.11: modes=[CHAT]，返回 chat 消息数
TC-1.12: session 无消息，返回 0
TC-1.13: session 不存在，返回 0 (不抛异常)
```

### 2.4 测试数据准备

预插入一个 session 的消息:
- 10 条 CHAT 消息
- 5 条 ASK 消息
- 3 条 EXPLAIN 消息
- 2 条 CONCLUDE 消息

---

## 3. T2: 分流加载 + 双记忆重命名

### 3.1 记忆隔离验证

```python
# test_session_memory_isolation.py

TC-2.1: 新建 session -> chat 3 轮 -> explain 2 轮
        断言: _memory 中仅有 6 条消息(3 user + 3 assistant，均为 CHAT)
        断言: _ec_memory 中仅有 4 条消息(2 user + 2 assistant，均为 EXPLAIN)

TC-2.2: 新建 session -> explain 1 轮 -> chat 1 轮 -> explain 1 轮
        断言: _memory 中仅有 CHAT 消息
        断言: _ec_memory 中有 2 轮 EXPLAIN 消息

TC-2.3: 加载已有 session(DB 中存在混合模式消息)
        断言: 加载后 _memory 和 _ec_memory 分别只包含对应模式的消息
```

### 3.2 边界情况

```
TC-2.4: session 中仅有 CHAT 消息 -> _ec_memory 为空
TC-2.5: session 中仅有 EXPLAIN 消息 -> _memory 为空
TC-2.6: session 无任何消息 -> 两个 memory 均为空
TC-2.7: end_session() 后两个 memory 均被重置
```

### 3.3 回归检查

```
TC-2.8: Chat 多轮对话能力不受影响(5 轮内有上下文)
TC-2.9: Ask 模式的检索质量不受影响
TC-2.10: _ec_memory 的 token_limit=2000 约束生效(超出时自动裁剪旧消息)
```

---

## 4. T3: Messages API 端点

### 4.1 正常路径

```
TC-3.1: GET /sessions/{id}/messages
        期望: 200, 返回所有消息(按时间升序)

TC-3.2: GET /sessions/{id}/messages?mode=chat,ask
        期望: 200, 仅返回 chat 和 ask 消息

TC-3.3: GET /sessions/{id}/messages?mode=explain
        期望: 200, 仅返回 explain 消息

TC-3.4: GET /sessions/{id}/messages?limit=5&offset=0
        期望: 200, 返回前 5 条，pagination.total 为实际总数

TC-3.5: GET /sessions/{id}/messages?limit=5&offset=5
        期望: 200, 返回第 6-10 条
```

### 4.2 边界情况

```
TC-3.6: GET /sessions/{不存在的ID}/messages
        期望: 404, {"detail": "Session not found"}

TC-3.7: GET /sessions/{id}/messages?mode=invalid_mode
        期望: 400, 提示无效的 mode 值

TC-3.8: GET /sessions/{空session}/messages
        期望: 200, items=[], pagination.total=0

TC-3.9: GET /sessions/{id}/messages?limit=0
        期望: 400 或使用默认 limit

TC-3.10: GET /sessions/{id}/messages?limit=-1
         期望: 400, 参数校验失败
```

### 4.3 响应结构验证

```
TC-3.11: 验证 MessageResponse 结构:
         {
           "id": "uuid",
           "session_id": "uuid",
           "role": "user|assistant",
           "mode": "chat|ask|explain|conclude",
           "content": "string",
           "metadata": {...},
           "created_at": "datetime"
         }

TC-3.12: 验证 MessageListResponse 结构:
         {
           "items": [MessageResponse],
           "pagination": {
             "total": int,
             "limit": int,
             "offset": int
           }
         }
```

---

## 5. T4 / T5: ExplainMode / ConcludeMode 迁移

### 5.1 ExplainMode 基本功能

```
TC-4.1: Explain 单轮 -- 选中文本 + 提问，返回解释结果
        断言: response 非空, source_nodes 存在

TC-4.2: Explain 多轮 -- 第 1 轮解释 "量子纠缠"，第 2 轮追问 "再详细说说"
        断言: 第 2 轮回答引用了第 1 轮的量子纠缠上下文

TC-4.3: Explain 流式 -- stream=true，验证 token 逐步输出
        断言: 至少收到 5 个 streaming chunk

TC-4.4: Explain 第 6 轮(超出 5 轮窗口)
        断言: token_limit 裁剪生效，不抛异常
```

### 5.2 ConcludeMode 基本功能

```
TC-5.1: Conclude 单轮 -- 对某文档进行总结
        断言: 返回结构化总结内容

TC-5.2: Conclude 多轮 -- 第 1 轮总结，第 2 轮要求 "用更简洁的语言重新总结"
        断言: 第 2 轮的总结与第 1 轮形成对比和修改关系

TC-5.3: Conclude 流式 -- stream=true
        断言: token 逐步输出

TC-5.4: Conclude 总结质量对比
        断言: 与迁移前的同一文档总结结果进行人工对比，质量不低于迁移前
```

### 5.3 双模式共享 _ec_memory

```
TC-5.5: Explain 1 轮 -> Conclude 1 轮(同一 session)
        断言: _ec_memory 中包含 Explain 和 Conclude 的消息

TC-5.6: Explain 3 轮 -> Conclude 3 轮(同一 session)
        断言: Conclude 可以引用 Explain 阶段提到的概念

TC-5.7: Explain 5 轮 -> Conclude 5 轮 (共 10 轮)
        断言: _ec_memory token_limit 生效，早期消息被裁剪
```

### 5.4 回归: Chat/Ask 不受影响

```
TC-5.8: Chat 模式 5 轮对话，上下文连贯性不受 T4/T5 改动影响
TC-5.9: Ask 模式单次查询，检索质量不变
TC-5.10: 混合使用: Chat 3 轮 -> Explain 2 轮 -> Chat 2 轮
         断言: Chat 的 _memory 中只有 Chat 消息，不包含 Explain 消息
```

---

## 6. T6: EC 上下文开关

### 6.1 默认行为(关闭)

```
TC-6.1: Session.include_ec_context 默认 false
        Explain 2 轮 -> Chat 提问 "我们刚才讨论了什么"
        断言: Chat 回答不引用 Explain 内容

TC-6.2: 创建 Session 不传 include_ec_context
        断言: SessionResponse.include_ec_context == false
```

### 6.2 开启行为

```
TC-6.3: Session 级开启: include_ec_context=true
        Explain 2 轮解释 "量子纠缠" -> Chat 提问 "结合之前的理解回答"
        断言: Chat 回答能够引用量子纠缠相关概念

TC-6.4: 请求级开启: Session 级 false，请求中 include_ec_context=true
        断言: 该次请求可以引用 EC 内容，后续请求(不传)恢复为 false

TC-6.5: 请求级关闭: Session 级 true，请求中 include_ec_context=false
        断言: 该次请求不引用 EC 内容

TC-6.6: 优先级验证: Session 级 true，请求级 false
        断言: 请求级 false 生效
```

### 6.3 无 EC 历史时

```
TC-6.7: Session 级 true，但无任何 Explain/Conclude 消息
        断言: Chat 正常工作，不注入任何 EC 摘要

TC-6.8: Session 级 true，Explain 1 轮(内容很少)
        断言: EC 摘要内容精简，不影响 Chat 质量
```

### 6.4 EC 摘要 Token 约束

```
TC-6.9: Explain 10 轮(大量内容)后开启 EC 摘要注入
        断言: 注入的摘要 token 数不超过设定上限(约 500 tokens)
        断言: 不导致 Chat system prompt 超长
```

---

## 7. T7: 删除逻辑拆分

### 7.1 DELETE /documents/{id} (软删除)

```
TC-7.1: 删除存在的文档
        期望: 200
        断言: Elasticsearch 索引已清除
        断言: PostgreSQL 记录已删除
        断言: data/documents/{id}/ 目录仍存在

TC-7.2: 删除不存在的文档
        期望: 404

TC-7.3: 删除后再次 GET /documents/{id}
        期望: 404(DB 记录已不在)

TC-7.4: 删除后检查该文档的所有 notebook 关联已清除
```

### 7.2 DELETE /library/documents/{id} (带 force 参数)

```
TC-7.5: force=false(默认)
        断言: 与 TC-7.1 行为一致(软删除)

TC-7.6: force=true
        断言: 所有内容删除 + data/documents/{id}/ 目录已删除

TC-7.7: force 不传
        断言: 默认 false，执行软删除

TC-7.8: force=true 删除后，data/documents/ 下无该 ID 目录
```

### 7.3 DELETE /notebooks/{nid}/documents/{did}

```
TC-7.9: 取消关联后，notebook 文档列表不再包含该文档
        断言: 文档本身仍存在(GET /documents/{did} 返回 200)
        断言: 文件系统无变化

TC-7.10: notebook 不包含该文档时执行取消关联
         期望: 404 或幂等处理
```

### 7.4 回归: 全链路删除

```
TC-7.11: 上传文档 -> 加入 notebook -> 从 notebook 移除 -> 软删除 -> 硬删除
         每步验证各层状态(DB/ES/文件系统)
```

---

## 8. T8: make clean-doc + 孤儿检测

### 8.1 make clean-doc 正常流程

```
TC-8.1: 准备一个 data/documents/{valid-uuid}/ 目录
        执行: make clean-doc ID={valid-uuid}
        断言: 该目录被删除
        断言: 其他文档目录不受影响

TC-8.2: Windows 环境下执行 PowerShell 脚本
        执行: .\scripts\clean-doc.ps1 -ID {valid-uuid}
        断言: 行为与 make 版一致
```

### 8.2 安全校验

```
TC-8.3: 不提供 ID
        执行: make clean-doc
        断言: 输出错误提示，不执行任何删除

TC-8.4: 提供无效格式的 ID
        执行: make clean-doc ID=not-a-uuid
        断言: UUID 格式校验失败，不执行删除

TC-8.5: 提供不存在的有效 UUID
        执行: make clean-doc ID=00000000-0000-0000-0000-000000000000
        断言: 提示目录不存在，不报错

TC-8.6: 尝试路径遍历攻击
        执行: make clean-doc ID=../../etc
        断言: UUID 格式校验失败，不执行删除
```

### 8.3 孤儿检测

```
TC-8.7: 准备状态: DB 中有文档 A、B 的记录，data/documents/ 下有 A/、B/、C/ 目录
        执行: detect_orphan_documents()
        断言: 日志输出 "发现 1 个孤儿目录: C"

TC-8.8: 无孤儿时
        断言: 日志输出 "未发现孤儿文档目录"

TC-8.9: make clean-orphans 执行
        断言: 列出所有孤儿目录
        断言: 确认后删除
        断言: 删除后再次检测，返回 0 个孤儿
```

---

## 9. 回归测试检查清单

以下检查确保 improve-6 的改动不影响 improve-1 到 improve-5 的已有功能:

### 9.1 文档上传与解析

```
REG-01: 上传 PDF 文档，解析成功
REG-02: 上传 Markdown 文档，解析成功
REG-03: 打开 MinerU 解析流程，Celery 任务正常执行
REG-04: 解析后的 chunks 正确写入 Elasticsearch
```

### 9.2 Notebook 管理

```
REG-05: 创建 Notebook，返回正确
REG-06: 向 Notebook 添加文档
REG-07: 列出 Notebook 文档列表
REG-08: Notebook 搜索功能
```

### 9.3 Chat/Ask 模式

```
REG-09: Chat 单轮对话
REG-10: Chat 多轮对话(5 轮内上下文连贯)
REG-11: Ask 单次查询，source_nodes 返回正常
REG-12: 流式响应正常
```

### 9.4 Session 生命周期

```
REG-13: 创建 Session
REG-14: 列出所有 Session
REG-15: 获取 Session 详情
REG-16: 删除 Session
REG-17: 获取最近 Session
```

### 9.5 Docker / 部署

```
REG-18: docker-compose up 正常启动
REG-19: bind mount 卷正常映射
REG-20: 容器重启后数据持久化
```

---

## 10. 测试执行策略

### 10.1 测试框架

- 单元测试: pytest + unittest.mock
- API 测试: pytest + httpx.AsyncClient (TestClient)
- 集成测试: pytest + 测试数据库(SQLite 或测试用 PostgreSQL)

### 10.2 执行顺序

```
1. T1 单元测试 (MessageRepository)
2. T2 集成测试 (记忆隔离)
3. T3 API 测试 (Messages 端点)
4. T7 API + 集成测试 (删除逻辑)
5. T4/T5 集成测试 (模式迁移)
6. T6 端到端测试 (EC 开关)
7. T8 手动测试 (脚本)
8. 全量回归 (REG-01 ~ REG-20)
```

### 10.3 测试文件组织

```
newbee_notebook/tests/
  improve_6/
    test_message_repository.py    # TC-1.x
    test_session_memory.py        # TC-2.x
    test_messages_api.py          # TC-3.x
    test_explain_mode.py          # TC-4.x
    test_conclude_mode.py         # TC-5.x
    test_ec_context_switch.py     # TC-6.x
    test_deletion_endpoints.py    # TC-7.x
    conftest.py                   # 共享 fixtures
```

T8 的测试(make clean-doc、孤儿检测)以手动执行 + 截图记录为主，不纳入自动化测试套件。

### 10.4 通过标准

- 所有自动化测试用例通过
- 回归测试 REG-01 ~ REG-20 无失败
- T4/T5 的总结质量人工评估不低于迁移前水平
- 无新增 lint 或 type check 警告
