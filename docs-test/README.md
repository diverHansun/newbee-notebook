# docs-test

**项目级测试方法论**

本目录是 newbee-notebook 项目的测试决策指南，与 `docs-plan/`（设计方法论）和 `docs-implement/`（执行方法论）平级，共同构成项目的工程方法论体系。

---

## 一、定位与职责

`docs-test/` 回答的核心问题是：**在这个项目中，测试决策怎么做？**

它不教测试技术（等价类、边界值、pytest 用法），也不替代模块级的 `test.md`。它提供的是一套**项目级的测试决策框架**，确保所有参与者（人类和 AI）在以下问题上有统一认知：

- 写了一个测试，它属于什么类型？
- 新增一个测试文件，它应该放在哪里？
- 一个依赖应该 mock 还是用真实的？
- CI 的不同阶段应该跑哪些测试？

---

## 二、核心原则

### 1. 测试的目标是建立信心，不是追求覆盖率

覆盖率是手段，不是目的。一个 95% 覆盖率但全是浅层断言的测试套件，不如一个 70% 覆盖率但精准验证了关键路径的套件。测试资源应优先投入在**失败代价最高的路径**上。

### 2. 测试类型服从模块性质

不同模块有不同的测试重心。纯逻辑模块用单元测试验证计算正确性，桥接模块用契约测试验证接口稳定性，基础设施模块用冒烟测试验证环境可用性。一刀切的测试策略是浪费。

模块原型与测试重心的映射规则，参见 `docs-plan/test-guide.md` 第三节。

### 3. Mock 边界由测试类型决定，不由方便程度决定

「用 mock 更方便」不是使用 mock 的理由。mock 的边界应该由测试类型的定义决定：单元测试 mock 直接依赖，契约测试 mock 被测接口之下的一切，集成测试尽量不 mock。

具体的 mock 边界规则，参见 `writing-guide.md`。

### 4. 测试目录结构必须显式维护

测试文件的归类不是「随便放一个能跑就行」。目录结构承载的是测试类型的语义——放在 `unit/` 还是 `contract/` 下，意味着这个测试的运行时机、速度预期、依赖范围都不同。

目录组织的具体规范，参见 `directory-convention.md`。

### 5. 测试是设计的延伸，不是实现的附属

测试在 Plan 阶段就应该被考虑（通过模块的 `test.md`），在 Implement 阶段作为代码的一部分产出，在 CI 中作为质量门禁执行。测试不是「写完代码后补上去的东西」。

---

## 三、与其他文档的关系

```
docs-plan/
  └── test-guide.md       教 AI 如何为单个模块撰写 test.md
                           （Plan 阶段产物：描述"应该怎么测"）
                                  |
                                  v
docs-test/                本目录
  ├── classification.md   定义测试分类体系
  ├── directory-convention.md   定义测试目录组织规范
  ├── writing-guide.md    定义测试代码编写规范
  └── ci-strategy.md      定义 CI 中的测试执行策略
                                  |
                                  v
newbee_notebook/tests/    实际测试代码
  ├── unit/               按 classification.md 的分类组织
  ├── contract/
  ├── integration/
  └── smoke/
```

**信息流向**：

1. `docs-plan/test-guide.md` 中的模块原型分类 → 决定 `classification.md` 中测试类型的选择
2. `classification.md` 中的类型定义 → 决定 `directory-convention.md` 中的目录归属
3. `directory-convention.md` 中的目录规则 → 决定实际测试文件的存放位置
4. `ci-strategy.md` 中的执行策略 → 决定各类型测试在 CI 中的运行时机

---

## 四、文档索引

| 文档 | 回答的问题 |
|------|----------|
| `classification.md` | 测试有哪几种类型？我写的测试属于哪一种？ |
| `directory-convention.md` | 测试文件放在哪里？conftest 怎么分层？ |
| `writing-guide.md` | mock 边界怎么划？fixture 怎么用？断言怎么写？ |
| `ci-strategy.md` | CI 的哪个阶段跑哪些测试？marker 怎么用？ |

---

## 五、适用范围

本方法论适用于 `newbee_notebook/tests/` 下的所有后端测试代码。前端测试（`frontend/` 下）有独立的测试体系，不在本文档覆盖范围内。
