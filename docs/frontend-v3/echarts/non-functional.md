# non-functional.md — echarts

## 撰写说明

echarts 模块横跨前后端、涉及外部 JS 库（echarts core ~200-400KB 按需注册体积）、且在会话流式渲染路径上——属于"明显需要 non-functional 显性化"的模块。本文件按 docs-plan 强制结构展开。

---

## 一、Quality Priorities（质量优先级）

按重要性从高到低：

1. **正确性优先于性能**——`validate_echarts_option` 宁可宽松到漏过个别拼写错误（让 ECharts 运行时承担），也不能误判合法的 option 为非法。误拒会破坏"LLM 输出能跑就行"的可演进性。

2. **首屏稳定性优先于 bundle 体积**——首次接入直接静态 import echarts core；可接受首屏多 200-400KB。Non-Duty #7 已明确不做 dynamic import 拆 chunk，bundle 监控放到 §四 暂缓项。

3. **流式渲染鲁棒性优先于"首字节即出图"**——LLM 流式输出 echarts 围栏期间，JSON 不完整是常态。loading 占位 + 完整后渲染是必须；不允许为了"边写边渲染"而吞掉异常导致崩溃。

4. **三端一致性优先于实现便利**——后端白名单 / 前端注册列表 / prompt 示例三处镜像必须严格相等；以工程约束（CI 测试）兜底，而不是依赖人为记忆。

5. **现有模块零侵入优先于"统一抽象"**——内联管线增量层不重写既有 markdown / mermaid / reactflow 路径，且默认关闭，只在本轮 `/diagram` assistant 回复启用。Non-Duty #1 / #9 已锁定。

---

## 二、Operational Constraints（运行约束）

### 2.1 性能与时延

- **后端 validator**：单次调用应在毫秒级完成（JSON parse + 4 步浅校验）。该路径在 LLM tool 调用链上，单次超过 50ms 视为异常。
- **前端 EChartsRenderer init**：单实例 init + setOption 应在 100ms 内完成（典型单 series 图表，无大数据集）。多图同屏渲染（一条消息包含 N 个图）应避免主线程长时间阻塞——必要时分帧 mount。
- **内联占位符识别**：markdown-pipeline 编译阶段对 echarts 围栏的提取必须是 O(n) 文本扫描；不引入回溯式正则导致大段流式文本性能退化。

### 2.2 资源占用

- **前端 bundle**：echarts core + 按需注册 ~200-400KB（gzip 后 ~80-150KB）。Studio 和 reader 路由共享同一 bundle；不为 echarts 单独拆 chunk（接入期）。
- **echarts 实例内存**：每个 mounted Renderer 持有一个 echarts 实例。`InlineChartPlaceholderLayer` 必须在消息卸载时 dispose 实例，避免会话切换后内存泄露。

### 2.3 外部依赖稳定性

- **echarts 库版本锁定**：在 `package.json` 显式 `^X.Y.0` 锁版本；不允许构建时拉到 breaking change 的次新版。CI 应做 `pnpm install --frozen-lockfile`。
- **ECharts 不可用场景**：若 echarts 模块加载失败（极少见，CDN / chunk 加载错误），`EChartsRenderer` 退化为 `<pre>` 显示原 JSON + 错误提示，不影响其他消息渲染。

### 2.4 并发与调用频率

- echarts 内联渲染走前端浏览器，本身并发即"用户单会话 N 个图"——典型 ≤5 个/消息。不引入显式队列或限流。
- 后端 `create_diagram` 调用与现有 mindmap / flowchart 共享 service 路径，不引入新的并发瓶颈。

### 2.5 成本预算

- 本模块不引入新的外部付费服务（不调云端图表渲染 API）；echarts 是开源本地库，无运行成本。
- LLM token 成本上涨主要来自 echarts agent system prompt 的扩展（按子类型示例可能新增数百-上千 tokens）——可接受，注入只在 `/diagram` 触发时发生（goals-duty §一.2）。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 3.1 失败处理策略

