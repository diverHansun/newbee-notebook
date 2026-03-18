# 图表导出

## 概述

batch-4 实现 React Flow 图表的 PNG 导出。Mermaid 图表的导出预留接口，未来 batch 实现时补充。

导出入口：DiagramDetailView 工具栏的"导出图片"按钮，调用 ReactFlowRenderer 通过 ref 暴露的 `exportToPng()` 方法。

## PNG 导出实现（React Flow）

### 依赖

```
html2canvas    将 DOM 元素渲染为 canvas，再导出为 PNG
```

### 实现

```typescript
// frontend/src/lib/diagram/export.ts

import html2canvas from "html2canvas";

/**
 * 将 React Flow 容器导出为 PNG 文件并触发下载。
 *
 * @param containerEl - React Flow 渲染容器的 DOM 元素（ReactFlowRenderer 的根 div）
 * @param filename - 下载文件名（不含扩展名）
 */
export async function exportReactFlowToPng(
  containerEl: HTMLElement,
  filename: string,
): Promise<void> {
  const canvas = await html2canvas(containerEl, {
    backgroundColor: "#ffffff",
    scale: 2,           // 2x 分辨率，保证导出清晰度
    useCORS: true,      // 跨域图片资源处理
    logging: false,
    // 仅捕获 React Flow 渲染层，排除控件遮罩
    ignoreElements: (el) =>
      el.classList.contains("react-flow__controls") ||
      el.classList.contains("react-flow__background"),
  });

  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${sanitizeFilename(filename)}.png`;
    link.click();
    URL.revokeObjectURL(url);
  }, "image/png");
}

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\?%*:|"<>]/g, "-").trim() || "diagram";
}
```

### 导出流程

```
用户点击"导出图片"按钮
  → DiagramDetailView 调用 rendererRef.current.exportToPng()
  → ReactFlowRenderer 调用 exportReactFlowToPng(containerRef.current, diagram.title)
  → html2canvas 捕获 React Flow 容器（2x 分辨率，白色背景）
  → 触发浏览器文件下载，文件名为 "{diagram.title}.png"
```

### 导出注意事项

- 导出前调用 React Flow 的 `fitView()` 确保所有节点都在视口内
- 导出过程中按钮显示 loading 状态，防止重复点击
- 导出失败时 toast 提示错误，不中断用户操作

### fitView 前置调用

```typescript
// 在 ReactFlowRenderer 中，exportToPng 前先 fitView
useImperativeHandle(ref, () => ({
  exportToPng: async () => {
    fitView({ padding: 0.1, duration: 0 });
    // 等待 fitView 完成（下一帧）
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await exportReactFlowToPng(containerRef.current!, diagram.title);
  },
}));
```

## Mermaid 导出预留（未来 batch）

Mermaid 的 `render()` API 直接返回 SVG 字符串，导出实现如下（预留，暂不实现）：

```typescript
// 预留接口骨架
export async function exportMermaidToSvg(
  syntax: string,
  filename: string,
): Promise<void> {
  // const { svg } = await mermaid.render(`export-${Date.now()}`, syntax);
  // const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  // downloadBlob(blob, `${sanitizeFilename(filename)}.svg`);
  throw new Error("Mermaid 导出将在 mermaid 渲染器实现时补充");
}
```

## 导出文件命名规则

- 使用图表标题作为文件名
- 移除操作系统不允许的特殊字符（`/\?%*:|"<>`），替换为 `-`
- 标题为空时使用 `diagram` 作为默认名称
- 文件扩展名 `.png`（React Flow）或 `.svg`（Mermaid，预留）
