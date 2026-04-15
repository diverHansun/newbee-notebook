# 设计目标与职责边界

## 1. 设计目标

### 1.1 单输入框，多平台自动识别

用户只看到一个输入框，可以直接粘贴：

- Bilibili URL
- BV 号
- YouTube URL
- YouTube 11 位视频 ID

前端负责识别平台并展示对应状态，不要求用户手动切换平台。

### 1.2 保持 summarize 操作心智统一

无论是 Bilibili 还是 YouTube，用户都使用同一个按钮开始 summarize；差异只体现在状态条、校验提示和步骤文案上。

### 1.3 避免 YouTube 场景被 Bilibili UI 干扰

当前 Video 面板顶部总是展示 Bilibili 登录状态，这在 YouTube 场景中会造成噪音。改造后必须按平台条件渲染。

### 1.4 让进度反馈更可理解

YouTube 需要额外表现：

- 已拿到视频信息
- 字幕来源
- 是否进入 ASR

但不应该为了支持 YouTube 再做一套完全不同的进度组件。

## 2. 职责

- 平台检测与输入校验
- 发起 summarize 请求并透传 `lang`
- 解析 SSE 事件并更新 UI
- 渲染动态平台状态条
- 列表作用域筛选与平台筛选
- 在列表项中显示平台标识

## 3. 非职责

- 不负责 YouTube / Bilibili 实际视频解析
- 不在前端做字幕内容拼接
- 不在 Studio Video 面板中提供 YouTube discovery
- 不新增第二套 summarize 页签或表单
