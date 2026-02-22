# 03 - View 按钮状态判断逻辑

## 当前问题

用户反馈: View 按钮应在文档状态变为 converted（MinerU 处理完成，Markdown 文件已生成）后即可使用，
无需等待后续的 RAG 索引和 ES 索引完成。

## 根因分析

### 前端逻辑（已正确）

**View 按钮启用条件** (`frontend/src/components/sources/source-card.tsx:11-12`):

```typescript
function canViewDocument(status: string) {
  return status === "completed" || status === "converted";
}
```

逻辑正确: converted 和 completed 状态均可查看。

**内容获取条件** (`frontend/src/components/reader/document-reader.tsx:44`):

```typescript
const canReadByStatus = status === "completed" || status === "converted";
```

同样正确。

### 后端历史问题（已修复）

**修复前**（`document_service.py` 旧代码）:

```python
# 旧逻辑：CONVERTED 被阻止
if doc.status in {
    DocumentStatus.UPLOADED,
    DocumentStatus.PENDING,
    DocumentStatus.PROCESSING,
    DocumentStatus.CONVERTED,  # 阻止了 converted 状态
}:
    raise DocumentProcessingError(...)  # E4001, HTTP 409
```

**修复后**（提交 `224b968`，当前代码）:

```python
# 新逻辑：仅阻止真正未完成转换的状态
if doc.status in {
    DocumentStatus.UPLOADED,
    DocumentStatus.PENDING,
    DocumentStatus.PROCESSING,
    # CONVERTED 已移除，不再阻止
}:
    raise DocumentProcessingError(...)

# 明确允许 CONVERTED 和 COMPLETED
if doc.status not in {DocumentStatus.CONVERTED, DocumentStatus.COMPLETED}:
    raise RuntimeError("Document not processed yet")
```

位置: `newbee_notebook/application/services/document_service.py:243-261`

### 自愈机制

后端增加了 content_path 自愈功能（`document_service.py:263-276`）：
当文件存在于磁盘但 content_path 为空时，自动探测并回填路径，
避免后续请求重复磁盘查找。探测候选路径包括：

1. 数据库中记录的 content_path
2. 去除 `documents/` 前缀的路径（兼容旧数据）
3. 约定路径 `{document_id}/markdown/content.md`

### 文档状态流转与内容可用性

```
uploaded -> pending -> processing -> converted -> completed
                                       |              |
                              可查看内容 |     可查看内容 |
                          索引进行中     |     全部完成   |
```

后端处理子阶段（processing 状态内部）:

```
queued -> converting -> splitting -> indexing_pg -> indexing_es -> finalizing
                           |
                   转换完成后状态变为 converted
                   后续索引阶段在 converted 状态下继续
```

### 前端轮询机制

前端通过 3 秒间隔的轮询检测状态变化 (`source-list.tsx:30-36`)。
converted 被归类为非终态（继续轮询），这是正确的行为:
文档虽然可以查看，但索引尚未完成，状态仍在变化中。

### 前端防御性错误处理

`document-reader.tsx` 中保留了对 E4001 + converted 场景的错误提示:

```typescript
if (err.errorCode === "E4001" && status === "converted") {
  return "文档处于 converted 状态，但后端当前仍将其视为处理中，暂不可预览。";
}
```

此代码现在不应再触发（后端已允许 converted 获取内容），但作为防御性代码可保留。

## 结论

**前后端逻辑均已正确，此问题已在提交 `224b968` 中修复。**

当前状态: 已修复，无需额外代码改动。

## 待确认事项

请确认以下场景是否仍可复现:

1. 上传新文档，等待状态变为 converted
2. 此时 View 按钮是否可点击
3. 点击后是否能正常显示 Markdown 内容

如果仍可复现，问题可能出在:
- 后端 content_path 字段在 converted 状态下未及时设置（自愈机制应能兜底）
- 或前端轮询未能及时获取到最新状态
