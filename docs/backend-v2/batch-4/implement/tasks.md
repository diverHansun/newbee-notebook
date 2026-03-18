# Tasks — Batch-4: Diagram Module (Mind Map)

## Metadata
- Created: 2026-03-18
- Source Plan:
  - `docs/backend-v2/batch-4/diagram/`
  - `docs/backend-v2/batch-4/frontend/`

## Progress Summary
- Total: 41 tasks
- Completed: 0
- In Progress: 0
- Remaining: 41

## Alignment Notes
- 数据库物理主键统一使用 `id`，领域/API 层映射为 `diagram_id`
- `diagrams.notebook_id` 外键应指向现有表结构 `notebooks(id)`
- 存储抽象对齐现有 `StorageBackend`：读取用 `get_text()`，删除用 `delete_file()`；文本写入需在 service 内部基于 `save_file()` 封装
- `DiagramRepository` 更新内容后的数据库回写建议只做元数据更新，不再设计伪造的 `update_content_path()` 合同
- batch-4 前端依赖 `@xyflow/react`、`@dagrejs/dagre`、`html2canvas`、`mermaid` 当前尚未安装，Vitest/前端测试脚本也尚未存在，需要先补基建
- Diagram skill 的确认流复用 batch-3：SSE 事件展示 `args_summary`，确认接口为 `POST /api/v1/chat/{session_id}/confirm`
- 代码目录沿用当前项目分层：领域实体/仓储放 `domain/`，服务放 `application/services/`，仓储实现放 `infrastructure/persistence/repositories/`，skill 放 `skills/diagram/`
- 前端目录沿用现状：hooks 放 `frontend/src/lib/hooks/`，store 放 `frontend/src/stores/`

---

## Phase 1: 数据库迁移

### Task 1: 创建 diagrams 表迁移脚本

**Files:**
- Create: `newbee_notebook/scripts/db/migrations/batch4_diagrams.sql`

- [ ] T001 创建 `diagrams` 表 DDL，包含所有索引和注释

  ```sql
  -- diagrams: agent 生成的可视化图表（mindmap 等）
  CREATE TABLE diagrams (
      id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
      notebook_id     UUID        NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
      title           TEXT        NOT NULL,
      diagram_type    TEXT        NOT NULL,
      -- 已注册类型：'mindmap'；新类型由应用层 DiagramTypeRegistry 控制，无需 CHECK 约束
      format          TEXT        NOT NULL CHECK (format IN ('reactflow_json', 'mermaid')),
      content_path    TEXT        NOT NULL,
      -- MinIO 路径：diagrams/{notebook_id}/{diagram_id}.json 或 .mmd
      document_ids    UUID[]      NOT NULL DEFAULT '{}',
      node_positions  JSONB,
      -- 仅 reactflow_json 格式使用；mermaid 格式始终为 NULL
      -- 结构：{"node_id": {"x": 120.5, "y": 80.0}, ...}
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE INDEX idx_diagrams_notebook_id  ON diagrams(notebook_id);
  CREATE INDEX idx_diagrams_document_ids ON diagrams USING GIN(document_ids);
  ```

  执行迁移脚本，验证表结构、索引、CHECK 约束均正确创建。

---

## Phase 2: 领域层 — 实体 + 注册表

### Task 2: Diagram 领域实体

**Files:**
- Create: `newbee_notebook/domain/entities/diagram.py`

- [ ] T002 定义 `Diagram` dataclass

  ```python
  from dataclasses import dataclass, field
  from datetime import datetime


  @dataclass
  class Diagram:
      diagram_id:     str
      notebook_id:    str
      title:          str
      diagram_type:   str          # "mindmap" | "flowchart" | ...
      format:         str          # "reactflow_json" | "mermaid"
      content_path:   str          # MinIO 路径
      document_ids:   list[str]    # 关联文档 ID 列表
      node_positions: dict[str, dict] | None
      created_at:     datetime
      updated_at:     datetime

      def touch(self) -> None:
          self.updated_at = datetime.utcnow()
  ```

### Task 3: DiagramTypeDescriptor + 异常类型

**Files:**
- Create: `newbee_notebook/application/services/diagram_service.py`（异常类型）
- Create: `newbee_notebook/skills/diagram/registry.py`（仅 DiagramTypeDescriptor 定义部分）

- [ ] T003 定义 4 个异常类 + DiagramTypeDescriptor dataclass

  ```python
  # exceptions.py
  class DiagramNotFoundError(Exception):
      """指定 diagram_id 的图表不存在"""

  class DiagramValidationError(Exception):
      """图表内容格式校验失败，错误信息应足够具体供 Agent 参考修正"""

  class DiagramTypeNotFoundError(Exception):
      """请求的图表类型未在注册表中注册"""

  class DiagramFormatMismatchError(Exception):
      """操作与图表格式不兼容（例如对 mermaid 格式调用 update_node_positions）"""
  ```

  ```python
  # registry.py（DiagramTypeDescriptor 部分）
  from dataclasses import dataclass
  from typing import Callable

  @dataclass(frozen=True)
  class DiagramTypeDescriptor:
      name:                str
      slash_command:       str
      output_format:       str   # "reactflow_json" | "mermaid"
      file_extension:      str   # ".json" | ".mmd"
      description:         str
      agent_system_prompt: str
      validator:           Callable[[str], None]
  ```

### Task 4: validate_reactflow_schema + DIAGRAM_TYPE_REGISTRY

**Files:**
- Modify: `newbee_notebook/skills/diagram/registry.py`（补充 validator + registry）

TDD 周期：

