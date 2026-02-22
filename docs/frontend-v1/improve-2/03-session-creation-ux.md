# P4: 新建会话 UX 优化

---

## 1. 当前问题

### 1.1 概念澄清：session_id 与 title 的区别

在当前代码中，两者是完全独立的字段（见 `lib/api/types.ts`）：

| 字段 | 类型 | 生成方式 | 用途 |
|------|------|----------|------|
| `session_id` | `string`（UUID） | 后端自动生成（`generate_uuid()`） | 系统标识符，前端用于 select/option 的唯一 key |
| `title` | `string \| null` | 用户输入或自动生成，可为空 | 人类可读标签，显示在下拉选择框中 |

当 `title` 为空时，UI 退化显示 `session_id` 前 8 位（`chat-panel.tsx` 第 78 行）。

### 1.2 后端接口行为

`POST /notebooks/{notebookId}/sessions` 接口：

- `title` 字段完全可选，不传或传 `null` 均合法
- `session_id` 由后端 UUID 自动生成，前端不参与

因此，技术层面从来不"需要"用户输入标题，接口本身不做此约束。

### 1.3 当前 UI 的问题

`components/chat/chat-panel.tsx` 第 93-111 行，当前布局：

```
[ 输入框: 新会话标题（可选）  ]  [ + 新建会话 ]
```

**问题一：视觉暗示与实际行为不符**

输入框与按钮并排，视觉上形成"先填写，再提交"的表单模式。用户无法直观判断输入框是否必填。虽然 placeholder 标注了"（可选）"，但仍造成认知摩擦。

**问题二：操作路径过长**

用户想要快速开始对话，必须先决定是否输入标题，再点击按钮。即使标题是可选的，多余的 UI 元素增加了决策成本。

**问题三：无标题时的退化显示不友好**

跳过输入直接创建时，会话名称显示为 UUID 前 8 位（如 `550e8400`），对用户不具备可读性。

**问题四：标题命名缺乏语义**

即便用户手动输入，也缺少参考。对于快速创建的会话，最有意义的自动命名应基于第一条消息内容（目前已有但仅在 `ensureSession` 路径触发，不在手动创建路径触发）。

### 1.4 相关代码位置

- 会话栏 UI：`components/chat/chat-panel.tsx` 第 93-114 行
- 状态与调用：`lib/hooks/useChatSession.ts` 第 99-108 行（`createSessionMutation`）
- 自动命名逻辑（现有）：`useChatSession.ts` 第约 162 行（`ensureSession`，使用消息前 30 字符）
- 显示短 ID 的退化逻辑：`chat-panel.tsx` 第 78 行、第 177 行

---

## 2. 解决方案（方案 A）

### 核心原则

点击"新建会话"按钮，系统立即创建会话并生成有意义的默认标题，不阻塞用户任何操作。
创建后，用户可以通过会话列表的重命名功能修改标题（本次不实现，作为后续迭代）。

### 2.1 自动命名规则

按优先级：

1. 如果当前 notebook 已有会话，使用 `会话 ${n+1}`（n 为当前会话数量）
2. 如果尚无会话，使用 `会话 1`
3. 名称重复时，在末尾追加数字后缀直到不重复

实现示意：

```typescript
function generateSessionTitle(sessions: Session[]): string {
  const n = sessions.length + 1;
  const candidate = `会话 ${n}`;
  // 检查重复
  const existing = new Set(sessions.map((s) => s.title));
  if (!existing.has(candidate)) return candidate;
  // 有重复则追加后缀
  let i = n + 1;
  while (existing.has(`会话 ${i}`)) i++;
  return `会话 ${i}`;
}
```

此函数为纯函数，放在 `chat-panel.tsx` 或 `useChatSession.ts` 均可，推荐放在 `chat-panel.tsx` 就近使用。

### 2.2 UI 改造

**移除**会话栏中的 title 输入框（`chat-panel.tsx` 第 93-100 行）。
**移除**组件 state `sessionTitle`（第 44 行）。
**修改**"新建会话"按钮点击逻辑：

```typescript
// 修改前（第 101-111 行）
<input
  className="input"
  style={{ width: 150 }}
  value={sessionTitle}
  placeholder="新会话标题（可选）"
  onChange={(event) => setSessionTitle(event.target.value)}
/>
<button
  className="btn btn-sm"
  type="button"
  onClick={() => {
    onCreateSession(sessionTitle.trim() || undefined);
    setSessionTitle("");
  }}
>
  + 新建会话
</button>

// 修改后
<button
  className="btn btn-sm"
  type="button"
  onClick={() => {
    onCreateSession(generateSessionTitle(sessions));
  }}
>
  + 新建会话
</button>
```

### 2.3 Props 接口保持不变

`ChatPanelProps` 中 `onCreateSession: (title?: string) => void` 签名不变。
`useChatSession.ts` 中的 `createNewSession(title?: string)` 不变。

自动生成的标题作为参数传入，与手动输入标题走完全相同的代码路径，不引入新逻辑。

### 2.4 退化显示修复

由于每次创建时都会传入自动生成的标题，`title` 字段将始终有值，`session_id.slice(0, 8)` 的退化分支不再触发（对于新创建的会话）。
历史遗留的无标题会话仍由 `session.title || session.session_id.slice(0, 8)` 正常处理，无需修改此逻辑。

---

## 3. 架构影响与修改点

### 修改文件

**`frontend/src/components/chat/chat-panel.tsx`**

| 变更类型 | 内容 |
|----------|------|
| 删除 | `const [sessionTitle, setSessionTitle] = useState("")`（第 44 行） |
| 删除 | title `input` 元素（第 94-100 行） |
| 修改 | 新建按钮 `onClick`：调用 `onCreateSession(generateSessionTitle(sessions))` |
| 新增 | 文件顶部（组件外）纯函数 `generateSessionTitle(sessions: Session[]): string` |

### 非修改文件

- `lib/hooks/useChatSession.ts`：`onCreateSession` 接口不变，内部 mutation 不变
- `lib/api/sessions.ts`：API 调用不变
- `lib/api/types.ts`：类型不变
- 后端：接口不变（`title` 字段始终为可选）

### 净变化

删除约 10 行（输入框 + state），新增约 10 行（generateSessionTitle 纯函数），总量持平。
组件复杂度下降（移除一个受控 state）。

### 行为变化对比

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 点击新建会话（无输入） | 创建会话，title 为 null，显示 UUID 前 8 位 | 创建会话，title 为"会话 N"，直接可读 |
| 点击新建会话（有输入） | 创建会话，title 为输入内容 | 不再有输入框，统一自动命名 |
| 操作路径 | 需决策是否输入 -> 点击 | 直接点击 |
| 标题可修改性 | 创建前可输入 | 创建后可重命名（后续迭代实现） |

### 后续迭代建议（本次不实现）

1. **会话重命名**：双击会话下拉选项或右键菜单，支持 inline 编辑 title
2. **基于消息内容自动重命名**：在第一条消息发送成功后，若 title 为系统生成的默认值，自动更新为消息前 20 字
3. **会话序号防重**：如果后端支持返回会话列表的命名统计，可以将 `generateSessionTitle` 逻辑移至后端，避免前端并发创建时序号冲突
