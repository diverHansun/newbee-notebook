# llm_title_aided 模块 architecture.md

本文档描述 `llm_title_aided` 模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：只服务 MinerU local/GPU 模式、不改造 cloud 模式、复用聊天 LLM 配置、只暴露一个用户开关、不实现 Newbee 自有标题分级后处理。

---

## 一、Architecture Overview（总体架构）

`llm_title_aided` 模块采用“Newbee 负责配置编排，MinerU 本地运行时负责标题分级执行”的结构。

模块由六个子组件协作完成“读取设置 → 判断 local 生效条件 → 复用聊天 LLM 配置 → 写入 MinerU runtime config → 本地 mineru-api 动态读取 → MinerU 自行执行 llm_aided_title”的职责。

1. **Settings Surface（设置入口）**：在现有模型配置接口中增加 MinerU title aided 开关；设置面板只展示一个开关，不展示独立模型配置。
2. **Runtime Guard（生效条件守卫）**：判断当前是否为 MinerU local 模式、本地 MinerU 是否可用、用户是否开启开关、聊天 LLM 是否具备可用 API key。
3. **LLM Config Bridge（聊天 LLM 配置桥）**：复用现有聊天 LLM runtime config，把 provider / model / api_key / base_url 转换成 MinerU 可理解的 `title_aided` 配置。
4. **MinerU Title Config Writer（MinerU 配置写入器）**：把 title aided 配置原子写入本地运行时配置文件；该文件位于 `data/mineru/`，不进入 git。
5. **Local MinerU Runtime Adapter（本地 MinerU 运行时适配）**：在 Newbee 自己的 `mineru-api` Docker 镜像中加入轻量兼容适配，使 hybrid/GPU 后端在解析时动态读取 title aided 配置，而不是只在进程 import 阶段缓存一次。
6. **Document Pipeline Integration（文档处理链路接入）**：文档任务在调用本地 MinerU 之前同步 MinerU 与 LLM runtime 配置；cloud converter 不经过该路径。

### 高层依赖关系

```text
setting_panel
  -> Config API
    -> app_settings: mineru.title_aided_enabled

document task
  -> Runtime Guard
  -> LLM Config Bridge
  -> MinerU Title Config Writer
  -> MinerULocalConverter
  -> local mineru-api
  -> MinerU llm_aided_title()
  -> markdown / metadata assets / content_list
```

### local 与 cloud 的分界