- [ ] T004-Red 为 `validate_reactflow_schema` 写单元测试

  ```python
  # newbee_notebook/tests/unit/skills/diagram/test_registry.py

  def test_valid_reactflow_json_passes():
      content = '{"nodes":[{"id":"root","label":"主题"},{"id":"n1","label":"子主题"}],"edges":[{"source":"root","target":"n1"}]}'
      validate_reactflow_schema(content)  # 不抛异常

  def test_invalid_json_raises():
      with pytest.raises(DiagramValidationError, match="JSON 解析失败"):
          validate_reactflow_schema("not json")

  def test_missing_nodes_raises():
      with pytest.raises(DiagramValidationError):
          validate_reactflow_schema('{"edges":[]}')

  def test_node_with_position_raises():
      content = '{"nodes":[{"id":"root","label":"x","position":{"x":0,"y":0}}],"edges":[]}'
      with pytest.raises(DiagramValidationError, match="position"):
          validate_reactflow_schema(content)

  def test_empty_nodes_passes():
      validate_reactflow_schema('{"nodes":[],"edges":[]}')

  def test_get_descriptor_known_type():
      d = get_descriptor("mindmap")
      assert d.output_format == "reactflow_json"

  def test_get_descriptor_unknown_type():
      with pytest.raises(DiagramTypeNotFoundError):
          get_descriptor("unknown_type")

  def test_get_all_slash_commands_contains_mindmap():
      assert "/mindmap" in get_all_slash_commands()
  ```

- [ ] T004-Green 实现 `validate_reactflow_schema`（Pydantic）、`DIAGRAM_TYPE_REGISTRY`（mindmap 条目）、`get_descriptor()`、`get_all_slash_commands()`

  ```python
  # registry.py（完整实现）
  from pydantic import BaseModel
  import json

  class ReactFlowNode(BaseModel):
      id: str
      label: str

  class ReactFlowEdge(BaseModel):
      source: str
      target: str

  class ReactFlowDiagramSchema(BaseModel):
      nodes: list[ReactFlowNode]
      edges: list[ReactFlowEdge]

  def validate_reactflow_schema(content: str) -> None:
      try:
          data = json.loads(content)
      except json.JSONDecodeError as e:
          raise DiagramValidationError(f"JSON 解析失败：{e}") from e
      try:
          ReactFlowDiagramSchema.model_validate(data)
      except Exception as e:
          raise DiagramValidationError(f"图表结构校验失败：{e}") from e
      for node in data.get("nodes", []):
          if "position" in node:
              raise DiagramValidationError(
                  f"节点 '{node.get('id')}' 包含 position 字段，请移除所有 position 字段，坐标由前端自动计算。"
              )

  DIAGRAM_TYPE_REGISTRY: dict[str, DiagramTypeDescriptor] = {
      "mindmap": DiagramTypeDescriptor(
          name="mindmap",
          slash_command="/mindmap",
          output_format="reactflow_json",
          file_extension=".json",
          description="思维导图",
          agent_system_prompt=(
              "你需要根据用户要求和文档内容生成一张思维导图。\n"
              "输出格式为严格的 JSON，顶层包含两个字段：\n"
              "- nodes：数组，每个元素包含 id（字符串）和 label（字符串）\n"
              "- edges：数组，每个元素包含 source（节点 id）和 target（节点 id）\n"
              "约束：\n"
              "1. 不要在节点中包含 position 字段\n"
              "2. 不要在 JSON 之外输出任何内容\n"
              "3. 根节点 id 建议使用 'root'\n"
              "4. label 内容使用与用户输入一致的语言\n"
              '示例：{"nodes":[{"id":"root","label":"主题"},{"id":"n1","label":"子主题"}],'
              '"edges":[{"source":"root","target":"n1"}]}'
          ),
          validator=validate_reactflow_schema,
      ),
  }

  def get_descriptor(diagram_type: str) -> DiagramTypeDescriptor:
      descriptor = DIAGRAM_TYPE_REGISTRY.get(diagram_type)
      if descriptor is None:
          raise DiagramTypeNotFoundError(
              f"图表类型 '{diagram_type}' 未注册，当前支持：{list(DIAGRAM_TYPE_REGISTRY.keys())}"
          )
      return descriptor

  def get_all_slash_commands() -> list[str]:
      return [d.slash_command for d in DIAGRAM_TYPE_REGISTRY.values()]
  ```

- [ ] T004-Refactor 确认所有测试通过后整理代码

### Task 5: DiagramRepository Protocol

**Files:**
- Create: `newbee_notebook/domain/repositories/diagram_repository.py`

- [ ] T005 定义 `DiagramRepository` Protocol（6 个方法签名）

  ```python
  from typing import Protocol

  class DiagramRepository(Protocol):
      async def save(self, diagram: Diagram) -> Diagram: ...
      async def find_by_id(self, diagram_id: str) -> Diagram | None: ...
      async def find_by_notebook(
          self,
          notebook_id: str,
          document_id: str | None = None,
      ) -> list[Diagram]: ...
      async def update_metadata(
          self,
          diagram_id: str,
          *,
          title: str | None = None,
      ) -> Diagram: ...
      async def update_positions(
          self,
          diagram_id: str,
          positions: dict[str, dict],
      ) -> None: ...
      async def delete(self, diagram_id: str) -> None: ...
  ```

---

## Phase 3: 基础设施 — PostgresDiagramRepository

### Task 6: PostgresDiagramRepository 实现

**Files:**
- Create: `newbee_notebook/infrastructure/persistence/repositories/diagram_repo_impl.py`

- [ ] T006 实现 `PostgresDiagramRepository`，覆盖 Protocol 所有方法

  重点细节：
  - `find_by_notebook`：`document_id` 不为 None 时追加 `WHERE $2 = ANY(document_ids)` 子句
  - `update_positions`：仅更新 `node_positions` 和 `updated_at`，不触碰其他字段
  - `delete`：从数据库删除记录（MinIO 文件由 DiagramService 先行删除）
  - 行映射辅助方法 `_row_to_diagram`：将 asyncpg 行映射为 `Diagram` 实体，注意 `node_positions` 为 JSONB（asyncpg 返回 dict 或 None）、`document_ids` 为 UUID 数组（需转 `list[str]`）

