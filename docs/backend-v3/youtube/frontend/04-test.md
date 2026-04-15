# 测试策略

## 1. 前端测试重点

### 1.1 平台识别

- Bilibili URL / BV
- YouTube URL / 短链 / Shorts / ID
- unknown / empty

### 1.2 输入区渲染

- 空输入显示中性提示
- Bilibili 显示登录状态
- YouTube 显示无需登录提示

### 1.3 SSE 事件

- `info` 事件不会导致前端报错
- `subtitle.source` 能被展示/记录
- `done` 会触发 query invalidate

### 1.4 双维筛选

- `all / this notebook`
- `all / bilibili / youtube`

## 2. 自动化测试范围

- `videos.ts`
- `video-input-area.tsx`
- `video-list.tsx`
- `video-list-item.tsx`

## 3. 手动验证

1. 输入 YouTube URL，状态条不再展示 Bilibili 登录 CTA
2. 输入 Bilibili URL，登录区正常显示
3. YouTube summarize 过程中可看到 info / subtitle / summarize / done
4. 列表可按平台过滤
