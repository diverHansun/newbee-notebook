# llm_title_aided 前端模块 non-functional.md

本文档列出本前端模块在功能正确之外必须满足的工程约束。模块极轻，本份文档比 sibling 模块更短。

---

## 一、Quality Priorities（质量优先级）

按重要性从高到低：

1. **与现有面板交互范式一致**优先于"为这个开关做差异化体验"。toggle 的乐观更新、错误回滚、reset 联动、disabled 行为都沿用现有 LLM/ASR/Embedding/MinerU 卡片的同一套范式。
2. **可见性边界**优先于功能丰富。mode != local 时整体不渲染，不画 disabled 状态、不出 tooltip。
3. **可访问性**不打折。toggle 必须有 `role="switch"`、`aria-checked`、键盘可达；提示文字与 toggle 关联（aria-describedby）。
4. **i18n 完备**优先于硬编码英文。新增的三条 uiStrings 必须 zh + en 同时落字，缺字回退到 key 名是不可接受的。

---

## 二、Operational Constraints（运行约束）

### 1. UI 性能

- toggle 切换的乐观更新必须立即反馈（< 16ms 渲染一帧）。
- 不为 toggle 引入额外的网络请求（如不发 LLM ping）。

### 2. 错误处理

- mutation 失败时的错误信息显示沿用 model-config-panel 现有的 error banner。
- 不允许让 toggle 卡在"中间态"——任何错误必须把 draft 拉回 snapshot。

### 3. 资源

- 不引入新依赖（不接入 Radix / shadcn / mui Switch 等）。
- 不在 panel 之外的地方挂任何全局事件监听。

### 4. 国际化

- 文案 keys：
  - `controlPanel.mineruTitleAidedLabel`：开关标签
  - `controlPanel.mineruTitleAidedDescription`：开关下方说明文字
  - `controlPanel.mineruTitleAidedRequiresLLMKey`：LLM key 缺失时的提示
- 每条键必须 zh + en 双语完整。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 1. 失败语义

- mutation 失败 → 错误 banner 显示 + draft 回滚 + toggle 视觉态恢复。
- 后端响应中 `title_aided_enabled` 字段缺失时，按 false 兜底（防止旧后端响应导致 React 报错）。
- 后端校验失败（mode 与 title_aided_enabled 同时为 None）→ 前端不会发出此请求；如出现，按 4xx 错误 banner 处理。

### 2. 不可接受的失败

- toggle 显示状态与服务端真值长期不一致（乐观更新失败后未回滚）。
- 切换 mode 到 cloud 后，原 title_aided_enabled 真值在后端被清掉（前端不应触发这种行为）。
- toggle 在 cloud 模式下仍渲染。

### 3. 可观测性

- 错误进入 model-config-panel 现有 error banner，不需要额外日志或埋点。
- 当前阶段不为 toggle 切换增加埋点；如需后续观察使用频率，可在埋点统一接入时一并加。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 1. 不实现"切换 mode 自动开启 title_aided"的智能默认

每次用户切回 local 时，title_aided_enabled 显示的是后端持久的真值，不在前端做"提示一下要不要开"。理由：用户已经在 backend 那边明确过单一开关的克制设计。

### 2. 不在面板外做"功能引导"

不弹气泡、不在首页 banner 提示。理由：goals-duty N6 已禁止。

### 3. 不为开关增加 confirm dialog

切换时直接生效（与切 mode 一致）。理由：误操作代价低（直接关回去即可）。

### 4. 暂不为 toggle 增加历史/审计日志

后续若需要观察"用户多久切换一次"，由专门的埋点模块负责，不在本模块内实现。
