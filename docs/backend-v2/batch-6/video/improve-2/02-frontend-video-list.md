# VideoList 返回按钮修复

## 问题描述

`VideoList` 组件 (`frontend/src/components/studio/video-list.tsx`) 的 header 区域
只有标题和 SegmentedControl，缺少"返回 Studio"按钮。

Notes 列表 (`renderNotesList`, studio-panel.tsx:414) 和 Diagrams 列表
(`renderDiagramsList`, studio-panel.tsx:599) 都在 `row-between` 容器的左侧放置了
`backToHome` 按钮，VideoList 需要对齐这一交互模式。

---

## 现状对比

### Notes 列表 (studio-panel.tsx:416-419)

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "center" }}>
  <button className="btn btn-ghost btn-sm" type="button" onClick={backToHome}>
    {t(uiStrings.studio.backToStudio)}
  </button>
  <button className="btn btn-sm" type="button" onClick={...}>
    {t(uiStrings.notes.createNote)}
  </button>
</div>
```

### Diagrams 列表 (studio-panel.tsx:601-608)

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "center" }}>
  <button className="btn btn-ghost btn-sm" type="button" onClick={backToHome}>
    {t(uiStrings.studio.backToStudio)}
  </button>
  <span className="muted" style={{ fontSize: 11 }}>
    {`${diagrams.length} ${t(uiStrings.studio.diagrams)}`}
  </span>
</div>
```

### VideoList 当前 (video-list.tsx:32-42)

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "center" }}>
  <strong>{t(uiStrings.video.title)}</strong>
  <SegmentedControl ... />
</div>
```

缺少 `backToHome` 按钮。

---

## 修改方案

### 1. VideoList 组件接收 `onBack` 回调

在 `VideoListProps` 中新增 `onBack` 属性:

```tsx
type VideoListProps = {
  notebookId: string;
  onOpenSummary: (summaryId: string) => void;
  onBack: () => void;
};
```

### 2. Header 区域添加返回按钮

调整 header 的 `row-between` 布局，左侧放返回按钮，右侧保留 SegmentedControl:

```tsx
<div className="row-between" style={{ gap: 8, alignItems: "center" }}>
  <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
    {t(uiStrings.studio.backToStudio)}
  </button>
  <SegmentedControl
    value={videoFilterMode}
    options={[
      { value: "all", label: t(uiStrings.studio.allFilter) },
      { value: "notebook", label: t(uiStrings.studio.thisNotebook) },
    ]}
    onChange={(value) => setVideoFilterMode(value as "all" | "notebook")}
  />
</div>
```

标题 `<strong>{t(uiStrings.video.title)}</strong>` 移到 VideoInputArea 上方或列表区域，
与 Notes/Diagrams 保持一致的布局层级。

### 3. studio-panel.tsx 传入 backToHome

```tsx
{studioView === "videos" ? (
  <VideoList
    notebookId={notebookId}
    onOpenSummary={openVideoDetail}
    onBack={backToHome}
  />
) : null}
```

`backToHome` 已在 `useStudioStore` 中定义 (studio-store.ts:81-88)，
将 `studioView` 重置为 `"home"` 并清除活跃状态。

---

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/components/studio/video-list.tsx` | 新增 `onBack` prop，header 添加返回按钮 |
| `frontend/src/components/studio/studio-panel.tsx` | 传入 `backToHome` 作为 `onBack` |
