# Video 模块 YouTube 扩展 -- 前端设计文档

## 模块定位

本目录描述 Studio Video 面板在 backend-v3 阶段接入 YouTube summarize 后的前端交互设计。目标不是新增第二套 UI，而是在现有 Video 面板上扩成“单输入框、多平台识别、统一进度体验”。

## 当前结论

1. 输入区继续只有一个框，用户可输入 Bilibili / YouTube 的链接或 ID。
2. 平台自动识别，前端不要求用户显式切换。
3. 顶部状态条按平台动态变化：
   - `bilibili`：展示登录状态与登录/退出 CTA
   - `youtube`：展示无需登录和语言提示
   - `empty/unknown`：展示中性提示
4. 列表筛选采用“双维度”：
   - 作用域：`All / This Notebook`
   - 平台：`All / Bilibili / YouTube`
5. 进度区改为数据驱动，兼容 `start/info/subtitle/asr/summarize/done/error`。

## 与现有代码的真实差距

- `video-input-area.tsx` 目前只校验 Bilibili。
- `videos.ts` 遇到未知 SSE 事件会直接报错。
- `video-list.tsx` 只有作用域筛选，没有平台筛选。
- `video-list-item.tsx` 没有平台 badge。
- `strings.ts` 当前文案几乎全部是 Bilibili 专属。

## 文档清单

| 序号 | 文档 | 说明 |
|------|------|------|
| 01 | [01-goals-duty.md](01-goals-duty.md) | 设计目标与职责边界 |
| 02 | [02-architecture.md](02-architecture.md) | 组件结构与状态设计 |
| 03 | [03-dfd-interface.md](03-dfd-interface.md) | 数据流、接口与事件约定 |
| 04 | [04-test.md](04-test.md) | 测试策略 |

## 关联文档

- 后端设计文档：[`../backend/README.md`](../backend/README.md)
- 实施计划：[`../implement/README.md`](../implement/README.md)
