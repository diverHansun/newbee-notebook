# Studio 卡片颜色与特效设计

## 背景

当前 Studio 首页展示三个功能入口卡片（Notes & Marks、Diagrams、Video），使用统一的 `.card.card-interactive` 样式，缺乏视觉区分度。本改进为每种卡片引入独立配色，并添加悬停光效。

## 设计目标

1. **颜色区分**：三种卡片使用不同淡色背景，一眼可辨认功能类型
2. **悬停光效**：悬停时产生柔和的光晕效果，提升交互体验
3. **保持简洁**：不引入渐变，保持界面干净

## 配色方案

### 颜色定义

| 卡片类型 | 颜色名称 | HEX 值 | HSL 值 | 用途 |
|----------|----------|--------|--------|------|
| Notes & Marks | 淡蓝 | `#e3f2fd` | `hsl(207, 90%, 94%)` | 卡片背景 |
| Diagrams | 淡绿 | `#e8f5e9` | `hsl(112, 47%, 90%)` | 卡片背景 |
| Video | 淡粉 | `#fce4ec` | `hsl(340, 82%, 90%)` | 卡片背景 |

### 设计原则

- 所有颜色均为高亮度（Lightness > 85%），确保内容可读性
- 颜色饱和度适中，不刺眼但有区分度
- 使用 HSL 格式，便于通过 CSS 变量统一管理

## CSS 变量设计

### 方案 A：在现有 CSS 变量体系中新增变量

在 `frontend/src/styles/cards.css` 或相关样式文件中定义：

```css
/* Studio Card Colors */
:root {
  /* Notes & Marks - Soft Blue */
  --studio-notes-bg: hsl(207, 90%, 94%);
  --studio-notes-glow: hsl(207, 90%, 85%);
  
  /* Diagrams - Soft Green */
  --studio-diagrams-bg: hsl(112, 47%, 90%);
  --studio-diagrams-glow: hsl(112, 47%, 80%);
  
  /* Video - Soft Pink */
  --studio-video-bg: hsl(340, 82%, 90%);
  --studio-video-glow: hsl(340, 82%, 80%);
}
```

### 方案 B：直接在组件中使用内联样式

在 `studio-panel.tsx` 的 `renderHome()` 函数中直接使用颜色值。

**推荐方案 A**，原因：
1. 颜色值集中管理，便于后续调整
2. 支持主题切换时单独覆盖
3. 语义化命名，提高代码可维护性

## 特效实现

### 悬停光效

使用 `box-shadow` 实现柔和光晕：

```css
/* 基础卡片样式 */
.studio-card {
  border: 1px solid hsl(var(--border));
  border-radius: calc(var(--radius) + 2px);
  background: hsl(var(--card));
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  transition: 
    box-shadow 200ms ease-out,
    transform 200ms ease-out,
    background-color 200ms ease-out;
}

/* Notes & Marks 卡片悬停 */
.studio-card--notes:hover {
  background-color: var(--studio-notes-bg);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1),
    0 0 20px 2px var(--studio-notes-glow);
  transform: translateY(-2px);
}

/* Diagrams 卡片悬停 */
.studio-card--diagrams:hover {
  background-color: var(--studio-diagrams-bg);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1),
    0 0 20px 2px var(--studio-diagrams-glow);
  transform: translateY(-2px);
}

/* Video 卡片悬停 */
.studio-card--video:hover {
  background-color: var(--studio-video-bg);
  box-shadow: 
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1),
    0 0 20px 2px var(--studio-video-glow);
  transform: translateY(-2px);
}
```

### 光效特点

| 特性 | 说明 |
|------|------|
| 扩散方式 | 水平垂直均匀扩散 |
| 模糊程度 | 20px 模糊半径 |
| 扩展距离 | 2px 扩展 |
| 动画时长 | 200ms ease-out |
| 悬停位移 | translateY(-2px) 上浮效果 |

## 组件改动

### StudioPanel renderHome()

修改 `studio-panel.tsx` 中的 `renderHome()` 函数：

```tsx
const renderHome = () => (
  <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
    <div 
      className="studio-card studio-card--notes" 
      style={{ padding: 16, minHeight: 100 }} 
      onClick={() => navigateTo("notes")}
    >
      <div className="stack-sm">
        <strong>{t(uiStrings.studio.notesAndMarks)}</strong>
        <span className="muted" style={{ fontSize: 12 }}>
          {t(uiStrings.studio.notesAndMarksDescription)}
        </span>
      </div>
    </div>
    
    <div 
      className="studio-card studio-card--diagrams" 
      style={{ padding: 16, minHeight: 100 }} 
      onClick={() => navigateTo("diagrams")}
    >
      <div className="stack-sm">
        <strong>{t(uiStrings.studio.diagrams)}</strong>
        <span className="muted" style={{ fontSize: 12 }}>
          {t(uiStrings.studio.diagramsDescription)}
        </span>
      </div>
    </div>
    
    <div 
      className="studio-card studio-card--video" 
      style={{ padding: 16, minHeight: 100 }} 
      onClick={() => navigateTo("videos")}
    >
      <div className="stack-sm">
        <strong>{t(uiStrings.studio.video)}</strong>
        <span className="muted" style={{ fontSize: 12 }}>
          {t(uiStrings.studio.videoDescription)}
        </span>
      </div>
    </div>
  </div>
);
```

## 文件改动清单

| 文件 | 改动内容 |
|------|----------|
| `frontend/src/styles/cards.css` | 新增 CSS 变量和卡片特效样式 |
| `frontend/src/components/studio/studio-panel.tsx` | 更新 renderHome() 卡片 className |

## 深色主题适配

在深色主题下，卡片颜色需要相应调整：

```css
@media (prefers-color-scheme: dark) {
  :root {
    --studio-notes-bg: hsl(207, 40%, 25%);
    --studio-notes-glow: hsl(207, 40%, 35%);
    
    --studio-diagrams-bg: hsl(112, 35%, 25%);
    --studio-diagrams-glow: hsl(112, 35%, 35%);
    
    --studio-video-bg: hsl(340, 45%, 25%);
    --studio-video-glow: hsl(340, 45%, 35%);
  }
}
```

## 测试要点

1. **视觉检查**
   - 三种卡片颜色正确区分
   - 悬停时光晕效果可见但不过于刺眼
   - 卡片上浮效果平滑

2. **交互测试**
   - 点击卡片正常跳转
   - 快速悬停不会产生视觉抖动
   - 连续悬停切换效果正常

3. **响应式测试**
   - 不同屏幕尺寸下卡片布局正常
   - 触摸设备上无悬停效果（保持基础样式）

4. **主题测试**
   - 浅色主题下颜色正确
   - 深色主题下颜色正确且可读