| 失败类型 | 期望行为 | 不可接受 |
|---|---|---|
| LLM 输出非法 option（持久化路径） | validator 抛错 → tool 回结构化错误 → LLM 自修正重试一次 | 静默落库非法 content |
| LLM 输出非法 option（内联路径） | `EChartsRenderer` `JSON.parse` 失败 → loading 或最终回落 `<pre>` | React tree 崩溃 / 整个消息白屏 |
| echarts 运行时拒绝渲染 | 捕获异常 → 卡片显示简短错误 + 原 JSON | 未捕获异常冒泡 |
| "保存到 Studio" REST 失败 | 卡片内错误信息 + 保留卡片状态 + 允许重试 | 声称成功但未落库 |
| 多次点击"保存到 Studio" | 按钮 inflight 期间 disabled | 重复创建 N 个相同 diagram |
| 流式过程中 JSON 不完整 | 显示 loading；下次 chunk 到达重试 parse | 反复抛错刷屏控制台 |
| 三处白名单不一致（构建期） | CI 单测失败 PR 阻塞 | 进入生产后才被发现 |

### 3.2 可观测性

- **后端**：复用现有 `_raise_validation_error` 诊断格式（category / detail / location / suggestion 四段式），让 LLM 和人类都能读懂错误。无需新增 metrics / trace（首版）。
- **前端**：echarts 实例运行时异常应写一次 `console.error`（带 `diagram_id` 或 `placeholderId`），便于开发者复现；不向用户展示堆栈。内联保存的成功/失败反馈使用卡片内状态，不引入全局 toast 依赖。
- **白名单一致性**：CI 测试输出明确指出"白名单三处中哪一处缺哪个子类型"。

### 3.3 降级行为允许范围

- 允许：`EChartsRenderer` 在 echarts 不可用时回落 `<pre>`；`SaveToStudioAction` 在网络失败时展示卡片内错误。
- 不允许：默默吞掉错误后让用户以为图已经渲染或保存。
- 不允许：用 try / catch 把 validator 的非法判定吞掉。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 4.1 暂缓：bundle splitting

- 当前阶段不拆 echarts chunk，加速首次接入。
- **跟踪指标**：构建产物体积报告。当 echarts 直接相关的 JS 在主 bundle 占比 > 15% 或绝对体积 > 500KB（gzip 前）时，单独立项做 `dynamic import('echarts')` 改造。

### 4.2 暂缓：严格 schema 校验

- 已在 architecture §四.1 锁定。轻量浅校验上线后，根据线上"LLM 输出但 ECharts 渲染失败"的实际比例决定是否升级。
- **判定阈值**：若线上同一会话出现"画图但用户报告图错"的反馈率 > 5%，则补充常用子类型的"必要字段存在性"检查（分层校验，不上严格 schema）。

### 4.3 暂缓：内联图表与持久化 diagram 的双向引用

- 当前"保存到 Studio"是单向升级动作，会话文本不绑定新 diagram_id；未来若用户提出"在消息里嵌入对图表的引用 `[[diagram:xxx]]`"需求，独立立项。

### 4.4 暂缓：echarts 高级特性 prompt 引导

- dataset / multi-series / visualMap / dataZoom / 联动事件等不在首版 prompt 引导范围。LLM 能输出就允许（validator 不拦），但不主动教。

### 4.5 暂缓：移动端 / 小屏适配

- 当前 Studio 与 reader 主要面向桌面端；echarts 容器宽度自适应即可。移动端的"图表手势缩放 / 长按导出"等不在本模块。

### 4.6 暂缓：图表"快照导出"批量化

- 单图导出 PNG 已实现；批量导出（如导出整个 notebook 所有 diagrams 到 zip）属于 export 模块，不在本模块。

### 4.7 暂缓：echarts 主题深度定制

- 当前仅做"深浅色"两套 option overlay；不引入用户可配置的主题色板编辑器。

### 4.8 暂缓：内联渲染的 SSR 支持

- `EChartsRenderer` 是 `"use client"`，不参与 SSR。会话内联渲染本身就发生在客户端流式期间，SSR 无意义。后续若 reader 需要在 SSR 渲染含图的 markdown，重新评估。

### 4.9 暂缓：前端 CSS 深度定稿

- 首版文档只锁定交互与信息架构：内联卡片使用保存 icon button、Studio 详情沿用现有卡片风格、列表只新增类型 chip。
- 具体 CSS 细节（间距、阴影、图表卡片视觉 polish）不随本批后端实施推进；前端实现前单独确认。

---

## 五、自检结论

- 优先级列表 5 条，按"正确性 > 稳定性 > 三端一致 > 实现便利"清晰排序，不是把"高质量"全部并列。
- 运行约束覆盖性能 / 资源 / 外部依赖 / 并发 / 成本五类，每类都有可验证方向。
- 失败处理表格列了 7 种典型场景，每种都明确"期望"与"不可接受"。
- 暂缓项 8 条，每条都有原因 + 触发重新评估的条件，避免后续维护者误以为"遗漏就是缺陷"。
