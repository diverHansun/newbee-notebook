# Markdown 查看器 -- 架构设计

前置文档：[goals-duty.md](./goals-duty.md)

---

## 1. 架构概览

Markdown 查看器由三个层次组成，各层职责清晰，数据单向流动：

```
Markdown 字符串（输入）
    |
    v
[渲染管线层] -- unified/remark/rehype 处理链
    |
    v
React 组件树（中间产物）
    |
    v
[样式层] -- CSS 变量 + Markdown 内容排版
    |
    v
DOM 输出（最终呈现）
```

- **渲染管线层**：负责将 Markdown 字符串解析为 AST，经过一系列转换插件处理后，输出为 React 组件树。这是模块的核心，所有 Markdown 特性支持（GFM、数学公式、代码高亮）都在这一层通过插件完成。
- **组件封装层**：对外提供 `MarkdownViewer` React 组件，接收 Markdown 字符串作为 props，内部调用渲染管线并处理加载状态。
- **样式层**：提供 Markdown 内容区的排版样式，通过 CSS 类名和 CSS 变量实现主题响应。

---

## 2. 设计模式与理由

### 2.1 管线模式（Pipeline）

渲染管线采用 unified 生态的管线模式：多个插件按固定顺序串联执行，每个插件只关注一种转换任务。

选择理由：
- MinerU 产出的 Markdown 包含多种需要特殊处理的元素（GFM 表格、LaTeX 公式等），每种处理逻辑独立封装为插件，避免单一渲染函数膨胀
- unified 生态提供了成熟的 remark（Markdown AST）和 rehype（HTML AST）插件体系，大部分能力可直接复用社区插件
- 管线的顺序和组合在初始化时确定，运行时不会动态变更，性能开销可控

放弃的替代方案：
- **react-markdown 直接使用**：react-markdown 底层也基于 unified，但其 API 隐藏了管线细节，在需要深度定制时直接使用 unified 管线更可控
- **手写 Markdown 解析器**：没有必要，unified 生态已经覆盖了所有需求

### 2.2 无需自定义插件

当前所有需求（GFM、数学公式、代码高亮、CJK 排版、标题锚点）均有可用的社区插件，不需要编写自定义插件。

关于图片路径：后端在文档处理保存阶段（`save_markdown()` 函数）已将 MinerU 输出的相对路径 `images/{hash}.jpg` 统一转换为 API 绝对路径 `/api/v1/documents/{id}/assets/images/{hash}.jpg` 并写入 `content.md`。前端拿到的 Markdown 文本中图片路径已经是可直接访问的 URL，浏览器渲染 `<img>` 后经 Next.js rewrites 代理到后端资源端点，无需前端做任何路径转换。

---

## 3. 模块结构与文件布局

```
components/reader/
  MarkdownViewer.tsx          -- 对外组件，接收 content
  markdown-pipeline.ts        -- 管线构建与配置
  styles/
    markdown-content.css      -- Markdown 内容区排版样式
```

各文件职责：

- **MarkdownViewer.tsx**：模块的外部接口。接收 `content`（Markdown 字符串）和可选的 `className` 作为 props。内部调用 `markdown-pipeline.ts` 创建管线实例，将处理结果渲染为 React 组件。处理 content 为空或加载中的边界状态。
- **markdown-pipeline.ts**：构建和配置 unified 管线。按顺序组装所有 remark 和 rehype 插件，导出管线构建函数。这是管线插件组合顺序的唯一定义位置。
- **markdown-content.css**：Markdown 内容区的排版样式。使用 CSS 变量实现主题响应。该文件只定义渲染内容区域内的样式，不影响外部布局。

### 3.1 外部接口与内部实现的边界

外部模块只与 `MarkdownViewer.tsx` 交互，不直接使用管线构建函数。管线配置属于内部实现细节，可以在不影响外部接口的前提下调整。

---

## 4. 架构约束与权衡

### 4.1 管线实例的创建时机

管线不依赖外部参数（移除 rehypeImageResolver 后无需注入 documentId），可以在模块加载时创建单例并复用。管线实例是无状态的，对同一 Markdown 输入总是产生相同的输出。

### 4.2 highlight.js 的语言包加载

highlight.js 完整语言包体积较大。有两种策略：

- 方案 A：打包时包含所有常用语言（约 40 种），牺牲包体积换取零配置
- 方案 B：只包含基础语言（约 10 种），其余按需动态加载

当前选择方案 A。理由：MinerU 转换的文档以文本为主，代码块占比较小，语言种类有限。40 种常用语言的额外体积（约 200KB gzip）在可接受范围内。

放弃方案 B 的理由：动态加载引入异步复杂度，且代码块高亮是渲染管线同步流程的一部分，异步加载会打断管线执行。

### 4.3 content-visibility 替代虚拟滚动

长文档（2000+ 行 Markdown）的性能优化采用 `content-visibility: auto` CSS 属性，而非虚拟滚动。

权衡：
- `content-visibility` 实现成本极低（只需在内容容器上添加 CSS 属性），浏览器自动跳过不可见区域的布局和绘制
- 虚拟滚动需要预先计算每个渲染块的高度，而 Markdown 内容的块高度不固定（包含图片、表格、代码块），实现复杂度高
- 代价是首次渲染仍需解析完整 Markdown 生成完整 DOM，内存占用不会减少。如后续内存成为瓶颈，再考虑虚拟滚动或分页加载

### 4.4 渲染管线的插件顺序

管线插件的执行顺序有严格要求，变更顺序可能导致渲染异常：

```
remark 阶段（操作 Markdown AST）:
  1. remarkParse        -- 基础解析，必须在最前
  2. remarkGfm          -- GFM 扩展，在基础解析之后
  3. remarkMath          -- 数学公式识别，需在 GFM 之后避免语法冲突
  4. remarkCjkFriendly   -- CJK 断行优化，在其他语法解析完成后处理

remark → rehype 转换:
  5. remarkRehype        -- AST 格式转换

rehype 阶段（操作 HTML AST）:
  6. rehypeSlug          -- 标题锚点生成
  7. rehypeHighlight     -- 代码语法高亮
  8. rehypeKatex         -- 数学公式渲染为 HTML

输出:
  9. rehypeReact         -- 将 HAST 转换为 React 组件树
```

约束说明：
- remarkParse 必须在第一位
- remarkMath 和 remarkGfm 的顺序会影响 `$` 符号的解析优先级，当前顺序确保 GFM 的删除线（`~~`）不会干扰数学公式的 `$` 定界符
- rehypeKatex 需要在 rehypeHighlight 之后，避免数学公式被误识别为代码

注：图片路径无需在管线中处理。后端在文档保存时已将所有图片路径转换为 API 绝对路径，管线直接解析即可。
