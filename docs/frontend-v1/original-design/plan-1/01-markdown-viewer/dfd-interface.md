# Markdown 查看器 -- 数据流与接口

前置文档：[goals-duty.md](./goals-duty.md)、[architecture.md](./architecture.md)

---

## 1. 上下文与范围

Markdown 查看器在系统中的位置：

```
[状态管理与 API 层]
    |
    | 提供 Markdown 文本
    v
[Markdown 查看器]  <--- [主题系统] 提供 CSS 变量
    |
    | 渲染后的 DOM
    v
[文本选择交互模块]  -- 在渲染区域内检测用户选中行为
```

本模块与以下外部模块存在数据交互：

- **状态管理与 API 层**（上游）：提供待渲染的 Markdown 文本
- **主题系统**（上游）：通过 CSS 变量提供当前主题的颜色值
- **后端资源端点**（外部）：浏览器根据渲染后的图片 URL 直接向后端请求图片资源（路径已由后端在保存时嵌入 Markdown）
- **文本选择交互模块**（下游）：在本模块渲染的 DOM 区域内工作，但不通过本模块的接口调用

本文档只描述进出 Markdown 查看器模块的数据流，不涉及上下游模块的内部实现。

---

## 2. 数据流描述

### 2.1 主数据流：Markdown 渲染

```
输入：Markdown 字符串
  |
  | MarkdownViewer 组件接收 props
  v
remark 阶段：Markdown 字符串 -> Markdown AST
  |  解析 GFM 扩展语法
  |  识别 LaTeX 数学公式标记
  |  处理 CJK 断行
  v
remarkRehype：Markdown AST -> HTML AST
  v
rehype 阶段：HTML AST 转换
  |  标题锚点 ID 生成
  |  代码块语法高亮
  |  数学公式渲染为 HTML 结构
  v
rehypeReact：HTML AST -> React 组件树
  |
  v
输出：React 组件树渲染到 DOM
```

关键分支处理：

- 若 `content` 为空字符串或 undefined，组件渲染空状态占位，不启动管线

### 2.2 图片加载流程（浏览器行为，非本模块逻辑）

后端在文档处理保存阶段（`store.py` 的 `save_markdown()` 函数）已完成图片路径转换：

```
MinerU 输出的相对路径:  images/{hash}.jpg
                           |
                           | save_markdown() 中 _rewrite_markdown_image_links()
                           v
content.md 中的实际路径:  /api/v1/documents/{id}/assets/images/{hash}.jpg
```

前端渲染后，浏览器自动加载图片：

```
DOM 中的 img 元素 src="/api/v1/documents/{id}/assets/images/{hash}.jpg"
  |
  | 浏览器发起 HTTP 请求
  v
Next.js rewrites 将 /api/v1/* 代理到后端 localhost:8000
  |
  v
后端 GET /documents/{id}/assets/{path} 返回图片文件
  （从 data/documents/{id}/assets/images/ 读取）
```

说明：图片加载是浏览器的默认行为，本模块不参与路径转换。图片加载失败的处理（如显示占位图）可在组件封装层通过 img 元素的 onError 回调实现，但不属于核心数据流。

### 2.3 主题响应流程

```
应用主题切换（light -> dark 或反向）
  |
  | CSS 变量值更新（由主题系统完成）
  v
Markdown 内容区样式通过 CSS 变量引用自动更新
  |
  v
代码高亮配色通过 CSS 类名切换（light/dark 两套 highlight.js 主题）
```

说明：主题切换不触发 Markdown 重新解析。管线输出的 React 组件树不变，只有样式层响应变化。

---

## 3. 接口定义

### 3.1 MarkdownViewer 组件接口（对外）

| 属性 | 输入含义 | 同步/异步 |
|------|----------|-----------|
| content | 待渲染的 Markdown 字符串 | 同步（props） |
| className | 可选，外部传入的容器样式类名 | 同步（props） |

组件无回调输出。渲染结果直接反映在 DOM 上。

说明：不再需要 `documentId` prop。后端已在保存时将所有图片路径转换为包含 document_id 的 API 绝对路径，前端管线无需感知当前文档 ID。

### 3.2 管线构建函数接口（内部）

| 函数 | 输入含义 | 输出含义 | 同步/异步 |
|------|----------|----------|-----------|
| renderMarkdown | content（Markdown 字符串） | React 组件树 | 同步 |

管线实例可在模块加载时创建为单例，后续每次调用 `renderMarkdown` 直接复用。该接口为模块内部接口，不对外暴露。

---

## 4. 数据所有权与责任

| 数据 | 创建者 | 消费者 | 本模块的责任 |
|------|--------|--------|-------------|
| Markdown 字符串 | 状态管理与 API 层（从后端获取） | Markdown 查看器 | 只读消费，不修改原始字符串 |
| 渲染后的 DOM | Markdown 查看器 | 文本选择交互模块、用户浏览器 | 创建并维护，随 content 变化更新 |
| 图片资源 | 后端文件系统 | 浏览器（通过 img 元素） | 不直接管理，路径已由后端嵌入 Markdown |
| CSS 变量（主题色） | 主题系统 | Markdown 查看器的样式层 | 只读引用，不修改 |
| 标题锚点 ID | Markdown 查看器（rehypeSlug 生成） | 外部目录导航组件（如有） | 创建，但不主动通知外部 |