---

## Phase 4: DiagramService (TDD)

### Task 7: list_diagrams + get_diagram

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Create: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T007-Red

  ```python
  # newbee_notebook/tests/unit/application/services/test_diagram_service.py
  import pytest
  from unittest.mock import AsyncMock
  from newbee_notebook.core.diagrams.service import DiagramService
  from newbee_notebook.core.diagrams.exceptions import DiagramNotFoundError

  @pytest.fixture
  def mock_repo():
      return AsyncMock()

  @pytest.fixture
  def mock_storage():
      return AsyncMock()

  @pytest.fixture
  def service(mock_repo, mock_storage):
      return DiagramService(repository=mock_repo, storage=mock_storage)

  async def test_list_diagrams_delegates_to_repo(service, mock_repo):
      mock_repo.find_by_notebook.return_value = []
      result = await service.list_diagrams("nb-1")
      mock_repo.find_by_notebook.assert_called_once_with("nb-1", document_id=None)
      assert result == []

  async def test_list_diagrams_with_document_filter(service, mock_repo):
      mock_repo.find_by_notebook.return_value = []
      await service.list_diagrams("nb-1", document_id="doc-1")
      mock_repo.find_by_notebook.assert_called_once_with("nb-1", document_id="doc-1")

  async def test_get_diagram_not_found_raises(service, mock_repo):
      mock_repo.find_by_id.return_value = None
      with pytest.raises(DiagramNotFoundError):
          await service.get_diagram("nonexistent-id")
  ```

- [ ] T007-Green 实现 `list_diagrams` 和 `get_diagram`

- [ ] T007-Refactor

### Task 8: get_diagram_content

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T008-Red

  ```python
  async def test_get_diagram_content_reads_minio(service, mock_repo, mock_storage):
      fake_diagram = make_fake_diagram(content_path="diagrams/nb-1/d1.json")
      mock_repo.find_by_id.return_value = fake_diagram
      mock_storage.get_text.return_value = '{"nodes":[],"edges":[]}'

      content = await service.get_diagram_content("d1")

      mock_storage.get_text.assert_called_once_with("diagrams/nb-1/d1.json")
      assert content == '{"nodes":[],"edges":[]}'

  async def test_get_diagram_content_not_found(service, mock_repo):
      mock_repo.find_by_id.return_value = None
      with pytest.raises(DiagramNotFoundError):
          await service.get_diagram_content("nonexistent")
  ```

- [ ] T008-Green 实现 `get_diagram_content`（先查元数据，再读 MinIO）

- [ ] T008-Refactor

### Task 9: create_diagram

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T009-Red

  ```python
  VALID_CONTENT = '{"nodes":[{"id":"root","label":"主题"},{"id":"n1","label":"子主题"}],"edges":[{"source":"root","target":"n1"}]}'
  INVALID_CONTENT = "not json"

  async def test_create_diagram_success(service, mock_repo, mock_storage):
      mock_repo.save.return_value = make_fake_diagram()
      result = await service.create_diagram(
          notebook_id="nb-1",
          title="测试导图",
          diagram_type="mindmap",
          content=VALID_CONTENT,
          document_ids=["doc-1"],
      )
      mock_storage.save_file.assert_called_once()
      mock_repo.save.assert_called_once()
      assert result.diagram_type == "mindmap"

  async def test_create_diagram_invalid_content_raises_before_storage(service, mock_repo, mock_storage):
      with pytest.raises(DiagramValidationError):
          await service.create_diagram(
              notebook_id="nb-1", title="x",
              diagram_type="mindmap", content=INVALID_CONTENT, document_ids=[],
          )
      mock_storage.save_file.assert_not_called()
      mock_repo.save.assert_not_called()

  async def test_create_diagram_unknown_type_raises(service, mock_repo, mock_storage):
      with pytest.raises(DiagramTypeNotFoundError):
          await service.create_diagram(
              notebook_id="nb-1", title="x",
              diagram_type="unknown", content=VALID_CONTENT, document_ids=[],
          )
  ```

- [ ] T009-Green 实现 `create_diagram`

  ```python
  async def create_diagram(self, notebook_id, title, diagram_type, content, document_ids):
      descriptor = get_descriptor(diagram_type)    # 类型不存在则抛出
      descriptor.validator(content)               # 格式非法则抛出，无 storage 副作用
      diagram_id = str(uuid4())
      content_path = f"diagrams/{notebook_id}/{diagram_id}{descriptor.file_extension}"
      await self._storage.save_file(
          content_path,
          BytesIO(content.encode("utf-8")),
          content_type="application/json" if descriptor.output_format == "reactflow_json" else "text/plain; charset=utf-8",
      )
      diagram = Diagram(
          diagram_id=diagram_id, notebook_id=notebook_id,
          title=title, diagram_type=diagram_type, format=descriptor.output_format,
          content_path=content_path, document_ids=document_ids,
          node_positions=None, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
      )
      return await self._repo.save(diagram)
  ```

- [ ] T009-Refactor

### Task 10: update_diagram_content

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T010-Red

  ```python
  async def test_update_content_overwrites_minio(service, mock_repo, mock_storage):
      fake = make_fake_diagram(node_positions={"root": {"x": 10, "y": 20}})
      mock_repo.find_by_id.return_value = fake
      mock_repo.update_metadata.return_value = fake

      await service.update_diagram_content("d1", VALID_CONTENT)

      mock_storage.save_file.assert_called_once()
      # node_positions 不应被清除
      call_kwargs = mock_repo.update_metadata.call_args
      assert call_kwargs  # update_metadata 被调用

  async def test_update_content_invalid_raises(service, mock_repo):
      mock_repo.find_by_id.return_value = make_fake_diagram()
      with pytest.raises(DiagramValidationError):
          await service.update_diagram_content("d1", INVALID_CONTENT)
  ```

