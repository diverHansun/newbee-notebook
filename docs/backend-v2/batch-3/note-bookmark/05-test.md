# Note-Bookmark 模块：测试策略

## 1. 测试分层

遵循现有项目的测试模式，按 Service 层和 API 层分别覆盖。

## 2. Service 层单元测试

### 2.1 MarkService

| 测试用例 | 验证点 |
|---------|--------|
| create_mark 正常创建 | 返回完整 Mark 对象，字段正确 |
| create_mark 文档不存在 | 抛出 ValueError |
| create_mark 文档状态为 uploaded | 拒绝创建，抛出异常 |
| create_mark anchor_text 超 500 字符 | 截断至 500 字符 |
| create_mark char_offset 为负数 | 抛出 ValueError |
| list_by_document 排序 | 按 char_offset 升序 |
| list_by_notebook 联查 | 正确通过 notebook_document_refs 关联 |
| count_by_document | 返回正确计数 |
| update_comment | comment 更新成功，其他字段不变 |
| delete_mark | 删除成功，关联 note_mark_refs 级联清理 |

### 2.2 NoteService

| 测试用例 | 验证点 |
|---------|--------|
| create_note 正常创建 | 返回完整 Note 对象 |
| create_note 带 document_ids | 同时创建 note_document_tags |
| update_note partial update | 只更新传入字段，未传入字段保持不变 |
| update_note 仅 content | title 不变（auto-save 场景） |
| delete_note | 删除成功，关联表级联清理 |
| add_document_tag 幂等 | 重复添加不报错，返回已有记录 |
| remove_document_tag | 关联删除，Note 本身不受影响 |
| add_mark_ref 幂等 | 重复添加不报错 |
| add_mark_ref mark 不存在 | 抛出 ValueError |
| list_mark_refs | 返回完整 Mark 对象列表 |
| list_by_notebook | 正确联查，返回相关 Notes |
| list_by_notebook 带 document_id 过滤 | 仅返回该文档关联的 Notes |
| list_by_notebook 无关联 | 返回空列表 |

## 3. API 层集成测试

使用 TestClient + 测试数据库，验证端点的请求/响应契约。

### 3.1 Mark API

| 测试用例 | 方法 | 路径 | 验证点 |
|---------|------|------|--------|
| 创建书签 | POST | /documents/{id}/marks | 201，返回完整对象 |
| 创建书签文档不存在 | POST | /documents/{id}/marks | 404 |
| 查询文档书签 | GET | /documents/{id}/marks | 200，按 offset 排序 |
| 查询 notebook 书签 | GET | /notebooks/{id}/marks | 200，联查正确 |
| 更新评论 | PATCH | /marks/{id} | 200，comment 更新 |
| 删除书签 | DELETE | /marks/{id} | 204 |
| 书签计数 | GET | /documents/{id}/marks/count | 200，count 正确 |

### 3.2 Note API

| 测试用例 | 方法 | 路径 | 验证点 |
|---------|------|------|--------|
| 创建笔记 | POST | /notes | 201 |
| 创建笔记带 document_ids | POST | /notes | 201，关联创建 |
| 获取笔记 | GET | /notes/{id} | 200，含 documents 和 marks |
| 更新笔记 | PATCH | /notes/{id} | 200，partial update |
| 删除笔记 | DELETE | /notes/{id} | 204 |
| 查询 notebook notes | GET | /notebooks/{id}/notes | 200，联查正确 |
| 按文档过滤 notes | GET | /notebooks/{id}/notes?document_id=x | 200，过滤正确 |

### 3.3 关联 API

| 测试用例 | 方法 | 路径 | 验证点 |
|---------|------|------|--------|
| 添加文档标签 | POST | /notes/{id}/documents | 201 |
| 重复添加文档标签 | POST | /notes/{id}/documents | 200，幂等 |
| 移除文档标签 | DELETE | /notes/{id}/documents/{did} | 204 |
| 添加 mark 引用 | POST | /notes/{id}/marks | 201 |
| 移除 mark 引用 | DELETE | /notes/{id}/marks/{mid} | 204 |
| 获取笔记 marks | GET | /notes/{id}/marks | 200，完整 Mark 对象 |

## 4. 级联删除集成测试

| 测试用例 | 验证点 |
|---------|--------|
| 删除 Document 后查询其 marks | marks 为空 |
| 删除 Document 后查询关联 note 的 marks | note_mark_refs 中对应记录消失 |
| 删除 Document 后 note 仍存在 | note_document_tags 删除但 Note 本身保留 |
| 删除 Note 后查询其 document_tags | tags 为空 |
| 删除 Note 后 Mark 仍存在 | Mark 不受 Note 删除影响 |
| 删除 Mark 后 Note 仍存在 | note_mark_refs 删除但 Note 内容不变 |
