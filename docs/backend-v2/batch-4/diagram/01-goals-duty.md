# 设计目标与职责

## 设计目标

### 目标一：可扩展的图表类型体系

通过 DiagramTypeRegistry 注册机制，将图表类型（mindmap、flowchart、sequence 等）的元数据（格式、校验器、Agent 生成指令）与业务逻辑解耦。batch-4 仅注册 mindmap 类型，新增其他类型时无需修改 DiagramService 主体代码。

### 目标二：内容与坐标分离存储

Agent 生成的图表内容（节点/边结构或 Mermaid 语法）存储在 MinIO，用户通过拖拽调整的节点坐标单独存储在 PostgreSQL JSONB 字段。两者独立更新，AI 重新生成图表不会覆盖用户的布局调整，用户调整坐标也不会触发 MinIO 写操作。

### 目标三：Agent 单一写入路径

图表的创建和内容更新只能通过 Agent Skill 工具调用完成。用户 UI 只能读取、浏览、删除图表，以及调整节点位置。这与 batch-3 中 Note 的操作语义分离原则保持一致。

### 目标四：格式校验闭环

Agent 输出图表内容后，DiagramService 立即调用对应类型的校验器进行格式验证。校验失败时返回具体错误信息，Agent 可根据错误信息重试，最多 3 次。校验逻辑集中在注册表层，不散落在 API 或工具层。

## 模块职责

diagram 模块负责：

- 维护 `diagrams` 数据库表的 CRUD 操作
- 通过 MinIO 服务存取图表内容文件
- 向 Agent 暴露 5 个 Skill 工具（list、read、create、update、delete）
- 通过 DiagramTypeRegistry 管理图表类型注册与格式校验
- 向前端暴露 REST API（列表、内容读取、坐标更新、删除）

diagram 模块不负责：

- Skill 基础设施的实现（SkillRegistry、SkillManifest、ConfirmationGateway 由 batch-3 提供）
- AgentLoop 的确认暂停逻辑（由 batch-3 的 AgentLoop 修改提供）
- 前端渲染逻辑（React Flow、Mermaid 渲染由前端负责）
- 图表导出为图片（由前端 html2canvas 处理）
- 与文档内容（markdown）的直接关联（通过 document_ids 列表间接关联）

## 非目标

- batch-4 不实现 Mermaid 类型图表的后端校验（Mermaid 类型预留注册位，校验器实现推迟到对应 batch）
- batch-4 不实现图表版本历史
- batch-4 不实现图表的协作编辑
- batch-4 不实现图表内容的语义搜索
