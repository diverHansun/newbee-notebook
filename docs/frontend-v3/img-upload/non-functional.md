# img_upload 前端模块 non-functional.md

本文档列出本前端模块在功能正确之外必须满足的工程约束。基于 [goals-duty.md](goals-duty.md)、[architecture.md](architecture.md)、[dfd-interface.md](dfd-interface.md)。

---

## 一、Quality Priorities（质量优先级）

按重要性从高到低：

1. **附件视觉响应零延迟**优先于带宽节省。选图 / 拖入 / 粘贴瞬间必须立即出现缩略图（ObjectURL），不依赖后端 thumbnail 端点。
2. **不阻断聊天主路径**优先于附件功能丰富度。任何附件错误、上传失败、ObjectURL 泄漏都不应让 textarea 输入或 SSE 流变慢、崩溃。
3. **发送门禁的强契约**优先于"边发边传"的体验便利。不能进入"按了发送但图还没传完"这一中间态。
4. **无障碍**不打折。键盘可达、ARIA 完整、focus 不丢失。
5. **简单实现**优先于横向扩展能力。一个 hook + 几个 dumb component 完全够用，不引入任何上传库。

---

## 二、Operational Constraints（运行约束）

### 1. 客户端限额（与 backend non-functional 强一致）

- 单图 ≤ 10 MB（前端预校验拒绝）。
- 单消息 ≤ 10 张（前端预校验拒绝）。
- MIME 仅 `image/png` / `image/jpeg` / `image/webp`（前端按 file.type 检查；后端做 magic byte 真校验）。

### 2. 性能与时延

- 选图 → ObjectURL 缩略图渲染 < 16ms（同步操作）。
- 上传请求按文件粒度 POST；前端最多 4 个并发，剩余排队。
- 历史回看的缩略图 `<img loading="lazy">`，避免初次加载所有图。

### 3. 网络

- 上传不做客户端 retry 自动循环；用户主动 retry 才再发。理由：避免重复消耗带宽与对象存储写。
- 每次上传请求 timeout 沿用项目 `apiFetch` 的现有 timeout。
- 不设客户端 RPS 限流（4 并发已是上限）。

### 4. 资源

- ObjectURL 在 remove / reset / unmount 三处释放；CI 测试需要锁定无泄漏。
- 截屏抓帧后立即 `stream.getTracks().forEach(t => t.stop())`，避免持续占用屏幕分享指示器。
- canvas 中间产物用完即丢，不缓存。

### 5. 浏览器兼容

- 目标浏览器：Chrome / Edge / Firefox / Safari 桌面端最新两个大版本。
- getDisplayMedia 在移动 Safari 不可用 → 截屏按钮隐藏，主路径不影响。
- ClipboardEvent.files 在 Safari 桌面端可用；不可用时 paste 入口静默失败（不弹错）。
- `<dialog>` 在 Safari 16+ 支持；更老版本退化为简单覆盖层（不阻塞放大查看）。

### 6. 文件命名 / 安全

- 不在前端把 file.name 显示成攻击入口（不 dangerously set innerHTML）；卡片 alt 文案使用 i18n 字串而不是用户文件名。
- 上传请求不包含原文件名以外的元信息；后端日志已禁打印用户可控字段。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 1. 失败语义

- 单图上传失败 → 卡片 failed 视觉 + retry/remove 按钮；不影响其他图与文本输入。
- 客户端预校验失败 → toast 提示原因；不进入集合。
- 截屏 user 取消 → getDisplayMedia rejection；不弹错；按钮恢复可点。
- 剪贴板拿到非图 → 静默忽略，仍允许默认 paste 文本。
- 发送时若所有 image_id 已 ready，则提交一定带这些 id；不允许"图 ready 但 id 丢失"。

### 2. 不可接受的失败

- 已 ready 的附件 image_id 在发送 payload 中遗漏。
- ObjectURL 泄漏导致长会话后内存激增。
- 发送按钮在所有图 ready 后仍 disabled（门禁死锁）。
- 发送成功后附件未清空。
- 截屏 stream 未停止，浏览器持续显示屏幕分享指示器。
- 历史回看缩略图加载失败导致整条消息卡片崩溃。
- 把 image_id 拼到无鉴权的 URL 让浏览器 fetch 时失败。

### 3. 可观测性

- 关键错误（上传 5xx、截屏 fail）打印 `console.error` 含原因码，不打印 file 内容。
- 当前阶段不引入埋点；如需统计附件用户行为，由统一埋点模块后续接入。
- 不为附件状态变化加详细 trace（reducer 自身已可调试）。

### 4. 允许的退化

- 浏览器不支持 getDisplayMedia → 截屏按钮不渲染。
- 浏览器不支持 `<dialog>.showModal` → lightbox 退化为简单覆盖层。
- 后端 thumbnail 端点暂不可用 → 历史卡片显示 placeholder 占位。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

### 1. 不引入任何上传库

不接入 react-dropzone / uppy / filepond。理由：本模块的状态机与 backend 两阶段契约对齐成本，比引入库更低。

### 2. 不实现"批次 207 partial 解析"

每文件一个 POST，错误隔离自然到位。理由：与 backend 单接口能力相比，前端的简单实现成本更低。

### 3. 不实现客户端图片压缩

backend 已在 `load_for_llm` 做长边缩放。理由：避免双重失真。

### 4. 不实现自动 retry

失败靠用户主动重试。理由：避免对带宽与对象存储写的重复消耗。

### 5. 不实现拖拽排序 / 多选删除等高级动作

附件量级 ≤ 10 张，删除单图按钮足够。

### 6. 不实现独立"我的图片"页面

附件不出附件栏；历史回看通过历史消息列表本身。

### 7. 不为本期接入完整埋点

切附件、上传成功、上传失败的次数统计延后；让模块尽快上线，可观测性后置。

### 8. 不实现移动端键盘快捷键 / 移动端拖拽体验

本期目标桌面端 main 面板；移动端只确保 file picker 可用。

### 9. 不引入 react-image-lightbox 等查看器

native `<dialog>` + `<img>` 起步；如果未来需要 zoom / 多图横滑再演进。

### 10. 不实现"附件转可粘贴 markdown"或"附件下载"

聊天回看时不允许把后端原图当附件下载下来——这是后端的安全边界（鉴权 + session 归属），前端遵循即可。
