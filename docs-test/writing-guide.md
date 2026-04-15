# writing-guide.md

**测试代码编写规范**

本文档定义编写测试代码时的决策规则，重点解决三个问题：mock 边界怎么划、fixture 怎么用、断言怎么写。

---

## 一、Mock 边界原则

Mock 的本质是「用一个可控的替身替换真实依赖」。用得对，它让测试快速且稳定；用得错，它让测试「永远通过但毫无意义」。

### 核心规则：Mock 边界由测试类型决定

| 测试类型 | Mock 范围 | 真实的部分 |
|---------|----------|----------|
| unit | mock 被测对象的**所有直接依赖** | 仅被测对象本身 |
| contract | mock 被测接口之下的**整个业务层** | 接口层本身（Router、协议适配器） |
| integration | **不 mock**（或仅 mock 不可控的外部服务） | 被集成的所有组件 |
| smoke | 不涉及 mock | 真实环境 |

### 各层级的具体 Mock 指南

#### unit 测试中的 Mock

```
被测：DocumentService.create_document()
Mock：repository（使用 AsyncMock）、storage_backend（使用 MagicMock）、embedding_provider
真实：DocumentService 自身的编排逻辑
```

**原则**：
- mock 到直接依赖，不要穿透。如果 `ServiceA` 依赖 `ServiceB`，`ServiceB` 依赖 `RepositoryC`，测试 `ServiceA` 时只 mock `ServiceB`，不需要 mock `RepositoryC`
- 使用 `unittest.mock.AsyncMock` 处理异步依赖
- 使用 `monkeypatch` 替换模块级函数或配置值
- mock 的返回值应尽量接近真实类型（使用领域对象而非裸字典），避免 mock 掩盖类型错误

#### contract 测试中的 Mock

```
被测：POST /api/v1/documents 端点
Mock：DocumentService（整个 service 层）
真实：Router 函数、FastAPI 的请求解析和响应序列化、TestClient 的 HTTP 通信
```

**原则**：
- 使用 FastAPI 的 `app.dependency_overrides` 注入 mock service
- mock service 的返回值应严格匹配真实 service 的返回类型
- 不要 mock FastAPI 框架本身（如请求解析、响应序列化），这些是契约的一部分

#### integration 测试中的 Mock

```
被测：ChatEngine 从接收消息到返回响应的完整链路
Mock：仅外部 LLM API（不可控且计费）
真实：Engine、SessionManager、ToolRegistry、MCP Client
```

**原则**：
- 只 mock 不可控的外部服务（第三方 API、计费服务）
- 数据库使用测试专用实例或 testcontainers，不 mock
- 文件系统使用 `tmp_path` fixture，不 mock

### 禁止事项

- 不要 mock 被测对象本身的方法（这会让测试失去意义）
- 不要使用 `mock.patch` 的自动递归 mock（`spec=True` 时的 `autospec`）来绕过类型检查
- 不要在 unit 测试中使用真实的网络请求或数据库连接
- 不要仅因为 mock「写起来太麻烦」就把 unit 测试改成 integration 测试

---

## 二、Fixture 使用约定

### Fixture 的作用域选择

| scope | 适用场景 | 示例 |
|-------|---------|------|
| `function`（默认） | 每个测试用例独立创建，互不干扰 | mock service 实例、临时数据 |
| `class` | 一组相关测试共享同一个设置 | 同一 TestClient 的多个端点测试 |
| `session` | 整个测试会话共享，创建成本高 | 项目根路径、配置目录路径 |

**原则**：默认使用 `function` scope。只有当 fixture 的创建成本显著（如启动数据库容器）且测试用例之间不会互相污染状态时，才使用更大的 scope。

### Fixture 的命名规范

- 使用描述性名称，说明 fixture 提供的是什么：`mock_document_service`、`sample_document`、`test_db_session`
- 不使用缩写：`doc_svc` 不如 `mock_document_service` 清晰
- mock 类 fixture 以 `mock_` 前缀标识
- 数据构造类 fixture 以 `sample_` 或 `fake_` 前缀标识