- [ ] T010-Green 实现 `update_diagram_content`

- [ ] T010-Refactor

### Task 11: update_node_positions + format mismatch

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T011-Red

  ```python
  async def test_update_positions_reactflow_ok(service, mock_repo):
      fake = make_fake_diagram(format="reactflow_json")
      mock_repo.find_by_id.return_value = fake
      positions = {"root": {"x": 0.0, "y": 0.0}}
      await service.update_node_positions("d1", positions)
      mock_repo.update_positions.assert_called_once_with("d1", positions)

  async def test_update_positions_mermaid_raises(service, mock_repo):
      fake = make_fake_diagram(format="mermaid")
      mock_repo.find_by_id.return_value = fake
      with pytest.raises(DiagramFormatMismatchError):
          await service.update_node_positions("d1", {})
  ```

- [ ] T011-Green 实现 `update_node_positions`

- [ ] T011-Refactor

### Task 12: delete_diagram

**Files:**
- Modify: `newbee_notebook/application/services/diagram_service.py`
- Modify: `newbee_notebook/tests/unit/application/services/test_diagram_service.py`

- [ ] T012-Red

  ```python
  async def test_delete_diagram_removes_minio_then_db(service, mock_repo, mock_storage):
      fake = make_fake_diagram()
      mock_repo.find_by_id.return_value = fake
      call_order = []
      mock_storage.delete_file.side_effect = lambda _: call_order.append("storage")
      mock_repo.delete.side_effect = lambda _: call_order.append("repo")

      await service.delete_diagram("d1")

      assert call_order == ["storage", "repo"]

  async def test_delete_diagram_not_found_raises(service, mock_repo):
      mock_repo.find_by_id.return_value = None
      with pytest.raises(DiagramNotFoundError):
          await service.delete_diagram("nonexistent")

  async def test_delete_diagram_minio_fail_continues_db_delete(service, mock_repo, mock_storage):
      """MinIO 文件已不存在时，仍应继续删除数据库记录"""
      fake = make_fake_diagram()
      mock_repo.find_by_id.return_value = fake
      mock_storage.delete_file.side_effect = Exception("file not found")

      await service.delete_diagram("d1")  # 不应抛出

      mock_repo.delete.assert_called_once_with("d1")
  ```

- [ ] T012-Green 实现 `delete_diagram`（MinIO 删除失败时记录 warning，继续删除数据库记录）

- [ ] T012-Refactor

---

## Phase 5: REST API

### Task 13: Pydantic 请求/响应模型

**Files:**
- Create: `newbee_notebook/api/models/diagram_models.py`

- [ ] T013 定义所有 Pydantic 模型

  - `DiagramResponse`：diagram 元数据（不含 content_path，含 node_positions）
  - `DiagramListResponse`：`diagrams: list[DiagramResponse]` + `total: int`
  - `UpdatePositionsRequest`：`positions: dict[str, PositionModel]`
  - `PositionModel`：`x: float` + `y: float`
  - `UpdatePositionsResponse`：`diagram_id: str` + `updated_at: datetime`
  - `DeleteDiagramResponse`：`diagram_id: str` + `deleted: bool`

### Task 14: GET /diagrams + GET /diagrams/{id}

**Files:**
- Create: `newbee_notebook/api/routers/diagrams.py`

- [ ] T014 实现列表查询和单条查询端点

  ```python
  @router.get("", response_model=DiagramListResponse)
  async def list_diagrams(
      notebook_id: str = Query(...),
      document_id: str | None = Query(None),
      service: DiagramService = Depends(get_diagram_service),
  ):
      diagrams = await service.list_diagrams(notebook_id, document_id=document_id)
      return DiagramListResponse(diagrams=[...], total=len(diagrams))

  @router.get("/{diagram_id}", response_model=DiagramResponse)
  async def get_diagram(
      diagram_id: str,
      service: DiagramService = Depends(get_diagram_service),
  ):
      try:
          return await service.get_diagram(diagram_id)
      except DiagramNotFoundError:
          raise HTTPException(status_code=404, detail={"code": "DIAGRAM_NOT_FOUND"})
  ```

### Task 15: GET /diagrams/{id}/content

**Files:**
- Modify: `newbee_notebook/api/routers/diagrams.py`

- [ ] T015 实现内容文件端点（返回 `text/plain`）

  ```python
  @router.get("/{diagram_id}/content", response_class=PlainTextResponse)
  async def get_diagram_content(
      diagram_id: str,
      service: DiagramService = Depends(get_diagram_service),
  ):
      try:
          content = await service.get_diagram_content(diagram_id)
          return PlainTextResponse(content, media_type="text/plain; charset=utf-8")
      except DiagramNotFoundError:
          raise HTTPException(status_code=404, detail={"code": "DIAGRAM_NOT_FOUND"})
  ```

### Task 16: PATCH /positions + DELETE

**Files:**
- Modify: `newbee_notebook/api/routers/diagrams.py`

- [ ] T016 实现坐标更新和删除端点

  错误码映射：
  - `DiagramNotFoundError` → 404 `DIAGRAM_NOT_FOUND`
  - `DiagramFormatMismatchError` → 400 `DIAGRAM_FORMAT_MISMATCH`

### Task 17: DI 注入 + 路由注册

**Files:**
- Modify: `newbee_notebook/api/dependencies.py`（或现有 DI 配置文件）
- Modify: `newbee_notebook/api/app.py`（或现有路由注册入口）

- [ ] T017 注册 `diagrams` 路由，配置 `get_diagram_service` 依赖注入（连接 `PostgresDiagramRepository` + `StorageService`）

---

## Phase 6: DiagramSkillProvider (TDD)

### Task 18: 5 个 Agent 工具工厂函数

