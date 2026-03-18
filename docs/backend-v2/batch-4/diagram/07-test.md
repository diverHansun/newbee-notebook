# 测试策略

## 测试层次

```
单元测试
  DiagramTypeRegistry：校验器、描述符查询
  DiagramService：各方法的业务逻辑（mock repository + storage）
  Agent 工具：每个 tool.execute() 的输出结构

集成测试
  DiagramService + PostgresDiagramRepository + 真实数据库
  DiagramService + MinIO（本地或 mock）
  Agent 工具 → DiagramService → Repository（端到端工具链）

API 测试
  各 REST 端点的请求/响应结构与错误码
```

## 单元测试

### DiagramTypeRegistry

```
validate_reactflow_schema()
  - 合法 JSON + 合规结构 → 不抛异常
  - 非法 JSON → DiagramValidationError（含"JSON 解析失败"）
  - 缺少 nodes 字段 → DiagramValidationError
  - 缺少 edges 字段 → DiagramValidationError
  - node 缺少 label → DiagramValidationError
  - node 包含 position 字段 → DiagramValidationError（提示移除）
  - 空 nodes 数组 → 通过（合法空图）

get_descriptor()
  - 已注册类型 "mindmap" → 返回 DiagramTypeDescriptor
  - 未注册类型 "unknown" → DiagramTypeNotFoundError

get_all_slash_commands()
  - 返回列表包含 "/mindmap"
```

### DiagramService

```
create_diagram()
  - 合法内容 → 调用 storage.write_text 和 repository.save，返回 Diagram
  - 非法内容 → 抛出 DiagramValidationError，不触发 storage 写操作
  - diagram_type 未注册 → 抛出 DiagramTypeNotFoundError

update_diagram_content()
  - 合法内容 → 覆写 MinIO 文件，更新 updated_at，node_positions 不变
  - 非法内容 → 抛出 DiagramValidationError
  - diagram_id 不存在 → 抛出 DiagramNotFoundError

update_node_positions()
  - reactflow_json 格式图表 → 更新 node_positions
  - mermaid 格式图表 → 抛出 DiagramFormatMismatchError

delete_diagram()
  - 存在的 diagram → 先删 MinIO，再删数据库记录
  - MinIO 删除失败（文件已不存在）→ 记录警告日志，继续删除数据库记录
  - diagram_id 不存在 → 抛出 DiagramNotFoundError
```

### Agent 工具 execute 函数

```
create_diagram tool
  - service.create_diagram 成功 → ToolCallResult.error 为 None，metadata 含 diagram_id
  - service 抛出 DiagramValidationError → ToolCallResult.error 非空，content 为空

update_diagram tool
  - service.update_diagram_content 成功 → ToolCallResult.error 为 None
  - service 抛出 DiagramNotFoundError → ToolCallResult.error 含图表 ID

delete_diagram tool
  - service.delete_diagram 成功 → ToolCallResult.content 含"已删除"
  - service 抛出 DiagramNotFoundError → ToolCallResult.error 非空
```

## 集成测试

### DiagramService + Repository

```
创建图表后可按 notebook_id 查询到
创建图表后内容文件存在于 MinIO 对应路径
更新坐标后 node_positions 持久化，不影响 content_path
删除图表后数据库记录和 MinIO 文件均不存在
删除 Notebook 后，关联图表级联删除（CASCADE 验证）
删除 Document 后，关联图表的 document_ids 中移除该 document_id
```

### Agent 重试场景

```
Agent 第一次输出非法 JSON → create_diagram 返回 error
Agent 第二次输出合法 JSON → 创建成功
（模拟 2 次调用，验证错误信息能正确传递给 Agent）

Agent 连续 3 次输出非法内容 → 第 3 次仍失败，AgentLoop 进入 synthesizing 告知用户
```

## API 测试

```
GET /api/v1/diagrams?notebook_id=X
  - 返回该 notebook 下所有图表
  - document_id 过滤参数有效

GET /api/v1/diagrams/{id}/content
  - 返回 MinIO 文件原始内容
  - 不存在的 id → 404

PATCH /api/v1/diagrams/{id}/positions
  - 合法 positions 结构 → 200，node_positions 更新
  - mermaid 格式图表 → 400 DIAGRAM_FORMAT_MISMATCH
  - 不存在的 id → 404

DELETE /api/v1/diagrams/{id}
  - 成功 → 200，diagram_id + deleted: true
  - 不存在的 id → 404
```

## 测试数据说明

- 测试用的 reactflow_json 内容使用固定的小型思维导图（3-5 节点），不依赖真实 RAG 输出
- 非法内容测试用例应覆盖：非 JSON、缺字段、类型错误、包含 position 字段等多种情况
- Agent 重试测试使用 mock LLMClient，预置多轮对话结果