### Fixture 的放置

参见 `directory-convention.md` 第七节的 conftest 分层规则。核心原则：fixture 放在使用它的最小公共祖先目录的 conftest.py 中。

---

## 三、断言编写规范

### 断言应验证行为，不验证实现

```python
# 正确：验证行为结果
assert result.status == DocumentStatus.PROCESSED
assert len(result.chunks) > 0

# 错误：验证内部实现细节
assert service._internal_counter == 3
assert mock_repo.save.call_args[0][0]._private_field == "value"
```

### 断言应具体，不使用 truthy 检查

```python
# 正确：具体断言
assert response.status_code == 201
assert response.json()["id"] == expected_id

# 错误：模糊断言
assert response.ok
assert response.json()
```

### Mock 调用验证的使用原则

验证 mock 被调用（`assert_called_once_with`）是合理的，但应克制使用。

**适合验证调用的场景**：
- 验证副作用是否被触发（如：删除文档时是否调用了 storage.delete）
- 验证调用顺序（如：先写入数据库，再触发异步任务）

**不适合验证调用的场景**：
- 验证内部方法的调用次数（这是实现细节）
- 验证传参的具体值（如果可以通过返回值验证结果，优先用返回值）

### 异常测试

使用 `pytest.raises` 验证异常类型和消息：

```python
with pytest.raises(DocumentNotFoundError, match="doc-123"):
    await service.get_document("doc-123")
```

不要捕获异常后手动 assert，这样会在异常未抛出时静默通过。

---

## 四、测试用例的组织

### 一个测试函数验证一个行为

```python
# 正确：一个函数一个行为
def test_create_document_returns_new_id():
    ...

def test_create_document_rejects_unsupported_type():
    ...

# 错误：一个函数验证多个不相关的行为
def test_create_document():
    # 验证正常创建
    ...
    # 验证文件类型校验
    ...
    # 验证重复检测
    ...
```

### 测试函数命名

格式：`test_<被测行为>_<预期结果>` 或 `test_<被测对象>_<场景>_<预期结果>`

```python
def test_compressor_truncates_at_token_limit():
def test_create_document_with_invalid_type_returns_400():
def test_session_lock_prevents_concurrent_access():
```

名称应能让读者不看测试体就知道这个测试验证的是什么。

### 使用 class 分组相关测试

当多个测试用例围绕同一个被测对象或场景时，使用 class 分组：

```python
class TestDocumentServiceCreate:
    def test_returns_new_document_with_id(self):
        ...

    def test_rejects_unsupported_file_type(self):
        ...

    def test_triggers_embedding_task_on_success(self):
        ...
```

---

## 五、异步测试

项目中大量使用 async/await。异步测试的约定：

- 使用 `asyncio.run()` 在同步测试函数中执行异步代码，或使用 `pytest-asyncio` 的 `@pytest.mark.asyncio` 装饰器
- 当前项目的惯例是使用 `asyncio.run()` 包装，保持与现有测试的一致性
- mock 异步函数使用 `AsyncMock`，不要使用 `MagicMock` 配合返回 coroutine 的方式

---

## 六、测试数据

### 使用工厂函数构造测试数据

当多个测试需要相同类型的测试数据时，使用工厂函数而非复制粘贴：

```python
def make_document(
    doc_id: str = "test-doc-1",
    title: str = "Test Document",
    status: DocumentStatus = DocumentStatus.UPLOADED,
) -> Document:
    return Document(document_id=doc_id, title=title, status=status, library_id="lib-1")
```

### 测试数据原则

- 测试数据应尽量接近真实数据的结构，但值可以简化
- 不要使用生产数据（包括脱敏后的）作为测试数据
- 每个测试用例应自包含其所需的数据，不依赖其他测试的运行结果