**Files:**
- Create: `newbee_notebook/skills/diagram/tools.py`
- Create: `newbee_notebook/tests/unit/skills/diagram/test_tools.py`

- [ ] T018-Red

  ```python
  # newbee_notebook/tests/unit/skills/diagram/test_tools.py

  @pytest.fixture
  def mock_service():
      return AsyncMock(spec=DiagramService)

  async def test_create_tool_success(mock_service):
      mock_service.create_diagram.return_value = make_fake_diagram(diagram_id="d-new")
      tool = _build_create_diagram_tool(mock_service, "nb-1", "mindmap")
      result = await tool.execute({
          "title": "测试导图",
          "content": VALID_CONTENT,
          "document_ids": ["doc-1"],
      })
      assert result.error is None
      assert "d-new" in result.content

  async def test_create_tool_validation_error(mock_service):
      mock_service.create_diagram.side_effect = DiagramValidationError("缺少 nodes 字段")
      tool = _build_create_diagram_tool(mock_service, "nb-1", "mindmap")
      result = await tool.execute({"title": "x", "content": "bad", "document_ids": []})
      assert result.error is not None
      assert result.content == ""

  async def test_delete_tool_not_found(mock_service):
      mock_service.delete_diagram.side_effect = DiagramNotFoundError()
      tool = _build_delete_diagram_tool(mock_service)
      result = await tool.execute({"diagram_id": "nonexistent"})
      assert result.error is not None

  async def test_list_tool_returns_json(mock_service):
      mock_service.list_diagrams.return_value = [make_fake_diagram()]
      tool = _build_list_diagrams_tool(mock_service, "nb-1")
      result = await tool.execute({})
      items = json.loads(result.content)
      assert isinstance(items, list)
      assert "diagram_id" in items[0]
  ```

- [ ] T018-Green 实现 5 个工厂函数：`_build_list_diagrams_tool`、`_build_read_diagram_tool`、`_build_create_diagram_tool`、`_build_update_diagram_tool`、`_build_delete_diagram_tool`（参见设计文档 `diagram/05-skill-provider.md`）

- [ ] T018-Refactor

### Task 19: DiagramSkillProvider 类

**Files:**
- Create: `newbee_notebook/skills/diagram/provider.py`

- [ ] T019 实现 `DiagramSkillProvider`（继承 `SkillProvider`）

  关键：
  - `slash_commands` 属性返回 `get_all_slash_commands()`
  - `build_manifest(context)` 中通过 `context.activated_command.lstrip("/")` 查注册表取 descriptor
  - `confirmation_required=frozenset({"update_diagram", "delete_diagram"})`
  - 工具通过 `_build_tools(context, diagram_type)` 按需构建（闭包注入 notebook_id 和 diagram_type）

### Task 20: 注册 DiagramSkillProvider 到 SkillRegistry

**Files:**
- Modify: 应用启动/DI 配置文件（与 batch-3 NoteSkillProvider 注册位置一致）

- [ ] T020 在应用启动时创建 `DiagramSkillProvider` 实例并调用 `skill_registry.register(diagram_skill_provider)`

---

## Phase 7: 前端基础

### Task 21: TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/diagram.ts`

- [ ] T021 定义 5 个接口/类型

  ```typescript
  export interface Diagram {
    diagram_id: string;
    notebook_id: string;
    title: string;
    diagram_type: DiagramType;
    format: DiagramFormat;
    document_ids: string[];
    node_positions: Record<string, { x: number; y: number }> | null;
    created_at: string;
    updated_at: string;
  }

  export type DiagramType = "mindmap" | "flowchart" | "sequence" | "gantt";
  export type DiagramFormat = "reactflow_json" | "mermaid";

  export interface ReactFlowDiagramContent {
    nodes: ReactFlowRawNode[];
    edges: ReactFlowRawEdge[];
  }

  export interface ReactFlowRawNode { id: string; label: string; }
  export interface ReactFlowRawEdge { source: string; target: string; }

  export interface UpdateDiagramPositionsRequest {
    positions: Record<string, { x: number; y: number }>;
  }
  ```

### Task 22: i18n 文案键值

**Files:**
- Modify: `frontend/src/lib/i18n/index.ts`（或现有 uiStrings 文件）

- [ ] T022 追加图表相关文案到现有 `uiStrings` 对象

  新增键值（中英双语）：
  - `studio.diagrams.cardTitle`、`cardDescription`、`emptyState`
  - `studio.diagrams.types.mindmap/flowchart/sequence/gantt`
  - `studio.diagrams.exportButton`、`deleteButton`、`deleteConfirm.title/message`
  - `studio.diagrams.unsupportedFormat`、`loadError`、`exportError`
  - `slashCommands.mindmap.label/description`
  - `slashCommands.flowchart.label/description`
  - `slashCommands.sequence.label/description`

### Task 23: API 客户端函数

**Files:**
- Create: `frontend/src/lib/api/diagram-api.ts`

- [ ] T023 实现 5 个 API 函数

  ```typescript
  export async function fetchDiagrams(notebookId: string, documentId?: string): Promise<Diagram[]>
  export async function fetchDiagram(diagramId: string): Promise<Diagram>
  export async function fetchDiagramContent(diagramId: string): Promise<string>
  export async function patchDiagramPositions(
    diagramId: string,
    positions: Record<string, { x: number; y: number }>,
  ): Promise<void>
  export async function deleteDiagram(diagramId: string): Promise<void>
  ```

  - `fetchDiagrams`：GET `/api/v1/diagrams?notebook_id=X[&document_id=Y]`
  - `fetchDiagramContent`：GET `/api/v1/diagrams/{id}/content`，返回 `response.text()`
  - 错误响应统一抛出 `ApiError`（复用项目现有错误处理约定）

### Task 24: TanStack Query Hooks

**Files:**
- Create: `frontend/src/lib/hooks/use-diagrams.ts`

