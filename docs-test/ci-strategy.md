# ci-strategy.md

**CI 测试执行策略**

本文档定义测试在 CI/CD 流水线中的执行时机和 pytest marker 的使用规范。

---

## 一、Marker 定义

所有可用的 pytest marker 定义在 `pytest.ini` 中：

| marker | 含义 | 执行速度预期 |
|--------|------|------------|
| `unit` | 单元测试 | 极快（整个 suite 秒级） |
| `contract` | 契约测试 | 快（单文件秒级） |
| `integration` | 集成测试 | 较慢（可能需要秒级到分钟级） |
| `smoke` | 冒烟测试 | 取决于环境（可能需要 Docker） |
| `slow` | 执行时间长的测试（叠加标记） | 超过 10 秒 |
| `requires_api` | 需要外部 API 的测试（叠加标记） | 取决于 API 响应 |

### 基础 marker 与叠加 marker

- `unit`、`contract`、`integration`、`smoke` 是**基础 marker**，每个测试必须且只能有一个
- `slow`、`requires_api` 是**叠加 marker**，可以与任何基础 marker 组合使用

```python
@pytest.mark.integration
@pytest.mark.slow
def test_full_document_pipeline():
    """集成测试且执行时间长"""
    ...

@pytest.mark.unit
@pytest.mark.requires_api
def test_llm_client_response_parsing():
    """单元测试但需要真实 API"""
    ...
```

---

## 二、Marker 标注方式

### 方式一：逐文件标注（推荐用于混合文件）

在文件顶部使用 `pytestmark` 变量为整个文件标注：

```python
import pytest

pytestmark = pytest.mark.unit
```

### 方式二：逐函数标注

当同一文件中需要不同的叠加 marker 时，在函数级别标注：

```python
pytestmark = pytest.mark.unit

def test_basic_parsing():
    ...

@pytest.mark.requires_api
def test_api_response_parsing():
    ...
```

### 方式三：基于目录的自动标注（可选）

可以在各层级 conftest.py 中使用 `pytest_collection_modifyitems` 钩子，根据文件路径自动添加基础 marker。此方式能避免每个文件都手动声明 `pytestmark`：

```python
# tests/unit/conftest.py
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.unit)
```

如果使用此方式，应在所有四个顶层测试目录的 conftest.py 中一致配置。

---

## 三、CI 各阶段的执行策略

### 阶段总览

| 触发时机 | 执行范围 | 命令 | 目标 |
|---------|---------|------|------|
| 本地开发（保存后） | 当前修改相关的 unit 测试 | `pytest tests/unit/core/context/ -x` | 即时反馈 |
| 提交前 | 全部 unit | `pytest -m unit` | 确保基本逻辑不破坏 |
| PR 检查 | unit + contract | `pytest -m "unit or contract"` | 确保逻辑和接口契约完整 |
| 合并到主分支 | unit + contract + integration | `pytest -m "unit or contract or integration"` | 确保组件协作正确 |
| 部署后 | smoke | `pytest -m smoke` | 确保环境正常 |

### 排除慢测试

日常开发中，可以排除标记为 `slow` 的测试以加快反馈速度：

```bash
pytest -m "unit and not slow"
```

### 排除需要 API 的测试

在没有 API 密钥的环境中：

```bash
pytest -m "not requires_api"
```

---

## 四、执行速度预算

各类型测试应遵守的执行时间预算：

| 类型 | 单文件上限 | 整个 suite 上限 |
|------|----------|---------------|
| unit | 3 秒 | 30 秒 |
| contract | 5 秒 | 60 秒 |
| integration | 30 秒 | 5 分钟 |
| smoke | 视环境而定 | 视环境而定 |

如果某类测试的执行时间超过预算，应排查原因：
- unit 测试超时通常意味着它不应该是 unit 测试（可能有未 mock 的 I/O）
- contract 测试超时通常意味着 service mock 不够彻底
- integration 测试超时通常意味着需要标记 `@pytest.mark.slow`

---

## 五、失败处理

### unit 或 contract 测试失败

**阻断等级：阻断提交和合并。**

这两类测试的失败意味着核心逻辑或接口契约被破坏，必须在提交前修复。

### integration 测试失败

**阻断等级：阻断合并到主分支。**

集成测试失败可能由组件间的交互问题导致。允许在开发分支上暂时存在，但必须在合并前修复。

### smoke 测试失败

**阻断等级：阻断部署发布。**

冒烟测试失败意味着环境配置有问题，不影响开发但阻止部署。

---

## 六、本地开发的常用命令

```bash
# 运行所有 unit 测试
pytest -m unit

# 运行特定模块的 unit 测试
pytest tests/unit/core/context/

# 运行所有 unit 和 contract 测试（模拟 PR 检查）
pytest -m "unit or contract"

# 运行除了需要 API 和慢测试之外的所有测试
pytest -m "not requires_api and not slow"

# 运行并显示覆盖率（需安装 pytest-cov）
pytest -m unit --cov=newbee_notebook --cov-report=term-missing
```
