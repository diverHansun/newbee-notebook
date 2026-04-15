# 书签创建 422 问题说明

> 本文档仅用于问题说明与根因分析，不包含具体代码改造步骤。

---

## 1. 问题现象

在 Markdown Viewer 中选中文本后点击书签按钮，前端提示“书签创建失败”，服务端日志出现：

```
POST /api/v1/documents/{document_id}/marks 422 Unprocessable Entity
```

该问题导致用户无法完成书签标记，影响阅读链路中的“选中即标记”体验。

---

## 2. 复现与证据

### 2.1 复现前提

- 文档状态为 `converted` 或 `completed`（即文档本身可打标）
- 在阅读器中选择一段较长文本（超过 500 字符）
- 点击书签按钮

### 2.2 复现结果

后端返回 422，响应体为字段校验错误（节选）：

```json
{
  "detail": [
    {
      "type": "string_too_long",
      "loc": ["body", "anchor_text"],
      "msg": "String should have at most 500 characters",
      "ctx": { "max_length": 500 }
    }
  ]
}
```

### 2.3 结论

该 422 来自请求体字段校验失败，不是文档状态不满足导致的业务 422。

---

## 3. 前后端调用链

### 3.1 前端链路

1. 阅读器选中文本，触发 `SelectionMenu` 的 `onMark`。
2. `DocumentReader.handleMark` 将 `selectedText` 原样作为 `anchor_text` 与 `context_text` 发送。
3. 请求进入 `POST /api/v1/documents/{document_id}/marks`。

关键点：前端在发请求前没有对 `selectedText` 做最大长度约束。

### 3.2 后端链路

1. 路由 `create_mark` 接收 `CreateMarkRequest`。
2. `CreateMarkRequest` 对 `anchor_text` 的约束为 `min_length=1, max_length=500`。
3. 超过 500 字符时，在进入业务服务前即被 Pydantic 拒绝并返回 422。

---

## 4. 根因判定

### 4.1 主根因

前端可提交任意长度选中文本，而后端契约固定 `anchor_text <= 500`。当用户选择较长片段时，必然触发 422。

这是典型的“前端输入边界与后端契约不一致”问题。

### 4.2 次要问题（非本次 422 主因）

`char_offset` 由 `chunk.content.indexOf(selectedText)` 计算，当选区文本与 chunk 原文在空白折叠或跨节点场景下不完全一致时，`indexOf` 可能返回 `-1`，当前实现会回退到 `0` 偏移。

该问题不一定触发 422，但会导致书签位置不准确，是后续应关注的数据一致性风险。

---

## 5. 影响范围

1. 受影响模块：Studio 阅读器书签创建链路。
2. 受影响用户：在 Markdown Viewer 中进行大段选中并尝试打书签的用户。
3. 用户侧表现：书签失败且反馈信息不够具体。
4. 系统侧表现：日志持续出现 422，问题可重复。

---

## 6. 排除项

以下情况已排除为本次主因：

1. 文档未完成转换：该场景会走 `MarkDocumentNotReadyError`，同样是 422，但错误语义不同。
2. 路由字段命名不一致：前端发送字段与后端模型字段命名一致（`anchor_text`, `char_offset`, `context_text`）。
3. 数据库约束冲突：`marks` 表对 `anchor_text` 未设置长度上限，问题发生在请求校验层。

---

## 7. 分析结论

本问题属于接口契约边界未在调用端前置处理，导致的可预期校验失败。

后续优化应同时覆盖三件事：

1. 在前端建立输入边界感知，避免无意义请求。
2. 在后端统一错误语义，便于前端区分与提示。
3. 通过测试锁定“正常长度可创建、超长长度可解释”两类核心行为。
