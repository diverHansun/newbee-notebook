# 图片生成模块（前端） - 组件设计

## Component Overview

```
MessageItem (assistant role)
  ├── ThinkingIndicator / ToolStepsIndicator（流式中）
  ├── MarkdownViewer（文字内容）
  ├── ImageCardList                 ← 新增
  │     └── ImageCard (×N)         ← 新增
  │           ├── <img> (src → /api/generated-images/{id}/data)
  │           ├── 下载按钮（右上角）
  │           └── prompt 文字（底部，单行省略）
  ├── DocumentReferencesCard（引用来源）
  └── ConfirmationCard（确认请求）
```

`ImageCardList` 和 `ImageCard` 是新增组件，`MessageItem` 仅在渲染逻辑中追加一个条件分支，不改变现有组件的内部结构。

## ImageCard 组件

### 职责

渲染单张生成图片，提供查看、放大和下载交互。

### Props

```typescript
interface ImageCardProps {
  imageId: string
  prompt: string
  width: number | null   // 图片实际像素宽度（用于骨架屏比例）
  height: number | null  // 图片实际像素高度
  provider: string       // 不在卡片中显示，仅用于调试日志
}
```

### 渲染结构

```
<div class="image-card">                    ← 玻璃质感容器，极小 padding
  <a class="image-card__download">          ← 右上角下载图标，position: absolute
    <DownloadIcon />                         ← 默认 opacity: 0，hover 时 opacity: 1
  </a>
  <img
    src="/api/generated-images/{imageId}/data"
    alt={prompt}
    class="image-card__image"               ← width: 100%, display: block
    onLoad={handleLoad}                     ← 加载成功：隐藏骨架屏
    onError={handleError}                   ← 加载失败：显示失败占位
  />
  <p class="image-card__prompt">{prompt}</p> ← 单行，text-overflow: ellipsis
</div>
```

### 状态机

```
initial → loading → loaded
                → error
```

- **loading**：显示骨架屏（pulse 动画），尺寸由 `width`/`height` 比例决定。若比例为空，使用 1:1 默认比例。
- **loaded**：`<img>` 正常显示，骨架屏隐藏。
- **error**：灰色占位块 + "图片加载失败" 文字 + "重试" 按钮。点击重试重新设置 `src`。

### 交互行为

- **点击图片**：打开 `ImageLightbox`，传入 `imageId`。
- **点击下载按钮**：浏览器原生下载，`href` 为 `/api/generated-images/{imageId}/data?download=1`，无需 JS fetch。

## ImageCardList 组件

### 职责

渲染一个 assistant 消息下的所有图片卡片。

### Props

```typescript
interface ImageCardListProps {
  images: ChatImage[]
}
```

### 渲染结构

```
<div class="image-card-list">
  {images.map(image => (
    <ImageCard key={image.imageId} {...image} />
  ))}
</div>
```

容器使用 `flex wrap`，卡片间 `gap: 12px`。当只有一张图片时，卡片占满消息宽度。多张图片时并排排列。

## ImageLightbox 组件

### 职责

全屏查看图片，点击图片放大时打开，ESC 或点击背景关闭。

### Props

```typescript
interface ImageLightboxProps {
  imageId: string | null    // null 时关闭
  prompt: string
  onClose: () => void
}
```

### 渲染结构

```
<div class="image-lightbox__overlay">      ← fixed, inset: 0, z-index: 9999, bg: rgba(0,0,0,0.85)
  <div class="image-lightbox__close">×</div> ← 右上角关闭按钮
  <img
    src="/api/generated-images/{imageId}/data"
    class="image-lightbox__image"           ← max-width: 90vw, max-height: 90vh, object-fit: contain
  />
</div>
```

### 交互行为

- 点击 overlay 背景 → 关闭
- 按 ESC → 关闭
- 关闭时设置 `imageId` 为 null

打开/关闭使用 CSS `opacity` 过渡动画（0.2s）。

## 渲染时机

在 `MessageItem` 中，assistant 消息的渲染顺序为：

1. 流式中间态（ThinkingIndicator / ToolStepsIndicator）
2. Markdown 正文（MarkdownViewer）
3. **ImageCardList**（新增，条件：`message.images && message.images.length > 0`）
4. DocumentReferencesCard（引用来源）
5. ConfirmationCard（确认请求）

流式进行中，`image_generated` 事件到达时，`images` 数组追加到当前 assistant 消息，`ImageCardList` 立即渲染（图片处于 loading 状态）。`done` 事件后，已渲染的图片保持不动。

历史消息加载时，消息 API 返回的 `images` 字段已包含图片元数据，`ImageCardList` 直接渲染（图片从后端缓存加载）。

## Styles & Theming

### 新增样式文件

`frontend/src/styles/image-card.css` — 所有图片卡片和 lightbox 相关样式。

### 风格要点

- **卡片容器**：`border-radius: 12px`，与现有消息圆角一致。玻璃质感：`background: hsl(var(--card) / 0.6); backdrop-filter: blur(8px)`。`overflow: hidden`。padding 极小（`4px`），图片贴合卡片边缘。
- **图片**：`width: 100%; display: block; object-fit: contain`。自然宽高比渲染。
- **下载按钮**：`position: absolute; top: 8px; right: 8px`。默认 `opacity: 0`，卡片 `:hover` 时 `opacity: 1`，`transition: opacity 0.2s`。
- **Prompt 文字**：`font-size: 0.75rem; color: hsl(var(--muted-foreground)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 4px 8px`。
- **骨架屏**：使用现有项目的 pulse 动画，宽高比由 `width/height` 决定。默认 1:1。
- **加载失败**：灰色占位块 + 居中 "⚠ 加载失败" + "重试" 链接。
- **Lightbox**：`position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.85)`。图片居中。关闭按钮右上角。打开/关闭使用 opacity 过渡（0.2s）。

### 主题兼容

所有颜色使用 CSS 变量（`--card`, `--muted-foreground` 等），自动适配 Dark/Light 主题。

暗色模式下：卡片背景稍深、下载按钮 hover 时更明显。
亮色模式下：卡片背景稍浅、prompt 文字更深。

### Globals 导入

在 `frontend/src/styles/globals.css` 中追加：

```css
@import "./image-card.css";
```