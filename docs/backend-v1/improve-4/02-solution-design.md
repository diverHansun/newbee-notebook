# Improve-4 方案设计

## 1. 设计目标

1. 文档未就绪时返回结构化业务错误，而不是 500。
2. 文档处理状态按照状态机可观测、可解释。
3. 脚本目录分层清晰，命令入口统一。

## 2. 设计原则

1. **规范一致性**：对齐 ai-core-v1 错误码与响应格式。
2. **最小侵入**：不重构核心业务链路，只修正边界语义。
3. **前端友好**：返回可直接驱动 UI 状态的结构化字段。
4. **可迁移**：脚本方案兼容当前使用方式并提供过渡期。

## 3. 方案一：结构化错误响应（文档未就绪）

### 3.1 适用场景

当模式需要文档检索能力且 Notebook 关联文档尚未就绪时触发。

建议覆盖：

1. `ask`
2. `explain`
3. `conclude`

`chat` 模式保持现有行为（可无 RAG 回答），不强制拦截。

### 3.2 返回契约

HTTP 状态码：`409`

响应体：

```json
{
  "error_code": "E4001",
  "message": "文档正在处理中，请稍后重试",
  "details": {
    "mode": "ask",
    "notebook_id": "xxx",
    "blocking_document_ids": ["doc-a", "doc-b"],
    "documents_by_status": {
      "uploaded": 1,
      "pending": 1,
      "processing": 1,
      "completed": 0,
      "failed": 0
    },
    "retryable": true
  }
}
```

### 3.3 实现要点

1. 服务层统一进行“模式可用性检查”，避免检索层异常冒泡。
2. API 层对业务异常统一映射，未知异常统一落到 `E1000`。
3. SSE 路径同样返回标准错误事件，`error_code` 与非流式一致。

## 4. 方案二：文档处理状态机与提交策略

## 4.1 状态定义

1. `uploaded`：已上传，尚未入队。
2. `pending`：已入队，等待 Worker 执行。
3. `processing`：Worker 已领取并执行中。
4. `completed`：处理成功并索引完成。
5. `failed`：处理失败。

## 4.2 状态流转

```text
uploaded -> pending -> processing -> completed
                                 -> failed
failed -> pending -> processing -> completed/failed
```

约束：

1. 禁止 `completed` 回退到 `processing`（管理端强制重建除外）。
2. `processing` 必须由 Worker“领取任务”后写入。

## 4.3 提交策略（关键）

将状态写入与长耗时处理解耦为短事务：

1. 入队时写 `pending` 并提交。
2. Worker 开始前原子更新为 `processing` 并提交。
3. 长耗时步骤（转换、embedding、索引）独立执行。
4. 结束后写 `completed` 或 `failed` 并提交。

这样可保证轮询接口实时看到中间状态。

## 4.4 并发与幂等

1. Worker 领取时使用条件更新，避免多 Worker 重复处理同一文档。
2. 若文档已是 `processing/completed`，重复任务直接跳过。
3. `reprocess` 场景显式重置状态并记录操作者来源。

## 5. 方案三：脚本分层规范

## 5.1 目录职责

1. `newbee_notebook/scripts`：后端内部脚本（索引重建、DB相关）。
2. `frontend/scripts`：前端工程脚本（构建、联调、mock 等）。
3. `scripts`：全局入口脚本（用户直接运行、跨模块编排）。

## 5.2 调用约定

1. 后端脚本标准入口：`python -m newbee_notebook.scripts.<script_name>`
2. 全局脚本用于：
   - 上传辅助（如 `upload_documents.py`）
   - 环境/服务编排（如 `up-mineru.ps1`）
   - 调用后端/前端脚本的薄包装入口（可选）

## 5.3 兼容策略

1. 保留现有高频命令，新增统一入口文档。
2. 对历史命令标注“兼容保留/推荐替代”。
3. 后续阶段（前端接入）按同一规范扩展 `frontend/scripts`。

## 6. 观测与日志补充

建议补充结构化日志字段：

1. `document_id`
2. `from_status`
3. `to_status`
4. `task_id`
5. `duration_ms`
6. `error_code`（失败时）

用于快速定位“卡 pending”“长时间 processing”“错误码分布”。