- [ ] T024 实现 5 个 Query/Mutation Hooks

  ```typescript
  export function useDiagrams(notebookId: string, documentId?: string)
  // queryKey: ["diagrams", notebookId, documentId ?? "all"], staleTime: 30_000

  export function useDiagram(diagramId: string)
  // queryKey: ["diagram", diagramId], enabled: Boolean(diagramId)

  export function useDiagramContent(diagramId: string)
  // queryKey: ["diagram-content", diagramId], staleTime: 60_000

  export function useUpdateDiagramPositions()
  // onSuccess: invalidateQueries(["diagram", diagramId])

  export function useDeleteDiagram()
  // onSuccess: invalidateQueries(["diagrams"]) + removeQueries(["diagram", id]) + removeQueries(["diagram-content", id])
  ```

---

## Phase 8: Studio 图表卡片

### Task 25: Zustand store 扩展

**Files:**
- Modify: `frontend/src/stores/studio-store.ts`（或现有 studio 相关 store）

- [ ] T025 扩展 studioView 联合类型，新增 `activeDiagramId` 状态

  ```typescript
  // 在现有 studioView 类型中新增
  studioView: "home" | "notes" | "note-detail" | "diagrams" | "diagram-detail"
  activeDiagramId: string | null
  setActiveDiagram: (id: string) => void
  clearActiveDiagram: () => void
  ```

### Task 26: Studio 首页 "图表" 卡片入口

**Files:**
- Modify: `frontend/src/components/studio/StudioHome.tsx`（或 Studio 首页网格组件）

- [ ] T026 在 Studio 首页卡片网格中新增 "图表" 功能卡片

  点击后 `setStudioView("diagrams")`；卡片标题/描述使用 i18n 键值 `studio.diagrams.cardTitle/cardDescription`

### Task 27: DiagramListView

**Files:**
- Create: `frontend/src/components/studio/diagrams/DiagramListView.tsx`

- [ ] T027 实现图表列表视图，支持以下所有状态

  - 加载中：骨架屏（2-3 行占位）
  - 加载失败：错误提示
  - 空状态：引导文案（含 `/mindmap` 提示）
  - 正常列表：每项含标题、类型 badge（DiagramType）、关联文档数
  - 按文档过滤：下拉选择器，选中后重新调用 `useDiagrams(notebookId, documentId)`
  - 点击列表项：`setActiveDiagram(id)` + `setStudioView("diagram-detail")`
  - 点击删除：弹出 `AlertDialog` 确认，确认后调用 `useDeleteDiagram().mutate(id)`

### Task 28: DiagramDetailView

**Files:**
- Create: `frontend/src/components/studio/diagrams/DiagramDetailView.tsx`

- [ ] T028 实现图表详情视图

  顶部工具栏：
  - "← 图表列表" 按钮：`setStudioView("diagrams")`
  - "导出图片" 按钮：调用 `rendererRef.current?.exportToPng()`，期间显示 loading
  - "删除" 按钮：弹出确认对话框，确认后删除并跳转回列表

  内容区：
  - `useDiagram(activeDiagramId)` 加载元数据
  - `useDiagramContent(activeDiagramId)` 加载内容
  - 任一 loading → 骨架屏
  - 任一 error → 错误提示文案（`studio.diagrams.loadError`）
  - 加载完成 → 渲染 `DiagramViewer`

### Task 29: DiagramViewer

**Files:**
- Create: `frontend/src/components/studio/diagrams/DiagramViewer.tsx`

- [ ] T029 实现 format 分发组件

  ```tsx
  interface DiagramViewerProps {
    diagram: Diagram;
    content: string;
    ref?: React.Ref<DiagramRendererHandle>;
  }

  // format 分发逻辑：
  // "reactflow_json" → <ReactFlowRenderer>
  // "mermaid"        → <MermaidRenderer>（占位，batch-5 实现具体渲染）
  // 其他             → <p>{t(uiStrings.studio.diagrams.unsupportedFormat)}</p>
  ```

  `DiagramRendererHandle` 接口：`{ exportToPng: () => Promise<void> }`

---

## Phase 9: ReactFlowRenderer + Dagre

### Task 30: applyDagreLayout 工具函数

**Files:**
- Create: `frontend/src/lib/diagram/dagre-layout.ts`

- [ ] T030-Red

  ```typescript
  // tests/lib/diagram/dagre-layout.test.ts
  describe("applyDagreLayout", () => {
    it("assigns positions to all nodes", () => {
      const nodes = [
        { id: "root", label: "Root" },
        { id: "n1", label: "Child 1" },
        { id: "n2", label: "Child 2" },
      ];
      const edges = [
        { source: "root", target: "n1" },
        { source: "root", target: "n2" },
      ];
      const result = applyDagreLayout(nodes, edges);
      result.forEach((n) => {
        expect(typeof n.position.x).toBe("number");
        expect(typeof n.position.y).toBe("number");
      });
    });

    it("handles single node without error", () => {
      const result = applyDagreLayout([{ id: "root", label: "Only" }], []);
      expect(result).toHaveLength(1);
      expect(result[0].position).toBeDefined();
    });

    it("returns empty array for empty input", () => {
      expect(applyDagreLayout([], [])).toEqual([]);
    });
  });
  ```

- [ ] T030-Green 实现 `applyDagreLayout`（使用 `@dagrejs/dagre`，`rankdir: "LR"`，节点宽度 160，高度 40）

  ```typescript
  import dagre from "@dagrejs/dagre";
  import type { ReactFlowRawNode, ReactFlowRawEdge } from "@/types/diagram";

  export function applyDagreLayout(
    nodes: ReactFlowRawNode[],
    edges: ReactFlowRawEdge[],
    nodeWidth = 160,
    nodeHeight = 40,
  ): Array<ReactFlowRawNode & { position: { x: number; y: number } }> {
    if (nodes.length === 0) return [];
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 80 });
    g.setDefaultEdgeLabel(() => ({}));
    nodes.forEach((n) => g.setNode(n.id, { width: nodeWidth, height: nodeHeight }));
    edges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);
    return nodes.map((n) => {
      const { x, y } = g.node(n.id);
      return { ...n, position: { x: x - nodeWidth / 2, y: y - nodeHeight / 2 } };
    });
  }
  ```

