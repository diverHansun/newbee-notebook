# 组件结构与状态设计

## 1. 总体结构

```text
VideoList
  ├── ScopeFilter (All / This Notebook)
  ├── PlatformFilter (All / Bilibili / YouTube)
  ├── VideoInputArea
  │     ├── PlatformStatusBar
  │     ├── Input
  │     ├── MetadataPreview
  │     ├── ProgressSteps
  │     └── ErrorHint
  └── VideoListItem
        └── PlatformBadge
```

## 2. 输入区状态模型

`VideoInputArea` 建议引入以下状态：

```typescript
type DetectedPlatform = "bilibili" | "youtube" | "unknown" | null;
```

说明：

- `null`：空输入
- `unknown`：有输入但无法识别
- 不再把未知输入直接当作 Bilibili

## 3. 平台状态条

### 3.1 `null`

显示中性说明：

- 支持 Bilibili / YouTube 链接或 ID

### 3.2 `bilibili`

显示：

- 登录状态 chip
- 登录 / 退出 CTA

### 3.3 `youtube`

显示：

- YouTube chip
- “No login required”
- “Summary language follows current UI language”

### 3.4 `unknown`

显示轻量校验提示，不阻塞继续输入。

## 4. 进度组件

步骤组件改为基于事件映射，而不是固定 `StepType` 常量硬编码。

建议事件到 UI 的映射：

- `start`：进入处理流程
- `info`：更新 metadata preview，可选地补一个“已获取视频信息”步骤
- `subtitle`：显示字幕来源
- `asr`：显示 ASR 进行中
- `summarize`：生成总结
- `done`：完成
- `error`：终止当前 active step

## 5. 列表筛选

列表筛选拆成两维：

- `videoFilterMode`: `all | notebook`
- `videoPlatformFilter`: `all | bilibili | youtube`

平台筛选是本地过滤，不影响后端接口。

## 6. 列表项

`VideoListItem` 至少新增：

- 平台 badge

可选第二阶段：

- `transcript_source` badge
