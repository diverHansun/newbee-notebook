# 03 当前 GPU 模式缺口分析

本文记录当前仓库 GPU 本地模式与官方本地基线之间的主要差距。

---

## 一、已经对齐的部分

### 1. 运行时版本已跟进 3.x

当前 GPU 镜像已经升级到适配 MinerU 3.x 的运行时路线，基础方向是正确的。

### 2. 本地 3.0 新参数已接入

当前本地 converter 已经支持：

- `parse_method`
- `formula_enable`
- `table_enable`

这说明本地 form 参数层面对 3.0 并不是空白状态。

### 3. 健康检查接口已修正

当前 GPU 栈已经把探针切到 `/health`，这一点与官方 3.x 本地服务一致。

---

## 二、核心缺口

### 缺口 1：本地 converter 只支持 PDF

当前 `MinerULocalConverter` 的核心行为仍然是：

- 只接收 `.pdf`
- 使用 PDF 页数统计
- 依赖 PDF 分页切批
- 上传 MIME 固定为 `application/pdf`

这意味着即使官方本地已经支持：

- 图片
- `DOCX`
- `PPTX`
- `XLSX`

当前项目里的 GPU 本地模式也不会真正走这些类型。

这会直接带来一个认知落差：

- 文档层面容易让人误以为 GPU 本地模式“已经升级到 3.0”
- 但真实用户体验仍然接近“本地只支持 PDF”

### 缺口 2：本地逻辑把“PDF 特性”当成“本地通用特性”

当前 converter 的设计默认所有本地请求都适用：

- `start_page_id`
- `end_page_id`
- 先数页再切批

这套逻辑仅对 PDF 自然成立。

对于以下类型，这些参数要么没有意义，要么应避免携带：

- 图片
- `DOCX`
- `PPTX`
- `XLSX`

所以当前不是简单加几个扩展名就能完事，而是要把本地 converter 内部拆成至少两条路径：

- PDF 路径
- 非 PDF 路径

### 缺口 3：GPU compose 的 backend 不一致

当前 GPU override 中：

- Worker 环境显式设置 `MINERU_BACKEND=hybrid-auto-engine`
- API 服务没有同样的显式设置
- 配置文件默认仍然是 `pipeline`

结果就是：

- 同样是 local 模式，不同运行入口可能落到不同 backend
- 问题排查时会出现“Worker 侧是 GPU，本机 API 或其他路径却不是”的混乱

### 缺口 4：GPU 服务启动时序未完全收口

当前 `mineru-api` 已经有 healthcheck，但：

- `api`
- `celery-worker`

并没有显式基于它的健康状态建立依赖。

在以下时机会放大这个问题：

- 第一次构建后启动
- 首次下载模型
- 切换 GPU 模式后立刻上传文档

容易表现成：

- 容器整体已经启动
- 但第一批任务仍然因为本地 MinerU 尚未 ready 而失败

### 缺口 5：GPU 文档还没有完全按本地能力边界重写

当前文档中 GPU 模式虽然已经说明：

- 是 NVIDIA 单机本地增强模式
- 会启动本地 `mineru-api`

但还缺少几项关键澄清：

- 本地支持集与云端支持集不同
- 本轮不会接 `mineru-router`
- 本轮继续沿用 Celery，不改用官方 `/tasks`
- `DOC / PPT / HTML` 不属于 GPU 本地模式本轮目标

### 缺口 6：测试覆盖不够

当前本地测试主要集中在：

- PDF form 参数
- 配置传递

缺少这些高价值断言：

- `.docx / .pptx / .xlsx / 图片` 是否会路由到本地 converter
- 非 PDF 本地请求是否不再携带分页字段
- GPU compose 是否对 API 和 Worker 使用一致的本地 backend
- GPU compose 是否对 `mineru-api` 建立明确依赖

---

## 三、次要缺口

### 1. 配置面板只支持 cloud/local 二选一

当前前端配置面板与后端配置接口只允许切换：

- `cloud`
- `local`

还不能在运行时直接调整：

- `backend`
- `parse_method`
- `formula_enable`
- `table_enable`

这会影响高级调试效率，但不阻塞本轮第一层适配。

### 2. GPU 文档里的官方部署说明需要重新贴近 3.x

当前文档对 GPU 模式的说明还是以“项目当前做法”为主，下一轮应补上更清晰的“官方本地部署基线”和“本项目裁剪后的采用方式”。

---

## 四、问题优先级

### P0：本轮必须解决

- 本地支持集补齐到 `PDF / image / DOCX / PPTX / XLSX`
- 本地 converter 区分 PDF / 非 PDF 请求逻辑
- GPU compose backend 一致性
- GPU 启动依赖与健康状态收口
- 测试与文档同步补齐

### P1：建议解决

- 补一套 GPU 本地 smoke 验证脚本或 compose 断言
- 补更多真实样本类型的单测覆盖

### P2：本轮明确不做

- `mineru-router`
- `/tasks`
- 多机多卡
- 配置面板高级参数开放

---

## 结论

当前 GPU 模式最主要的问题，不是“版本没升上去”，而是“本地能力面与官方 3.x 基线没有真正对齐”。

因此 improve-3-gpu 的核心价值，在于把 GPU 本地模式从“3.x 运行时 + PDF 主路径”推进到“3.x 运行时 + 官方本地支持集 + 单机单卡稳定可用”。
