# API 层

## 路由前缀

```
/api/v1/diagrams
```

## 端点列表

| 方法 | 路径 | 描述 | 调用方 |
|------|------|------|--------|
| GET | `/api/v1/diagrams` | 列出 notebook 下的图表 | 前端 Studio |
| GET | `/api/v1/diagrams/{diagram_id}` | 获取图表元数据 | 前端 Studio |
| GET | `/api/v1/diagrams/{diagram_id}/content` | 获取图表内容文件 | 前端渲染 |
| PATCH | `/api/v1/diagrams/{diagram_id}/positions` | 更新节点坐标 | 前端拖拽后防抖 |
| DELETE | `/api/v1/diagrams/{diagram_id}` | 删除图表 | 前端 Studio |

注：图表的创建和内容更新仅通过 Agent Skill 工具完成，无对应的 REST 写接口。

---

## GET /api/v1/diagrams

列出 notebook 下的图表元数据列表。

### 请求参数（Query）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `notebook_id` | string | 是 | Notebook ID |
| `document_id` | string | 否 | 按关联文档过滤 |

### 响应

```json
{
  "diagrams": [
    {
      "diagram_id": "d1b2c3...",
      "notebook_id": "nb-abc",
      "title": "大模型基础知识导图",
      "diagram_type": "mindmap",
      "format": "reactflow_json",
      "document_ids": ["doc-abc", "doc-def"],
      "created_at": "2026-03-18T10:00:00Z",
      "updated_at": "2026-03-18T12:30:00Z"
    }
  ],
  "total": 1
}
```

---

## GET /api/v1/diagrams/{diagram_id}

获取单张图表的元数据，包含节点坐标。

### 响应

```json
{
  "diagram_id": "d1b2c3...",
  "notebook_id": "nb-abc",
  "title": "大模型基础知识导图",
  "diagram_type": "mindmap",
  "format": "reactflow_json",
  "document_ids": ["doc-abc"],
  "node_positions": {
    "root": {"x": 0.0, "y": 0.0},
    "n1":   {"x": 200.0, "y": -80.0},
    "n2":   {"x": 200.0, "y": 80.0}
  },
  "created_at": "2026-03-18T10:00:00Z",
  "updated_at": "2026-03-18T12:30:00Z"
}
```

`node_positions` 为 null 时表示用户尚未调整坐标，前端使用 dagre 自动布局。

---

## GET /api/v1/diagrams/{diagram_id}/content

从 MinIO 获取图表内容文件，返回原始文本。

### 响应

`Content-Type: text/plain; charset=utf-8`

响应体为原始内容文本：

- `format = reactflow_json`：JSON 字符串
- `format = mermaid`：Mermaid 语法文本

---

## PATCH /api/v1/diagrams/{diagram_id}/positions

更新图表的节点坐标。由前端在用户拖拽结束后防抖（2 秒）调用。

### 请求体

```json
{
  "positions": {
    "root": {"x": 0.0,   "y": 0.0},
    "n1":   {"x": 250.0, "y": -100.0},
    "n2":   {"x": 250.0, "y":  100.0}
  }
}
```

### 响应

```json
{
  "diagram_id": "d1b2c3...",
  "updated_at": "2026-03-18T12:35:00Z"
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 400 | `DIAGRAM_FORMAT_MISMATCH` | 图表格式为 mermaid，不支持坐标更新 |
| 404 | `DIAGRAM_NOT_FOUND` | 图表不存在 |

---

## DELETE /api/v1/diagrams/{diagram_id}

删除图表（同时删除 MinIO 文件和数据库记录）。

此端点为前端 Studio UI 的直接删除操作提供支持，执行前前端须弹出确认对话框（由前端 UI 负责，不依赖 Agent 确认机制）。

### 响应

```json
{
  "diagram_id": "d1b2c3...",
  "deleted": true
}
```

### 错误

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `DIAGRAM_NOT_FOUND` | 图表不存在 |

---

## 通用错误码

| 错误码 | 状态码 | 含义 |
|--------|--------|------|
| `DIAGRAM_NOT_FOUND` | 404 | 指定图表不存在 |
| `DIAGRAM_TYPE_NOT_FOUND` | 400 | 图表类型未注册 |
| `DIAGRAM_VALIDATION_ERROR` | 422 | 图表内容格式校验失败（正常情况下仅 Agent 工具路径触发，REST API 不直接接收内容） |
| `DIAGRAM_FORMAT_MISMATCH` | 400 | 操作与图表格式不兼容 |
| `NOTEBOOK_NOT_FOUND` | 404 | 指定 Notebook 不存在 |

---

## 文件路由结构

```
newbee_notebook/api/routers/
└── diagrams.py    # 以上所有端点的路由定义
```

路由注册方式与现有 `documents.py`、`notes.py`（batch-3）保持一致。
