# 数据模型

## 数据库表：diagrams

```sql
CREATE TABLE diagrams (
    diagram_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id     UUID        NOT NULL REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
    title           TEXT        NOT NULL,
    diagram_type    TEXT        NOT NULL,
    -- 已注册类型：'mindmap'
    -- 预留类型：'flowchart' | 'sequence' | 'gantt'（未来 batch 注册后生效）
    format          TEXT        NOT NULL CHECK (format IN ('reactflow_json', 'mermaid')),
    content_path    TEXT        NOT NULL,
    -- MinIO 路径，格式见下方存储路径说明
    document_ids    UUID[]      NOT NULL DEFAULT '{}',
    -- 关联的文档 ID 列表，对应生成图表时的文档作用域
    node_positions  JSONB,
    -- 用户拖拽调整的节点坐标，仅 reactflow_json 格式使用
    -- 结构：{"node_id": {"x": 120.5, "y": 80.0}, ...}
    -- mermaid 格式此字段始终为 NULL
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_diagrams_notebook_id  ON diagrams(notebook_id);
CREATE INDEX idx_diagrams_document_ids ON diagrams USING GIN(document_ids);
```

### 设计说明

- `diagram_type` 不加 CHECK 约束，由应用层 DiagramTypeRegistry 控制合法性，避免新增类型时需要执行 DB migration
- `format` 仅有两种值，加 CHECK 约束保证数据完整性
- `node_positions` 与 MinIO 中的内容文件分离：Agent 更新图表内容时只覆写 MinIO 文件，不影响 `node_positions`；用户拖拽时只更新 `node_positions`，不触发 MinIO 写操作
- `document_ids` 使用 GIN 索引，支持按文档 ID 反查关联图表

### 级联规则

| 触发操作 | 行为 |
|---------|------|
| 删除 Notebook | CASCADE 删除所有关联 diagrams 数据库记录，同时删除对应 MinIO 文件 |
| 删除 Document | 从关联图表的 `document_ids` 数组中移除该 document_id，不删除图表本身 |

删除 Notebook 时的 MinIO 清理由 DiagramService 的删除逻辑负责，不依赖数据库触发器。

## MinIO 存储路径

```
diagrams/{notebook_id}/{diagram_id}.json    # format = reactflow_json
diagrams/{notebook_id}/{diagram_id}.mmd     # format = mermaid
```

文件内容为 Agent 输出的原始文本，经过 DiagramTypeDescriptor.validator 校验后写入。

### reactflow_json 文件结构

```json
{
  "nodes": [
    { "id": "root", "label": "大模型基础" },
    { "id": "n1",   "label": "模型训练" },
    { "id": "n2",   "label": "模型推理" },
    { "id": "n3",   "label": "Transformer 架构" }
  ],
  "edges": [
    { "source": "root", "target": "n1" },
    { "source": "root", "target": "n2" },
    { "source": "n1",   "target": "n3" }
  ]
}
```

节点不包含 `position` 字段，坐标由前端 dagre 自动计算，用户调整的坐标存储在 `node_positions` 字段中。

### mermaid 文件结构

存储原始 Mermaid 语法文本，例如：

```
flowchart TD
    A[开始] --> B{判断条件}
    B -- 是 --> C[执行操作]
    B -- 否 --> D[结束]
```

## 领域实体

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Diagram:
    diagram_id:     str
    notebook_id:    str
    title:          str
    diagram_type:   str                  # "mindmap" | "flowchart" | ...
    format:         str                  # "reactflow_json" | "mermaid"
    content_path:   str                  # MinIO 路径
    document_ids:   list[str]            # 关联文档 ID 列表
    node_positions: dict[str, dict] | None  # {"node_id": {"x": float, "y": float}}
    created_at:     datetime
    updated_at:     datetime

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()
```

## 查询路径

| 查询场景 | 方式 |
|---------|------|
| 获取 notebook 下所有图表 | `WHERE notebook_id = ?` |
| 获取关联某文档的所有图表 | `WHERE ? = ANY(document_ids)` + GIN 索引 |
| 获取单张图表元数据 | `WHERE diagram_id = ?` |
| 获取图表内容 | 从 MinIO 读取 `content_path` 对应文件 |
| 更新节点坐标 | `UPDATE diagrams SET node_positions = ?, updated_at = ? WHERE diagram_id = ?` |
