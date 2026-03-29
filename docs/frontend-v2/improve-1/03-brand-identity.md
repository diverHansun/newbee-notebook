# 品牌标识设计

## 背景

Newbee Notebook 项目需要一个统一的品牌标识。当前设置面板的触发按钮使用文字 "NB"（Newbee 缩写），需要替换为设计好的小蜜蜂图标 `newbee-icon.png`。

## 资源管理

### 图片放置位置

为保持 Next.js 项目的最佳实践，静态资源放置于 `frontend/public/assets/images/` 目录：

```
frontend/
  public/
    assets/
      images/
        newbee-icon.png    # 小蜜蜂品牌图标
```

### 路径引用

在 Next.js 中，`public` 目录下的文件可通过根路径直接访问：
- 图片 URL：`/assets/images/newbee-icon.png`

## 图标规格

根据设计稿要求：
- 格式：PNG（支持透明背景）
- 用途：设置面板按钮的品牌标识

## 前端改动

### ControlPanelIcon 组件

修改 `control-panel-icon.tsx`，将文字 "NB" 替换为图片：

```tsx
// frontend/src/components/layout/control-panel-icon.tsx

export function ControlPanelIcon() {
  // ... existing code ...

  return (
    <div ref={rootRef} className={`control-panel-root${isDev ? " is-dev" : ""}`}>
      <button
        type="button"
        className="control-panel-button"
        aria-label={open ? t(uiStrings.controlPanel.closeSettings) : t(uiStrings.controlPanel.openSettings)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="control-panel-button-mark" aria-hidden>
          <Image 
            src="/assets/images/newbee-icon.png" 
            alt="Newbee Notebook" 
            width={24} 
            height={24}
            priority
          />
        </span>
      </button>
      {/* ... */}
    </div>
  );
}
```

### CSS 样式调整

对应的 CSS 可能需要微调以适应图片尺寸：

```css
/* frontend/src/styles/control-panel.css */

.control-panel-button-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.control-panel-button-mark img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
```

## 实施步骤

1. 将 `newbee-icon.png` 复制到 `frontend/public/assets/images/` 目录
2. 修改 `control-panel-icon.tsx` 中的按钮内容
3. 更新 CSS 样式确保图标正确显示
4. 验证按钮在不同主题下的显示效果

## 主题兼容性

品牌图标需要支持浅色和深色主题。如果图标为深色蜜蜂图案：
- 浅色主题：直接显示
- 深色主题：可能需要 CSS filter 调整对比度

如果需要主题适配，可在 CSS 中使用变量：

```css
.theme-light .control-panel-button-mark img {
  filter: none;
}

.theme-dark .control-panel-button-mark img {
  filter: brightness(0) invert(1);  /* 或其他适合的滤镜 */
}
```

## 维护建议

- 保留原始设计源文件（如 Sketch、Figma、AI 文件）于项目文档目录
- 如需调整图标尺寸，只需修改 Image 组件的 width/height 属性
- 未来其他品牌标识图片也统一放置于 `frontend/public/assets/images/`