```text
MINERU_MODE=local
  Newbee 写 runtime config
  local mineru-api 动态读取 config
  MinerU 执行 llm_aided_title()

MINERU_MODE=cloud
  Newbee 不写 title aided 请求参数
  cloud converter 保持现有 v4 Smart Parsing API
  不要求 local mineru-api 存在
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Facade / Coordinator：标题增强配置编排器

模块对文档处理链路只暴露“准备本地 MinerU title aided runtime”这一件事。内部如何读开关、解析 LLM、写配置、记录日志，都由该编排器隐藏。

这样服务于 goals-duty **G3（复用聊天 LLM 配置）** 和 **D3 / D4（同步 MinerU 本地 title aided 配置）**。

### 2. Guard Clause：local-only 生效守卫

标题增强的第一层判断始终是 MinerU 模式。只要当前是 cloud，就直接跳过 title aided 准备，不尝试写 cloud 参数，也不走 Newbee 后处理。

这样服务于 goals-duty **G1 / G2 / D5（只接入 local，不改造 cloud）**。

### 3. Adapter：把聊天 LLM runtime 转成 MinerU title_aided config

Newbee 内部聊天 LLM 配置和 MinerU `title_aided` 配置不是同一种结构。Adapter 负责把现有 runtime config 转为 MinerU 需要的字段：

- `model`
- `api_key`
- `base_url`
- `enable`

它不决定模型，也不覆盖用户选择，服务于 goals-duty **G3 / G4 / N4**。

### 4. Atomic Runtime Config Writer：避免半写入配置

MinerU 本地配置文件包含 API key，且会被另一个容器读取。写入时采用“临时文件 → 原子替换”的策略，避免 `mineru-api` 读到半截 JSON。

它服务于 goals-duty **G5（增强失败不破坏基础解析）** 和 **D8（可诊断但不泄露密钥）**。

### 5. Local Runtime Adapter：选择本地适配而不是要求用户手动重启

MinerU 本地 `/file_parse` 没有请求级 `title_aided` 参数，title aided 来自运行时配置文件。同时，MinerU hybrid/GPU 后端当前存在 import 阶段读取 title aided 配置的行为。

如果 Newbee 只写 `mineru.json`，会出现两个问题：

- 用户在设置面板打开开关后，已启动的 `mineru-api` 可能不会立刻生效。
- 用户切换聊天 LLM 模型后，已启动的 `mineru-api` 可能仍使用旧模型配置。

因此本模块采用 Newbee 本地 Docker 镜像内的轻量 runtime adapter，让本地 `mineru-api` 在解析阶段读取共享 runtime config。这样用户无需理解 MinerU 配置文件和容器重启细节。

该设计服务于 goals-duty **G4（用户只面对一个开关）** 和 **D4（同步策略在架构中定义）**。

### 6. No Post-Processing Strategy：不在 Newbee 侧改写结果

本阶段不在 Newbee 侧读取 `content_list.json` 后再调用 LLM 改写标题层级。原因是这会让 local 与 cloud 的边界变模糊，也会让 Newbee 承担标题层级算法职责。

这服务于 goals-duty **N2（不实现 Newbee 自有标题分级算法）** 和 **N8（不改变索引职责）**。

### 7. Default Model Update：Zhipu 默认模型作为 LLM preset 的关联演进

`glm-5v-turbo` 是 Zhipu provider 的默认聊天模型调整，不是 title aided 的隐藏专用模型。用户如果手动选择其他 Zhipu 模型，title aided 仍尊重聊天 LLM 当前选择。

这服务于 goals-duty **G7 / D7**。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

### 后端配置层

```text
newbee_notebook/core/common/config_db.py
```

职责：

- 在 MinerU 配置中增加 `title_aided_enabled`。
- 维护 DB > env > default 的读取顺序。
- 默认值解析应优先使用启动时 bootstrap env，避免被 `apply_mineru_runtime_env()` 后续写回的进程内 runtime env 污染。
- 将有效配置投影到运行时环境。
- reset 时保留 local_enabled 能力守卫，并恢复 title aided 默认值。

```text
newbee_notebook/api/routers/config.py
```

职责：

- `GET /config/models` 返回 MinerU title aided 开关状态。
- `PUT /config/mineru` 接收 mode 与 title aided 开关更新。
- `POST /config/mineru/reset` 恢复 MinerU 默认配置。
- `GET /config/models/available` 将 Zhipu 默认 preset 从 `glm-5` 调整为 `glm-5v-turbo`。

### LLM 配置复用层

```text
newbee_notebook/core/llm/config.py
newbee_notebook/core/llm/zhipu.py
newbee_notebook/configs/llm.yaml
```

职责：

- 继续作为聊天 LLM runtime config 的唯一来源。
- title aided 准备逻辑以 `resolve_llm_runtime_config()` 的结果为准，包括 provider-specific fallback 规则。
- Zhipu 默认模型调整为 `glm-5v-turbo`。
- 保持 provider-specific `api_key` 与 `base_url` 解析逻辑。

### 文档处理接入层

```text
newbee_notebook/infrastructure/tasks/document_tasks.py
```

职责：

- 文档转换前同步 MinerU runtime config。
- 在 local 模式且 title aided 开启时，同步聊天 LLM runtime config。
- 调用 title aided 配置编排器准备本地 MinerU runtime 文件。

```text
newbee_notebook/infrastructure/document_processing/processor.py
```

职责：

- 保持 cloud/local converter 路由职责。
- local 模式仍走 `MinerULocalConverter`。
- cloud 模式不引入 title aided 行为。

```text
newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py
```

职责：

- 继续只负责调用本地 `/file_parse`。
- 不承载 LLM API key。
- 不新增请求级 `title_aided` 表单字段，因为 MinerU 本地 API 当前不支持。

```text
newbee_notebook/infrastructure/document_processing/mineru_title_aided.py
```

职责：

- 新增 title aided 配置编排器。
- 根据 MinerU 配置与 LLM runtime config 生成 MinerU runtime JSON。
- 原子写入 `data/mineru/mineru-runtime.json`。
- local 模式下，只要后续仍会调用 `/file_parse`，开关关闭或 LLM 配置不可用时必须原子写入 disabled config，覆盖任何旧的 enabled 状态。
- cloud 模式下可以完全跳过 runtime 写入，因为 cloud 不读取该文件。
- 日志只记录 provider/model/enabled 状态，不记录 API key。

### 本地 MinerU 容器适配层

```text
docker-compose.gpu.yml
```

职责：

- 将 `data/mineru/` 以只读方式挂载给 `mineru-api`。
- 设置 `NEWBEE_MINERU_TITLE_AIDED_CONFIG_JSON` 指向共享 runtime config 文件，避免覆盖 MinerU 原生 tools config。
- 保持 `MINERU_MODE=local`、`MINERU_LOCAL_ENABLED=true`、`MINERU_BACKEND=hybrid-auto-engine`。

```text
docker/mineru/Dockerfile.gpu
docker/mineru/patches/
```

职责：

- 在 Newbee 自有 `mineru-api` 镜像中应用 local runtime adapter。
- Dockerfile 必须显式复制并应用 runtime adapter patch；仅安装 `mineru[core]` 不足以满足动态读取配置目标。
- 适配目标是让 MinerU hybrid/GPU 后端在解析阶段读取 title aided 配置。
- 适配只属于 Newbee 本地镜像，不修改 MinerU cloud API，也不要求用户维护 MinerU 官方源码。

### 前端轻量入口（后续批次）

本次实现批次只落后端与 GPU 本地运行时。以下前端入口是完整产品方案的一部分，不属于本批代码实施范围。

```text
frontend/src/lib/api/config.ts
frontend/src/components/layout/model-config-panel.tsx
frontend/src/components/layout/model-config-panel.test.tsx
```

职责：

- MinerU config 类型增加 `title_aided_enabled`。
- 设置面板 MinerU 区域增加一个开关。
- LLM provider 切换到 zhipu 时，默认模型改为 `glm-5v-turbo`。
- 不新增 title aided 独立 provider/model/api_key/base_url 输入。
- 前端测试覆盖 Zhipu 默认模型切换和 MinerU title aided 开关 payload。

### 运行时配置文件

```text
data/mineru/mineru-runtime.json
```

职责：

- 作为 worker/API 与本地 `mineru-api` 之间的共享配置文件。
- 包含 MinerU 需要的 `llm-aided-config.title_aided` 片段。
- 位于 `data/*` 下，默认不进入 git。
- 文件中包含 API key，不能输出到日志或文档处理结果。

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 放弃方案：给 MinerU cloud 强行做 title aided

MinerU cloud API 没有公开 `llm_title_aided` 字段。强行在 Newbee 侧做 cloud 后处理会让模块从“接入 MinerU 本地能力”变成“Newbee 自研标题增强”，超出 goals-duty 边界。

代价：cloud 模式仍然保留当前标题层级能力边界。

### 放弃方案：给用户单独配置 title aided LLM

单独配置会引入新的 provider/model/api_key/base_url，并造成“聊天模型”和“标题增强模型”两套心智模型。

代价：如果用户手动选择了不适合 title aided 的聊天模型，标题增强质量可能下降。当前接受这个代价，因为配置一致性优先。

### 放弃方案：只写 mineru.json，要求用户重启 mineru-api

这最简单，但不符合设置面板开关的预期。尤其是 hybrid/GPU 后端存在 import 阶段缓存配置的问题，用户很难判断“开关已保存但为何没生效”。

代价：我们需要维护一个 Newbee 本地 MinerU runtime adapter。这个适配只在本地 Docker 镜像中存在，后续 MinerU 官方如果提供请求级字段或动态配置能力，应优先移除本地适配。

### 放弃方案：在 Newbee 侧改写 content_list / markdown

Newbee 后处理可以同时覆盖 cloud 与 local，但这会让模块承担标题算法职责，并可能造成 markdown、content_list、middle_json 三者不一致。

代价：本阶段只能增强 local/GPU 解析结果，不能增强 cloud 结果。

### 妥协：runtime config 是进程外共享文件

共享文件让 worker/API 与 `mineru-api` 解耦，不需要 Docker socket，也不需要从业务容器控制容器重启。

代价：

- 文件中包含 API key，需要放在 ignored runtime 目录。
- 需要原子写入，避免并发读到半写 JSON。
- 多个并发 MinerU parse 共享同一份配置。v1 依赖 GPU compose 的单并发设置：`MINERU_API_MAX_CONCURRENT_REQUESTS=1` 与 Celery worker concurrency=1。未来如果要支持多并发，需要 MinerU 提供请求级配置或 Newbee 为每个任务隔离 runtime。

### 妥协：增强失败时优先保留基础解析

如果 title aided 开关打开但 LLM API key 缺失，模块不会把半配置交给 MinerU。它应记录 warning，并让基础 MinerU 解析继续。

为了避免旧配置残留，local 模式下该场景必须写入 `enable=false` 的 disabled runtime config，覆盖先前可能存在的 `enable=true` 文件。

代价：用户可能看到“开关打开但结果没有改善”。因此设置面板应复用 LLM 配置摘要中的 `llm.api_key_set`，日志记录 skip reason，但不能泄露密钥。

### 可演进性

- 如果 MinerU 官方未来在 `/file_parse` 增加请求级 `title_aided` 字段，可以移除本地 runtime adapter，改为 local converter 请求级传参。
- 如果 MinerU cloud API 未来公开相同能力，可以在新的 goals-duty 讨论后扩展 cloud，不在当前模块内预留隐藏行为。
- 如果后续 `img-upload` 完成，可继续把 Zhipu 默认多模态模型选择沉淀到 LLM provider preset 策略中，而不是 title aided 模块内。

---

## 五、架构自检

- [x] 每个子组件都能追溯到 goals-duty 中的目标或职责。
- [x] cloud 模式没有被引入新的 title aided 行为。
- [x] 用户侧仍然只有一个 MinerU title aided 开关。
- [x] LLM provider/model/api_key/base_url 复用聊天配置。
- [x] 没有把 Newbee 变成标题分级后处理算法模块。
- [x] 明确说明了为什么需要本地 MinerU runtime adapter。
- [x] 明确说明了共享配置文件的密钥风险和并发边界。