- [ ] T030-Refactor

### Task 31: mergeUserPositions 工具函数

**Files:**
- Modify: `frontend/src/lib/diagram/dagre-layout.ts`

- [ ] T031-Red

  ```typescript
  describe("mergeUserPositions", () => {
    const dagreNodes = [
      { id: "root", label: "R", position: { x: 10, y: 20 } },
      { id: "n1",   label: "N1", position: { x: 100, y: 50 } },
    ];

    it("returns original when savedPositions is null", () => {
      expect(mergeUserPositions(dagreNodes, null)).toEqual(dagreNodes);
    });

    it("returns original when savedPositions is empty object", () => {
      expect(mergeUserPositions(dagreNodes, {})).toEqual(dagreNodes);
    });

    it("overrides only matching node position", () => {
      const saved = { root: { x: 999, y: 888 } };
      const result = mergeUserPositions(dagreNodes, saved);
      expect(result.find(n => n.id === "root")!.position).toEqual({ x: 999, y: 888 });
      expect(result.find(n => n.id === "n1")!.position).toEqual({ x: 100, y: 50 });
    });

    it("ignores unknown node IDs in savedPositions", () => {
      const result = mergeUserPositions(dagreNodes, { "ghost": { x: 0, y: 0 } });
      expect(result).toEqual(dagreNodes);
    });
  });
  ```

- [ ] T031-Green 实现 `mergeUserPositions`

- [ ] T031-Refactor

### Task 32: ReactFlowRenderer 组件

**Files:**
- Create: `frontend/src/components/studio/diagrams/ReactFlowRenderer.tsx`
- Create: `frontend/src/components/studio/diagrams/MindMapNode.tsx`

- [ ] T032 实现 ReactFlowRenderer 核心逻辑

  关键实现点：
  - JSON 解析 content → `ReactFlowDiagramContent`
  - 调用 `applyDagreLayout` 计算节点坐标
  - 调用 `mergeUserPositions` 合并 `diagram.node_positions`（用户已保存的坐标）
  - 转换为 React Flow `Node[]` 和 `Edge[]`（type: "mindMapNode"）
  - 使用 `useImperativeHandle` 暴露 `exportToPng` 方法
  - 通过 `containerRef` 获取根 div 的 DOM 引用
  - MindMapNode：自定义节点，透明 handle，label 居中展示

  ```tsx
  // MindMapNode.tsx
  export function MindMapNode({ data }: { data: { label: string } }) {
    return (
      <div className="px-4 py-2 bg-white border border-gray-200 rounded-lg shadow-sm text-sm">
        <Handle type="target" position={Position.Left} className="opacity-0" />
        {data.label}
        <Handle type="source" position={Position.Right} className="opacity-0" />
      </div>
    );
  }
  ```

### Task 33: 节点拖拽后防抖坐标保存

**Files:**
- Modify: `frontend/src/components/studio/diagrams/ReactFlowRenderer.tsx`

- [ ] T033 监听节点拖拽结束事件，防抖 2 秒后调用 PATCH 接口

  ```tsx
  const { mutate: updatePositions } = useUpdateDiagramPositions();
  const debouncedSave = useMemo(
    () =>
      debounce((nodes: Node[]) => {
        const positions: Record<string, { x: number; y: number }> = {};
        nodes.forEach((n) => { positions[n.id] = n.position; });
        updatePositions({ diagramId: diagram.diagram_id, positions });
      }, 2000),
    [diagram.diagram_id, updatePositions],
  );

  // 在 onNodesChange 中，dragging 从 true 变为 false 时触发
  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      onNodesChange(changes);
      const dragEndChange = changes.find(
        (c) => c.type === "position" && c.dragging === false,
      );
      if (dragEndChange) {
        debouncedSave(getNodes());
      }
    },
    [onNodesChange, getNodes, debouncedSave],
  );
  ```

---

## Phase 10: 导出

### Task 34: exportReactFlowToPng 工具函数

**Files:**
- Create: `frontend/src/lib/diagram/export.ts`

- [ ] T034-Red

  ```typescript
  // tests/lib/diagram/export.test.ts
  import { exportReactFlowToPng } from "@/lib/diagram/export";

  vi.mock("html2canvas", () => ({
    default: vi.fn().mockResolvedValue({
      toBlob: (cb: (blob: Blob | null) => void) => cb(new Blob(["img"], { type: "image/png" })),
    }),
  }));

  it("creates download link with correct filename", async () => {
    const el = document.createElement("div");
    const createSpy = vi.spyOn(document, "createElement");
    await exportReactFlowToPng(el, "my diagram");
    const link = createSpy.mock.results.find(r => r.value?.tagName === "A")?.value;
    expect(link?.download).toBe("my diagram.png");
  });

  it("sanitizes special chars in filename", async () => {
    const el = document.createElement("div");
    const createSpy = vi.spyOn(document, "createElement");
    await exportReactFlowToPng(el, "test/file");
    const link = createSpy.mock.results.find(r => r.value?.tagName === "A")?.value;
    expect(link?.download).toBe("test-file.png");
  });

  it("uses 'diagram' for empty title", async () => {
    const el = document.createElement("div");
    const createSpy = vi.spyOn(document, "createElement");
    await exportReactFlowToPng(el, "");
    const link = createSpy.mock.results.find(r => r.value?.tagName === "A")?.value;
    expect(link?.download).toBe("diagram.png");
  });
  ```

