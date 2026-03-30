# 实现计划

## 涉及文件

| 文件 | 操作类型 | 说明 |
|------|---------|------|
| `frontend/src/components/notebooks/notebook-workspace.tsx` | 修改 | 删除 `buildRagHint`、`ragHint`、`askBlocked`，移除相关 props |
| `frontend/src/components/chat/chat-panel.tsx` | 修改 | 移除 `askBlocked`/`ragHint` props 和黄色 banner |
| `frontend/src/components/chat/chat-input.tsx` | 修改 | 移除 `askBlocked` prop、禁用逻辑、红色 badge |
| `frontend/src/lib/i18n/strings.ts` | 修改 | 删除 `ragUnavailable` 和 `ragHint` 两条 i18n 条目 |
| `frontend/src/components/chat/chat-input.test.tsx` | 修改 | 移除测试中的 `askBlocked` prop |
| `newbee_notebook/application/services/chat_service.py` | 修改 | 缩小 `rag_modes` 范围、对齐非流式/流式路径守卫逻辑、`validate_mode_for_chat` 增加跳过条件 |
| `newbee_notebook/tests/unit/test_chat_service_guards.py` | 修改 | 更新 Ask 模式相关测试用例 |

## 实现步骤

### 步骤 1：后端 - 修改模式守卫逻辑

修改后端优先于前端，确保 Ask 模式请求不再被 409 拦截后，前端移除预判逻辑才有意义。

- 修改 `chat_service.py` 第 669 行：`rag_modes` 从 `(ASK, CONCLUDE, EXPLAIN)` 改为 `(CONCLUDE, EXPLAIN)`
- 修改 `chat_service.py` 第 201 行附近：非流式路径增加 `if mode_enum not in {ModeType.CHAT, ModeType.AGENT}:` 跳过条件，与流式路径（第 378 行）保持一致
- 修改 `chat_service.py` 第 634-657 行：`validate_mode_for_chat` 方法中增加 `if mode_enum in {ModeType.CHAT, ModeType.AGENT, ModeType.ASK}: return` 提前返回

验证点：后端单元测试通过。

### 步骤 2：后端 - 更新测试

- 更新 `test_chat_service_guards.py` 中 `test_validate_mode_guard_allows_ask_when_completed_docs_exist`：该测试验证"有已完成文档时 Ask 允许"，现在 Ask 在任何情况下都应允许。考虑重命名测试并增加"无已完成文档时 Ask 也不抛错"的断言
- 确认 `test_validate_mode_guard_blocks_explain_when_target_document_is_not_completed` 和 `test_validate_mode_guard_keeps_conclude_selected_text_rule` 不受影响

验证点：全部后端测试通过。

### 步骤 3：前端 - 清理 i18n 字符串

先清理字符串，避免后续步骤引用已删除的 key 导致 TypeScript 编译错误。

- 删除 `strings.ts` 第 66 行 `ragUnavailable` 条目
- 删除 `strings.ts` 第 479-482 行 `ragHint` 条目

### 步骤 4：前端 - 清理 chat-input.tsx

- 从 Props 类型和解构中删除 `askBlocked`
- 删除第 71 行发送拦截：`if (mode === "ask" && askBlocked) return;`
- 简化第 75 行：`const sendDisabled = !input.trim();`
- 删除第 182-186 行红色 badge JSX 块
- 检查并清理因删除 badge 后可能多余的 import

### 步骤 5：前端 - 清理 chat-panel.tsx

- 从 Props 类型和解构中删除 `askBlocked` 和 `ragHint`
- 删除第 168-184 行黄色警告 banner JSX 块
- 删除向 ChatInput 传递的 `askBlocked` prop

### 步骤 6：前端 - 清理 notebook-workspace.tsx

- 删除 `buildRagHint` 函数（第 23-44 行）
- 删除 `ragHint` 和 `askBlocked` 变量（第 54-55 行）
- 从 ChatPanel 的 props 中移除 `askBlocked` 和 `ragHint`
- 检查 `documents` 状态是否仍有其他消费者。如无其他引用，可一并移除 `documents` state、`setDocuments`，以及 SourcesPanel 的 `onDocumentsUpdate` prop。但如果 `onDocumentsUpdate` 用于触发 React Query 的缓存更新或其他副作用，则保留
- 清理多余的 import（`useMemo`、`uiStrings` 等，视实际引用情况）

### 步骤 7：前端 - 更新测试

- 修改 `chat-input.test.tsx` 三处测试用例，移除 `askBlocked={false}` prop
- 运行前端测试确认通过

验证点：前端构建通过 + 全部前端测试通过。

## 实现顺序说明

按步骤 1-7 顺序实现。后端先行（步骤 1-2），确保 API 行为正确后再清理前端（步骤 3-7）。前端内部从底层组件（strings -> chat-input -> chat-panel -> notebook-workspace）自下而上清理，每一步都保持编译通过。

## 注意事项

- 步骤 6 中 `documents` 状态的清理需要谨慎确认。`SourcesPanel` 的 `onDocumentsUpdate` 回调可能被其他逻辑依赖，实现时需 grep 全部引用后再决定是否移除
- 步骤 3 删除 i18n 字符串后，如果 TypeScript 类型系统会在其他文件引用处报错，则步骤 4-6 的清理必须在同一次编译周期内完成
- 后端 `_build_blocking_warning` 的 `partial_documents` warning 保持不变，它通过 SSE 流以系统消息形式送达前端，与本次删除的 banner 无关
