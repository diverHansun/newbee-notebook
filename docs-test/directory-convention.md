# directory-convention.md

**测试目录组织规范**

本文档定义 `newbee_notebook/tests/` 下的目录结构规则。目录结构不只是文件的存放位置，它承载着测试类型的语义——放在哪个目录下，决定了这个测试的运行时机、速度预期和依赖范围。

---

## 一、顶层目录结构

```
newbee_notebook/tests/
├── conftest.py              全局共享 fixtures
├── unit/                    单元测试
├── contract/                契约测试
├── integration/             集成测试
└── smoke/                   冒烟测试
```

每个顶层目录对应 `classification.md` 中定义的一种测试类型。不允许在顶层目录之外直接放置测试文件。

---

## 二、unit/ 的内部结构：镜像源码目录

`unit/` 的子目录结构必须镜像 `newbee_notebook/` 的源码目录结构。

**源码结构**：

```
newbee_notebook/
├── api/
├── application/
│   └── services/
├── core/
│   ├── common/
│   ├── context/
│   ├── engine/
│   ├── llm/
│   ├── mcp/
│   ├── rag/
│   ├── session/
│   ├── skills/
│   └── tools/
├── infrastructure/
│   ├── asr/
│   ├── bilibili/
│   ├── document_processing/
│   ├── persistence/
│   ├── storage/
│   └── tasks/
└── skills/
    ├── diagram/
    ├── note/
    └── video/
```

**对应的测试结构**：

```
unit/
├── api/
├── application/
│   └── services/
├── core/
│   ├── common/
│   ├── context/
│   ├── engine/
│   ├── llm/
│   ├── mcp/
│   ├── rag/
│   ├── session/
│   ├── skills/
│   └── tools/
├── infrastructure/
│   ├── asr/
│   ├── bilibili/
│   ├── document_processing/
│   ├── persistence/
│   ├── storage/
│   └── tasks/
└── skills/
    ├── diagram/
    ├── note/
    └── video/
```

**镜像规则**：
- 源码路径 `newbee_notebook/core/context/compressor.py` → 测试路径 `tests/unit/core/context/test_compressor.py`
- 如果一个源码目录下没有需要测试的文件，不需要创建对应的测试目录
- 测试文件名以 `test_` 前缀加上被测模块名，例如 `test_compressor.py`
- 当一个源码文件的测试用例过多时，可以拆分为多个测试文件，使用描述性后缀区分，例如 `test_document_service_content_guard.py` 和 `test_document_service_diagram_cleanup.py`

---

## 三、contract/ 的内部结构：按接口类型组织

`contract/` 按接口协议类型组织，而非镜像源码结构。

```
contract/
├── api/                HTTP API 契约（FastAPI Router 测试）
└── mcp/                MCP 协议契约（如需要时创建）
```

**命名规则**：
- Router 测试以被测 router 名命名：`test_notes_router.py`、`test_diagrams_router.py`
- 如果一个 router 的契约测试过多，按关注点拆分：`test_documents_router_storage_redirects.py`

---

## 四、integration/ 的内部结构：按集成场景组织

`integration/` 按被集成的组件或场景组织。

```
integration/
├── core/
│   └── mcp/            MCP 协议的真实集成
├── storage/            存储层的真实集成
└── test_chat_engine_integration.py    引擎级完整集成
```

集成测试的组织相对灵活，因为集成测试天然跨越多个模块。关键原则是：**文件名或目录名应能让读者快速理解「哪些组件被集成在一起」**。

---

## 五、smoke/ 的内部结构：扁平组织

`smoke/` 通常文件较少，采用扁平结构即可，无需子目录。

```
smoke/
├── test_docker_compose_stack.py
├── test_dependency_manifests.py
├── test_db_init_script.py
└── test_migrate_to_minio_script.py
```

---

## 六、__init__.py 规则

每个测试目录（包括所有中间目录）都必须包含 `__init__.py` 文件。内容为空即可，但文件必须存在，否则 pytest 的模块发现机制可能失效。

新建测试子目录时，必须同时创建 `__init__.py`。

---

## 七、conftest.py 分层规则

conftest.py 的放置遵循 pytest 的作用域继承机制。原则是：**fixture 应放在使用它的最小公共祖先目录中**。

### 各层级的 conftest 职责

| 位置 | 职责 | 示例 fixture |
|------|------|-------------|
| `tests/conftest.py` | 全局共享、所有测试类型通用的 fixture | project_root_path、data_dir |
| `tests/unit/conftest.py` | 仅 unit 测试共享的 fixture | mock 工厂函数、通用 stub |
| `tests/contract/conftest.py` | 仅 contract 测试共享的 fixture | TestClient 实例、mock service 工厂 |
| `tests/integration/conftest.py` | 仅 integration 测试共享的 fixture | 真实数据库连接、testcontainers 配置 |
| `tests/unit/core/context/conftest.py` | 仅该子目录内共享的 fixture | 特定模块的测试数据构造器 |

### 禁止事项

- 不要在 `tests/conftest.py` 中放置仅某一类测试使用的 fixture
- 不要在子目录 conftest 中重复定义上级 conftest 已有的 fixture
- 不要创建「万能 conftest」——如果一个 conftest 超过 200 行，应考虑拆分或下沉到更具体的子目录

---

## 八、新增测试文件的决策流程

当需要为一段代码编写测试时：

1. **判断测试类型**：参照 `classification.md` 的决策流程，确定测试属于 unit / contract / integration / smoke
2. **确定目录位置**：
   - unit → 镜像源码路径
   - contract → 按接口协议类型
   - integration → 按集成场景
   - smoke → 直接放在 smoke/ 下
3. **检查目录是否存在**：如不存在，创建目录并添加 `__init__.py`
4. **命名测试文件**：`test_` + 被测模块或场景名
5. **检查是否需要新 conftest**：如果新测试需要的 fixture 在当前目录层级尚不存在，且会被同级其他测试复用，则创建或更新对应层级的 conftest.py

---

## 九、目录维护

### 定期清理

当源码模块被删除或重命名时，对应的测试目录和文件也应同步删除或重命名。空的测试目录（只有 `__init__.py`）应被清理。

### 归类检查

如果发现测试文件被放置在错误的目录中（例如一个 router 契约测试放在了 `unit/` 下），应将其迁移到正确的位置。迁移时注意更新相关的 import 路径。