- [ ] T034-Green 实现 `exportReactFlowToPng` + `sanitizeFilename`

  ```typescript
  import html2canvas from "html2canvas";

  export async function exportReactFlowToPng(
    containerEl: HTMLElement,
    filename: string,
  ): Promise<void> {
    const canvas = await html2canvas(containerEl, {
      backgroundColor: "#ffffff",
      scale: 2,
      useCORS: true,
      logging: false,
      ignoreElements: (el) =>
        el.classList.contains("react-flow__controls") ||
        el.classList.contains("react-flow__background"),
    });
    canvas.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${sanitizeFilename(filename)}.png`;
      link.click();
      URL.revokeObjectURL(url);
    }, "image/png");
  }

  function sanitizeFilename(name: string): string {
    return name.replace(/[/\\?%*:|"<>]/g, "-").trim() || "diagram";
  }
  ```

- [ ] T034-Refactor

### Task 35: 导出接入（fitView + loading 状态）

**Files:**
- Modify: `frontend/src/components/studio/diagrams/ReactFlowRenderer.tsx`
- Modify: `frontend/src/components/studio/diagrams/DiagramDetailView.tsx`

- [ ] T035 在 `ReactFlowRenderer.exportToPng()` 中先调用 `fitView`，等待下一帧后再截图

  ```typescript
  useImperativeHandle(ref, () => ({
    exportToPng: async () => {
      fitView({ padding: 0.1, duration: 0 });
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await exportReactFlowToPng(containerRef.current!, diagram.title);
    },
  }));
  ```

  在 `DiagramDetailView` 中：导出按钮点击时设置 `isExporting = true`，导出完成/失败后重置；失败时 toast 提示 `studio.diagrams.exportError`。

---

## Phase 11: Slash 命令集成 + QueryKey 失效

### Task 36: /mindmap 等命令条目注册

**Files:**
- Modify: `frontend/src/lib/slash-commands/registry.ts`（或现有 slash 命令注册文件）

- [ ] T036 在现有 slash 命令注册表中追加图表命令条目

  ```typescript
  {
    command: "/mindmap",
    label: t(uiStrings.slashCommands.mindmap.label),
    description: t(uiStrings.slashCommands.mindmap.description),
    available: true,
  },
  {
    command: "/flowchart",
    label: t(uiStrings.slashCommands.flowchart.label),
    description: t(uiStrings.slashCommands.flowchart.description),
    available: false,   // 显示为"即将推出"，不可点击
  },
  {
    command: "/sequence",
    label: t(uiStrings.slashCommands.sequence.label),
    description: t(uiStrings.slashCommands.sequence.description),
    available: false,
  },
  ```

### Task 37: SSE done 事件后刷新图表列表

**Files:**
- Modify: `frontend/src/lib/hooks/useChatStream.ts`（或 SSE 事件处理器）

- [ ] T037 在 SSE `done` 事件处理逻辑中，检测本次会话的 `active_skill` 是否为图表类型

  若 `active_skill` 属于 `["mindmap", "flowchart", "sequence"]`，则 invalidate `["diagrams", notebookId]` queryKey，触发图表列表自动刷新。

---

## Phase 12: 集成与收尾

### Task 38: Notebook 删除级联清理 MinIO

**Files:**
- Modify: `newbee_notebook/application/services/notebook_service.py`（或 Notebook 删除逻辑）

- [ ] T038 在 Notebook 删除流程中，先列出所有关联图表，逐一删除 MinIO 文件，再依赖数据库 CASCADE 清除 `diagrams` 表记录

  数据库 CASCADE 已由 `diagrams.notebook_id` 外键的 `ON DELETE CASCADE` 保证；MinIO 文件需手动清理。

### Task 39: Document 删除 → 从 document_ids 移除

**Files:**
- Modify: `newbee_notebook/application/services/document_service.py`（或 Document 删除逻辑）

- [ ] T039 在 Document 删除后，执行 `UPDATE diagrams SET document_ids = array_remove(document_ids, $1) WHERE $1 = ANY(document_ids)` 移除关联

  此操作不删除图表本身，仅更新 `document_ids` 数组。

### Task 40: E2E 冒烟测试

**Files:**
- Create: `newbee_notebook/tests/e2e/test_diagram_smoke.py`

- [ ] T040 编写端到端冒烟测试（后端集成测试）

  测试流程：
  1. 创建 Notebook + 上传 Document
  2. 直接调用 `DiagramService.create_diagram`（跳过 Agent，使用合法的 mindmap JSON）
  3. 调用 `GET /api/v1/diagrams?notebook_id=X`，确认图表出现
  4. 调用 `GET /api/v1/diagrams/{id}/content`，确认内容正确
  5. 调用 `PATCH /api/v1/diagrams/{id}/positions`，确认坐标更新持久化
  6. 调用 `DELETE /api/v1/diagrams/{id}`，确认图表不再出现于列表

### Task 41: 最终类型检查 + lint + 提交

**Files:**
- 涉及 batch-4 所有新增/修改文件

- [ ] T041 执行最终质量检查

  后端：
  ```bash
  python -m pytest newbee_notebook/tests/unit/application/services/test_diagram_service.py newbee_notebook/tests/unit/skills/diagram/ newbee_notebook/tests/e2e/test_diagram_smoke.py -v
  mypy newbee_notebook/application/services/diagram_service.py newbee_notebook/skills/diagram/ newbee_notebook/api/routers/diagrams.py
  ```

  前端：
  ```bash
  # 先补齐 package.json 依赖与测试脚本
  cd frontend
  npx tsc --noEmit
  npx eslint src/types/diagram.ts src/lib/hooks/use-diagrams.ts src/lib/diagram/ src/components/studio/diagrams/
  npx vitest run src/lib/diagram/
  ```

  全部通过后提交 batch-4 实现代码（use quick commit skill）。
