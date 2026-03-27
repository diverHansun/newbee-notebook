# Video 前端模块：前端数据模型

## 1. 核心概念

前端数据模型描述在 UI 层流转的数据结构，包括从后端 API 接收的类型定义、组件间传递的 props 类型、本地状态类型，以及 TanStack Query 的缓存 key 策略。这些类型是前端与后端契约的 UI 侧表达。

## 2. TypeScript 类型定义

### 2.1 VideoSummary 类型

来自后端 VideoSummary 实体的前端映射。完整字段以 `lib/api/types.ts` 中后端模型为准，此处列出 UI 层直接使用的关键字段：

```typescript
export type VideoSummary = {
  summary_id: string;
  notebook_id: string | null;
  document_ids: string[];
  platform: "bilibili" | string;

  bvid: string;
  title: string;
  cover_url: string | null;
  uploader_name: string;
  duration_seconds: number;

  summary_content: string;
  summary_version: string;

  subtitle_path: string | null;

  created_at: string;
  updated_at: string;
};
```

`is_associated` 是前端派生字段，不来自后端。当 `notebook_id === 当前 notebookId` 时为 true。

### 2.2 VideoSummaryListItem 类型

列表页使用的精简类型，不包含 `summary_content`：

```typescript
export type VideoSummaryListItem = {
  summary_id: string;
  notebook_id: string | null;
  platform: string;
  bvid: string;
  title: string;
  cover_url: string | null;
  uploader_name: string;
  duration_seconds: number;
  created_at: string;
  updated_at: string;
};
```

### 2.3 VideoListResponse 类型

```typescript
export type VideoListResponse = {
  summaries: VideoSummaryListItem[];
  total: number;
};
```

### 2.4 SSE 进度事件类型

```typescript
export type SseEventProcessing = {
  event: "processing";
  bvid: string;
  title: string;
  step: string;
};

export type SseEventCompleted = {
  event: "completed";
  summary_id: string;
  bvid: string;
  title: string;
  status: "success" | "no_subtitle";
  duration_sec: number;
};

export type SseEventError = {
  event: "error";
  bvid: string;
  title: string;
  message: string;
};

export type SseEventDone = {
  event: "done";
  total: number;
  success: number;
  skipped: number;
  no_subtitle: number;
  errors: number;
};

export type VideoSseEvent = SseEventProcessing | SseEventCompleted | SseEventError | SseEventDone;
```

### 2.5 BilibiliAuthState 类型

```typescript
export type BilibiliAuthState =
  | { status: "logged_out" }
  | { status: "logging_in" }
  | { status: "logged_in"; username: string; face?: string };
```

### 2.6 VideoFilterMode 类型

```typescript
export type VideoFilterMode = "all" | "current-notebook";
```

## 3. Query Keys

遵循 `lib/hooks/use-diagrams.ts` 的 Query Key 工厂模式：

```typescript
export const ALL_VIDEO_SUMMARIES_QUERY_KEY = ["video-summaries", "all"] as const;

export const VIDEO_SUMMARIES_QUERY_KEY = (notebookId: string) =>
  ["video-summaries", notebookId] as const;

export const VIDEO_SUMMARY_QUERY_KEY = (summaryId: string) =>
  ["video-summary", summaryId] as const;
```

### 3.1 Query Key 失效策略

| 操作 | 失效的 Query Keys |
|------|-----------------|
| 创建新摘要（SSE done） | ALL_VIDEO_SUMMARIES_QUERY_KEY |
| 删除摘要 | ALL_VIDEO_SUMMARIES_QUERY_KEY + VIDEO_SUMMARY_QUERY_KEY(summaryId) |
| 关联到 notebook | VIDEO_SUMMARIES_QUERY_KEY(notebookId) |
| 取消关联 | VIDEO_SUMMARIES_QUERY_KEY(notebookId) |
| agent 工具调用后 | 同创建，由 cache invalidation 机制触发 |

## 4. Store State（studio-store.ts 扩展部分）

```typescript
type VideoStudioState = {
  activeVideoId: string | null;
  openVideoDetail: (videoId: string) => void;
  backToVideoList: () => void;
};
```

其他 Video 相关状态（筛选模式、SSE 进度、输入框值）作为组件局部状态管理，不进入全局 store。

## 5. Props 类型

```typescript
type VideoListViewProps = {
  notebookId: string;
};

type VideoDetailViewProps = {
  notebookId: string;
};

type VideoInputAreaProps = {
  notebookId: string;
  authState: BilibiliAuthState;
  onLoginClick: () => void;
};

type VideoListItemProps = {
  summary: VideoSummaryListItem;
  isAssociated: boolean;
  onClick: (summaryId: string) => void;
};
```

## 6. 组件间数据流动

```
后端 API 响应
    │
    v
API Client (lib/api/videos.ts)
    │
    v
TanStack Query Cache
    │
    ├── useAllVideoSummaries()  ──> VideoListView 渲染列表
    ├── useVideoSummaries(nbId) ──> VideoListView（筛选模式）
    └── useVideoSummary(id)    ──> VideoDetailView 渲染详情
                                      │
                                      v
                              VideoActionBar（关联/取消关联 mutation）
                                      │
                                      v
                              API Client（PATCH /summaries/:id/associate）
                                      │
                                      v
                              queryClient.invalidateQueries()
```

## 7. 类型定义的约束

前端类型定义必须与后端 API 响应保持一致。类型定义以 `lib/api/types.ts` 为准，任何新增类型应同步更新该文件。

前端不定义后端业务逻辑相关的类型（如 VideoService 的内部结构、BilibiliClient 的方法签名），这些属于后端模块的范畴。
