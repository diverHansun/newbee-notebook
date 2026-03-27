# Video 前端模块：关键用例

## 1. 用例概览

| 用例 | 触发方式 | 关键前端行为 |
|------|---------|------------|
| 触发视频总结 | 用户在 Video 输入框输入 URL，点击按钮 | 建立 SSE 连接，展示 step indicator，完成后刷新列表 |
| 浏览摘要列表 | 用户进入 Video 视图 | 默认展示全部摘要，支持切换为当前 notebook 筛选 |
| 查看摘要详情 | 用户点击列表条目 | 导航到 video-detail 视图，渲染 Markdown 内容 |
| 关联到 notebook | 用户在详情页点击「关联到笔记本」 | 调用 PATCH API，刷新列表缓存 |
| 取消关联 | 用户在详情页点击「取消关联」 | 调用 PATCH API，刷新列表缓存 |
| 删除摘要 | 用户在详情页点击删除 | ConfirmDialog 确认后调用 DELETE API，返回列表 |
| B站登录 | 用户点击「B站登录」按钮 | 弹出 QR 码弹窗，轮询状态，完成后刷新 auth 状态 |
| /video 斜杠命令 | 用户在聊天输入框输入 /video | 与 /note、/diagram 一致：切换 Agent 模式，执行工具调用 |

## 2. 主流程描述

### 2.1 触发视频总结

**输入**：用户在 Video 输入框中输入 Bilibili URL 或 BV 号，点击「总结」按钮。

**前置条件**：无（未登录不阻断提交）。

**执行步骤**：

1. 校验 URL 格式（前端简单校验，不合法则提示"请输入有效的 Bilibili URL 或 BV 号"）
2. 调用 `POST /api/v1/videos/summarize`，获取 task_id
3. 建立 SSE 连接 `POST /api/v1/videos/summarize/stream`
4. UI 切换到「总结中」状态：输入框禁用，按钮文字变为"总结中..."，展示 step indicator
5. 消费 SSE 事件：
   - 收到 `processing`：更新 `currentStep`，step indicator 高亮当前步骤
   - 收到 `completed`：提取 summary_id，调用 `queryClient.invalidateQueries` 刷新列表
   - 收到 `error`：在 step indicator 下方显示红色错误文字 + 「重试」按钮
6. 收到 `done` 或错误后，UI 恢复到可输入状态

**输出**：摘要出现在列表顶部（按 created_at 倒序）。

**异常处理**：

- URL 格式错误：输入框下方显示错误提示，不调用 API
- 网络错误：`error` 事件中包含 "网络错误"，显示重试按钮
- 后端返回需要登录：`error` 事件 message 包含 "需要登录"，引导用户登录

### 2.2 浏览摘要列表

**输入**：用户进入 Video 视图（从 Home 点击 Video 卡片，或从详情页返回）。

**执行步骤**：

1. 挂载 `useAllVideoSummaries()` hook，显示加载状态（skeleton）
2. 数据返回后，渲染列表：
   - 每个条目：缩略图 + 标题 + UP主 + 时长
   - 按 created_at 倒序排列
3. 条目右上角显示关联状态图标（已关联当前 notebook 则显示书签图标）
4. 用户可点击条目右侧的筛选器切换「全部」/「当前笔记本」

**输出**：展示用户全部视频摘要列表（未关联 notebook 的也显示）。

**异常处理**：

- 加载失败：显示错误状态 + 「重试」按钮
- 列表为空：显示空状态插画 + 「输入第一个视频 URL 开始总结」

### 2.3 查看摘要详情

**输入**：用户点击列表条目。

**执行步骤**：

1. 调用 `openVideoDetail(summaryId)`，更新 studio-store 的 `activeVideoId` 和 `studioView = "video-detail"`
2. 挂载 `useVideoSummary(summaryId)` hook
3. 详情页渲染：
   - 顶部：视频封面图、标题、UP主、时长、平台标签
   - 中部：Markdown 渲染的 summary_content（使用项目现有 Markdown 渲染组件）
   - 底部：操作栏（关联/取消关联、复制、删除）
4. 如果 `notebook_id === 当前 notebookId`，操作栏显示「取消关联」；否则显示「关联到笔记本」

**输出**：video-detail 视图展示完整摘要信息。

### 2.4 关联到 notebook

**输入**：用户在 video-detail 视图点击「关联到笔记本」。

**执行步骤**：

