# Service 层

## DiagramService

DiagramService 是 diagram 模块的核心业务逻辑层，负责协调 DiagramTypeRegistry、DiagramRepository 和 MinIO 存储，向上层（API 路由和 Skill 工具）提供统一接口。

存储接口对齐现有代码：

- 读取文本：`storage.get_text(object_key)`
- 删除对象：`storage.delete_file(object_key)`
- 写入文本时可在 service 内部复用现有 backend 能力封装 `save_file` / `save_from_path`

```python
class DiagramService:

    def __init__(
        self,
        repository: DiagramRepository,
        storage: StorageBackend,   # 复用现有存储抽象（local/minio 均实现）
    ) -> None:
        self._repo = repository
        self._storage = storage

    # -----------------------------------------------------------------------
    # 读操作（API 和 Skill 工具均可调用）
    # -----------------------------------------------------------------------

    async def list_diagrams(
        self,
        notebook_id: str,
        document_id: str | None = None,
    ) -> list[Diagram]:
        """
        列出 notebook 下所有图表的元数据。
        document_id 不为 None 时，仅返回关联该文档的图表。
        返回结果按 created_at 降序排列。
        """
        ...

    async def get_diagram(self, diagram_id: str) -> Diagram:
        """
        获取图表元数据。
        图表不存在时抛出 DiagramNotFoundError。
        """
        ...

    async def get_diagram_content(self, diagram_id: str) -> str:
        """
        从 MinIO 读取图表内容文件，返回原始文本（JSON 字符串或 Mermaid 语法）。
        图表不存在时抛出 DiagramNotFoundError。
        """
        diagram = await self.get_diagram(diagram_id)
        return await self._storage.get_text(diagram.content_path)

    # -----------------------------------------------------------------------
    # Agent 写操作（通过 Skill 工具调用，破坏性操作需确认机制介入）
    # -----------------------------------------------------------------------

    async def create_diagram(
        self,
        notebook_id: str,
        title: str,
        diagram_type: str,
        content: str,
        document_ids: list[str],
    ) -> Diagram:
        """
        创建图表。

        流程：
        1. 从注册表获取 DiagramTypeDescriptor
        2. 调用 descriptor.validator(content) 校验内容格式
           校验失败时抛出 DiagramValidationError（调用方捕获后返回给 Agent）
        3. 生成 diagram_id，构造 MinIO 路径
        4. 写入 MinIO 文件
        5. 写入数据库记录
        6. 返回 Diagram 实体
        """
        ...

    async def update_diagram_content(
        self,
        diagram_id: str,
        content: str,
        title: str | None = None,
    ) -> Diagram:
        """
        更新图表内容。调用前须经用户确认（由 AgentLoop 确认机制保证）。

        流程：
        1. 查询现有图表，取得 diagram_type
        2. 从注册表获取 descriptor，校验新内容格式
        3. 覆写 MinIO 文件（不修改 node_positions）
        4. 更新数据库 updated_at，可选更新 title
        5. 返回更新后的 Diagram 实体
        """
        ...

    async def delete_diagram(self, diagram_id: str) -> None:
        """
        删除图表。调用前须经用户确认（由 AgentLoop 确认机制保证）。

        流程：
        1. 查询图表，取得 content_path
        2. 删除 MinIO 文件
        3. 删除数据库记录
        """
        ...

    # -----------------------------------------------------------------------
    # 用户 UI 操作（仅前端直接调用，不经过 Agent）
    # -----------------------------------------------------------------------

    async def update_node_positions(
        self,
        diagram_id: str,
        positions: dict[str, dict],
    ) -> None:
        """
        更新 reactflow_json 图表的节点坐标。由前端拖拽结束后防抖调用。

        positions 结构：{"node_id": {"x": 120.5, "y": 80.0}, ...}

        此操作仅更新 node_positions JSONB 字段，不触及 MinIO 文件，
        不需要 Agent 确认。
        mermaid 格式的图表调用此接口时返回 400 错误。
        """
        ...
```

## DiagramRepository

```python
from typing import Protocol


class DiagramRepository(Protocol):

    async def save(self, diagram: Diagram) -> Diagram:
        """插入新图表记录，返回含数据库生成字段的完整实体。"""
        ...

    async def find_by_id(self, diagram_id: str) -> Diagram | None:
        """按 diagram_id 查询，不存在时返回 None。"""
        ...

    async def find_by_notebook(
        self,
        notebook_id: str,
        document_id: str | None = None,
    ) -> list[Diagram]:
        """
        查询 notebook 下的图表列表。
        document_id 不为 None 时追加 WHERE ? = ANY(document_ids) 条件。
        """
        ...

    async def update_metadata(
        self,
        diagram_id: str,
        *,
        title: str | None = None,
    ) -> Diagram:
        """文件覆写后更新数据库元数据（title / updated_at），不改动 node_positions。"""
        ...

    async def update_positions(
        self,
        diagram_id: str,
        positions: dict[str, dict],
    ) -> None:
        """仅更新 node_positions 字段，同步更新 updated_at。"""
        ...

    async def delete(self, diagram_id: str) -> None:
        """删除图表记录。对象文件由 DiagramService 在调用此方法前删除。"""
        ...
```

## 错误类型

```python
class DiagramNotFoundError(Exception):
    """指定 diagram_id 的图表不存在"""
    pass


class DiagramValidationError(Exception):
    """图表内容格式校验失败，错误信息供 Agent 参考修正"""
    pass


class DiagramTypeNotFoundError(Exception):
    """请求的图表类型未在注册表中注册"""
    pass


class DiagramFormatMismatchError(Exception):
    """操作与图表格式不兼容，例如对 mermaid 格式调用 update_node_positions"""
    pass
```

## Agent 重试流程

当 Agent 调用 `create_diagram` 或 `update_diagram` 工具，且内容未通过格式校验时：

```
create_diagram tool.execute()
  → DiagramService.create_diagram()
  → descriptor.validator(content) → 抛出 DiagramValidationError
  → tool.execute() 捕获异常
  → 返回 ToolCallResult(content="", error="图表结构校验失败：...")
  → AgentLoop 将错误信息追加到 chat history
  → Agent 读取错误信息，修正输出，重新调用 create_diagram
  → 最多重试 3 次，超过后 AgentLoop 进入 synthesizing 阶段告知用户生成失败
```

错误信息应具体描述失败原因（例如"节点缺少 label 字段"），使 Agent 能够准确修正。
