# llm_title_aided 前端模块 test.md

本文档说明如何验证本前端模块在真实协作环境中是可信的。该文档基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[data-model.md](data-model.md)、[dfd-interface.md](dfd-interface.md) 与 [non-functional.md](non-functional.md)。

---

## 一、Module Test Profile（模块测试档案）

- **模块原型**：服务编排模块（在已有 React Query mutation 编排上叠加一个开关）。本模块没有独立的纯逻辑或桥接组件，唯一的"接口"是后端 Config API，且该接口已由 backend 模块负责契约测试。
- **主要测试类型**：unit（前端组件）+ smoke（后端真实接口的端到端确认）。
- **Mock 边界**：
  - `lib/api/config.ts` 全部 mock；前端组件测试中不发起真实 HTTP。
  - React Query 客户端使用项目既有 test fixture。
  - 后端契约测试不归属本前端模块，归属 `backend-v4/llm_title_aided/test.md`。
- **测试归属目录**：
  - `frontend/src/components/layout/model-config-panel.test.tsx`（已存在；本模块仅追加 case）

---

## 二、Test Scope（测试范围）

### 覆盖

- toggle 在 mode=local 时正确渲染；在 mode=cloud 时不渲染。
- toggle 的 aria-checked 与 draft.title_aided_enabled 同步。
- 切换 toggle 触发 `updateMinerUConfig({ title_aided_enabled })`，且不携带 mode 字段。
- mutation 失败时 draft 回滚、错误 banner 显示。
- reset 后 toggle 恢复为后端默认（false）。
- LLM api_key_set=false 时，开启状态下显示提示文案；关闭状态下不显示提示。
- 三条 i18n 键在 zh / en 都有文本。

### 不覆盖

- 后端 `mineru.title_aided_enabled` 的持久化、默认值、cloud/local 边界（属于 backend 测试）。
- LLM api_key_set 的真值（属于 LLM 配置模块）。
- model-config-panel 的整体渲染、其他卡片的行为（属于该面板自身测试）。

---

## 三、Critical Scenarios（关键场景）

### 1. 渲染条件
- mineru.mode=local & local_enabled=true → toggle 节渲染。
- mineru.mode=local & local_enabled=false → toggle 节不渲染。
- mineru.mode=cloud（任何 local_enabled）→ toggle 节不渲染。

### 2. 初始映射
- 后端响应 `title_aided_enabled=true` → toggle aria-checked="true"。
- 后端响应 `title_aided_enabled=false` → toggle aria-checked="false"。
- 后端响应缺失字段（旧后端） → toggle aria-checked="false"，不抛错。

### 3. 切换交互
- 关闭态下点击 → 立即变为开启态（乐观）；mock 拦截到 `PUT /config/mineru` 请求体只含 `{ title_aided_enabled: true }`。
- mutation 成功 → toggle 保持开启，错误 banner 不出现。
- mutation 失败（4xx/5xx）→ toggle 回到关闭态；错误 banner 显示后端 error message。
- 连击两次（开 → 关 → 开）：每次都触发独立 PUT；最终态与最后一次一致；中途失败回滚到正确 snapshot。

### 4. mode 切换联动
- mode 从 local 切到 cloud → toggle 节消失；title_aided_enabled draft 字段不被前端清空。
- mode 从 cloud 切回 local → toggle 节重新出现，显示 backend 真值。

### 5. Reset
- 点击 Restore Defaults → resetMinerUMutation 命中；onSuccess 后 toggle 显示 defaults.title_aided_enabled（默认 false）。

### 6. LLM key 提示
- title_aided_enabled=true 且 llm.api_key_set=false → 提示文字渲染。
- title_aided_enabled=true 且 llm.api_key_set=true → 提示文字不渲染。
- title_aided_enabled=false → 提示文字不渲染（无论 api_key_set）。

### 7. i18n
- 切换语言到 zh：`mineruTitleAidedLabel` 等三键显示中文。
- 切换语言到 en：三键显示英文。
- 没有 fallback 到 key 名的渲染。

### 8. 无障碍
- toggle 元素有 `role="switch"` 与 `aria-checked`。
- 描述文字与 toggle 通过 aria-describedby 关联。
- 键盘 Space / Enter 都能切换 toggle。

---

## 四、Integration Points（集成点测试）

### 1. 与 Config API client
- 验证 toggle handler 调用的是 `updateMinerUConfig`（不是 LLM/ASR/Embedding 的 update），且 payload 形如 `{ title_aided_enabled: <bool> }`。
- 验证 reset handler 调用的是 `resetMinerUConfig`，不会顺带触发其他 reset。

### 2. 与 React Query
- mutation onSuccess 后 `["models-config"]` 缓存被更新；下次渲染读到的 mineru.title_aided_enabled 是 mutation 响应中的值。
- mutation onError 后缓存不被错误响应污染（仍保持上一次成功的 snapshot）。

### 3. 与 model-config-panel 现有错误 banner
- mutation 失败时错误 banner 出现；新切换其他卡片不会让错误 banner 错位关联。

### 4. 与 LLM 卡片状态
- 当 LLM 卡片自身的 mutation 把 api_key_set 由 true 变 false（例如切换到没填 key 的 provider），toggle 下方的提示文字应在 next render 即时出现。

---

## 五、Verification Strategy（验证策略）

- **单元测试**：vitest + testing-library。沿用 [model-config-panel.test.tsx](../../../frontend/src/components/layout/model-config-panel.test.tsx) 既有 fixture；新增上述 8 类 case。
- **mock 策略**：mock `lib/api/config` 模块的 4 个函数（getModelsConfig / getAvailableModels / updateMinerUConfig / resetMinerUConfig），断言调用参数与次数。
- **端到端 smoke**：手动验证一次"切换 mode local → 出现 toggle → 切 toggle → 刷新页面 → toggle 状态保持"，由开发者在引入或修改本模块时执行；不进 CI。
- **CI 标记**：unit 测试随 frontend lint/test pipeline 一起跑；smoke 不进 CI。
- **可访问性验证**：testing-library 自带 axe 集成（如项目已配）或断言 ARIA 属性手工检查。

---

## 六、文档自检

- [x] 已声明模块原型（轻量服务编排）。
- [x] 关键职责（D1–D7）每条都有对应验证场景：
  - D1 类型扩展 → 类型检查由 tsc 兜底，单元测试间接验证。
  - D2 渲染开关 → 场景 1。
  - D3 PUT 切换 → 场景 3、集成点 1。
  - D4 reset 联动 → 场景 5。
  - D5 LLM key 提示 → 场景 6、集成点 4。
  - D6 mode!=local 不渲染 → 场景 1、4。
  - D7 i18n → 场景 7。
- [x] mock 边界明确：不打真实后端。
- [x] 测试归属目录与现有 frontend 测试位置一致，不另开目录。