1. 按钮显示加载状态
2. 调用 `PATCH /api/v1/videos/summaries/:id/associate`，body 为 `{ notebook_id }`
3. 成功后：
   - 调用 `queryClient.invalidateQueries` 刷新列表
   - 更新本地派生字段 `is_associated = true`
   - 操作栏按钮变为「取消关联」

**输出**：摘要与当前 notebook 关联成功。

### 2.5 删除摘要

**输入**：用户在 video-detail 视图点击「删除」。

**执行步骤**：

1. 弹出 ConfirmDialog："确定要删除这个视频摘要吗？此操作不可撤销。"
2. 用户确认后：
3. 调用 `DELETE /api/v1/videos/summaries/:id`
4. 成功后：
   - 调用 `queryClient.removeQueries` 清除详情 cache
   - 调用 `queryClient.invalidateQueries` 刷新列表
   - 调用 `backToVideoList()` 回到列表视图

**输出**：摘要删除，列表刷新，用户回到列表视图。

### 2.6 B站登录

**输入**：用户点击「B站登录」按钮。

**执行步骤**：

1. 弹出登录弹窗，显示 QR 码图片
2. 调用 `POST /api/v1/bilibili-auth/qr/create` 获取二维码
3. 轮询 `GET /api/v1/bilibili-auth/qr/status?qr_id=xxx`（每 2 秒一次）
4. 根据状态更新 UI：
   - `waiting`：显示"请使用 B站 App 扫码"
   - `scanned`：显示"已扫码，等待确认"
   - `confirmed`：关闭弹窗，刷新 auth 状态，输入框旁的登录按钮变为用户名
   - `expired`：显示"二维码已过期"，提供「刷新二维码」按钮
5. 轮询超时（5 分钟）：显示"登录超时，请重试"

**输出**：用户 B站账号登录成功，UI 更新登录状态。

### 2.7 /video 斜杠命令

**输入**：用户在聊天输入框输入 `/video` 后从提示面板选中。

**执行步骤**：

1. SlashCommandHint 组件过滤并高亮 `/video` 条目
2. 用户点击或回车选中
3. 输入框内容替换为 `/video `，光标移到命令后
4. ChatInput 组件切换到 AGENT 模式
5. 用户继续输入完整指令（如 `/video 总结这个视频 BVxxxxxx`）
6. 提交后 AgentLoop 调用 VideoSkillProvider 的工具
7. 工具执行完毕，通过 SSE 的 `tool_result` 事件通知前端
8. chat-store 消费事件，调用 `queryClient.invalidateQueries(["video-summaries", "all"])`
9. Video 面板（如果当前可见）自动刷新列表

**输出** `/video` 命令被识别并执行，结果出现在 chat 消息中。

## 3. 责任边界

### 3.1 前端真正负责的部分

- URL 格式的前端校验（正则匹配）
- SSE 连接的建立、解析、中止
- UI 状态切换（输入框可用/禁用、按钮 loading、文字变化）
- TanStack Query 缓存的失效和重新获取
- ConfirmDialog 的展示和用户确认结果处理
- B站 QR 码弹窗的展示和轮询逻辑

### 3.2 外部负责的部分

- Bilibili URL 的合法性（是否真实存在视频）：后端 API 返回
- 字幕是否可获取：后端调用 Bilibili API 决定
- ASR 转录是否成功：后端 ASR pipeline 决定
- LLM 总结质量：后端 LLM 调用决定
- agent 工具调用结果：后端 VideoSkillProvider 决定

## 4. 失败点与决策点

### 4.1 SSE 连接建立失败

- 表现：POST 请求返回网络错误
- 前端行为：显示"连接失败，请检查网络后重试"，输入框恢复可用
- 用户操作：点击「重试」按钮

### 4.2 总结过程中后端报错

- 表现：SSE 收到 `error` 事件
- 前端行为：在 step indicator 下方显示红色错误文字，提供「重试」按钮
- 用户操作：点击「重试」重新发起总结，或忽略继续其他操作

### 4.3 后端返回需要登录

- 表现：SSE 收到 `error` 事件，message 包含"登录"
- 前端行为：显示"此视频需要登录才能获取字幕，请先登录 B站"，登录按钮高亮
- 用户操作：点击登录

### 4.4 删除时网络错误

- 表现：DELETE API 返回错误
- 前端行为：ConfirmDialog 显示错误文字"删除失败，请重试"，不关闭弹窗
- 用户操作：点击「重试」或「取消」

### 4.5 列表加载为空

- 表现：`useAllVideoSummaries()` 返回 `summaries: []`
- 前端行为：显示空状态插画 + "还没有视频摘要"
- 用户操作：输入第一个视频 URL 开始总结
