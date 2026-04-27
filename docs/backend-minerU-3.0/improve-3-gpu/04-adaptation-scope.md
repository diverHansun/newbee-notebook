# 04 本轮适配范围与设计取舍

本文明确本轮 GPU 本地模式适配要做什么、不做什么，以及推荐的实现取舍。

---

## 一、本轮实施范围

### 1. 本地支持集补齐

本轮目标把 GPU 本地模式补齐到官方本地支持集：

- `PDF`
- 图片
- `DOCX`
- `PPTX`
- `XLSX`

其中“图片”在本项目里建议沿用当前仓库已经支持的常见扩展名集合，例如：

- `png`
- `jpg`
- `jpeg`
- `bmp`
- `webp`
- `gif`
- `jp2`
- `tif`
- `tiff`

### 2. 继续使用本地 `mineru-api`

本轮保持：

- Worker 调用本地 `mineru-api`
- 外层继续使用 Celery 管排队、重试和任务生命周期

不引入：

- `mineru-router`
- 官方 `/tasks` 任务编排

### 3. 单机单卡 compose 收口

本轮要让 GPU compose 更明确服务于：

- 单机
- 单卡
- 单用户

重点收口：

- `MINERU_BACKEND`
- `mineru-api` readiness
- `api` / `worker` 与本地 MinerU 的依赖关系

### 4. 测试与文档同步补齐

本轮必须同步更新：

- 单元测试
- compose smoke 测试
- `quickstart.md`

---

## 二、推荐设计

### 设计 1：本地 converter 拆成 PDF 与非 PDF 两条子路径

推荐在同一个 `MinerULocalConverter` 里明确拆出两类逻辑：

#### PDF 路径

保留现有优势能力：

- 统计页数
- 大 PDF 分批
- 携带 `start_page_id / end_page_id`
- 合并结果

#### 非 PDF 路径

新增单请求逻辑：

- 不做页数统计
- 不传分页参数
- 按真实文件类型上传
- 直接解析返回 zip

这样可以最大化复用当前实现，同时避免为了支持 Office / 图片而破坏 PDF 稳定路径。

### 设计 2：GPU 默认 backend 统一到 `hybrid-auto-engine`

本轮建议在 GPU 覆盖栈下统一约定：

- `MINERU_MODE=local`
- `MINERU_BACKEND=hybrid-auto-engine`

适用对象应包括：

- `celery-worker`
- `api`

这样做的好处是：

- 配置行为一致
- 问题更容易复现
- 与“GPU 本地增强模式”的用户预期一致

同时保留通过环境变量显式改回 `pipeline` 的能力，便于调试或资源不足时降级。

### 设计 3：保留 Celery，避免与官方 `/tasks` 重叠

本轮不建议为了“官方已经有 `/tasks`”就切换本项目的编排方式。

原因很直接：

- 我们已经有 Celery
- 已有后端状态流转
- 已有失败补偿与索引任务衔接

如果这轮强行把 Worker 改成依赖 `POST /tasks`，会把问题从“本地支持集补齐”扩展成“外层任务系统重构”。

### 设计 4：文档必须明确本地能力边界

本轮文档中应明确写清楚：

- GPU 本地模式只补齐 `PDF / image / DOCX / PPTX / XLSX`
- `DOC / PPT / HTML` 不在本轮本地支持范围
- 这些类型仍应走云端模式或 fallback

这条非常重要，因为如果文档不写清楚，用户会自然认为“既然 cloud 支持，local 也应该支持”。

---

## 三、本轮不做的设计项

### 1. 不做 `mineru-router`

虽然官方已经支持 `mineru-router`，但本轮先不接。

原因：

- 单机单卡场景没有强需求
- 会引入新的路由与 worker 管理复杂度
- 与当前 Celery 编排边界重叠

### 2. 不做 `/tasks`

虽然官方本地 API 已提供异步 `/tasks`，但本项目已有 Celery 外层队列。

本轮若接 `/tasks`，等于出现两层任务系统：

- 外层 Celery
- 内层 MinerU task manager

这会让状态与失败处理更加复杂。

### 3. 不做多机多卡

本轮只服务于单机单卡：

- 不做本地 worker 自动扩展
- 不做跨 GPU 调度
- 不做统一入口路由层

### 4. 不开放高级配置面板

是否在前端设置面板中增加：

- backend
- parse_method
- formula/table 开关

本轮不作为主目标。

原因：

- 对用户价值不如“本地支持集补齐”直接
- 会额外带来前后端配置接口设计
- 更适合作为后续增强项

---

## 四、实施后的目标状态

如果本轮按上述设计完成，目标状态应是：

1. GPU 模式下，`PDF / image / DOCX / PPTX / XLSX` 都会优先走本地 MinerU。
2. PDF 仍保留分页分批能力，非 PDF 不再误走 PDF 参数。
3. `api` 与 `worker` 对本地 MinerU 的 backend 认知一致。
4. 启动 GPU 栈后，`mineru-api` 的 readiness 对转换链路更可预期。
5. 文档会清楚说明“本地不等于云端全能力”。

---

## 五、最终取舍结论

本轮采取的策略可以概括为：

> 只做单机单卡 GPU 本地模式必须完成的第一层能力对齐，把官方本地支持集补齐到仓库中，同时继续沿用 Celery 队列，不提前引入 `mineru-router` 或官方 `/tasks`。
