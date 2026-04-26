# 05 建议实施顺序、测试重点与验收口径

本文给出 improve-3-gpu 的建议实施顺序，用于后续正式编写实施计划前对齐节奏。

---

## 一、建议实施顺序

### 第 1 步：先改本地 converter 路由能力

优先修改：

- `newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py`
- `newbee_notebook/infrastructure/document_processing/processor.py`

目标：

- 本地支持集补齐到 `PDF / image / DOCX / PPTX / XLSX`
- 区分 PDF 与非 PDF 的请求路径

原因：

- 这是本轮主价值所在
- 后续 compose、文档、测试都要围绕这一点展开

### 第 2 步：再修 compose 与默认配置一致性

重点关注：

- `docker-compose.gpu.yml`
- `newbee_notebook/configs/document_processing.yaml`

目标：

- 让 API 与 Worker 对本地 backend 的认知一致
- 让 GPU 栈对 `mineru-api` 的依赖更明确

### 第 3 步：补单元测试

优先补齐：

- 本地 converter 单测
- processor 路由单测
- compose smoke 断言

### 第 4 步：更新文档

最后再更新：

- `quickstart.md`
- 相关 README 或脚本说明

这样能避免先写文档、后面又被实现细节推翻。

---

## 二、建议测试重点

### 1. 本地 converter 测试

应至少覆盖：

- `PDF` 请求继续携带分页参数
- `DOCX / PPTX / XLSX / 图片` 请求不携带分页参数
- 非 PDF 上传 MIME 与文件名正确
- 3.0 的 `parse_method / formula_enable / table_enable` 在非 PDF 路径也能传递

### 2. processor 路由测试

应明确验证在 `MINERU_MODE=local` 下：

- `.pdf` 优先走 `MinerULocalConverter`
- `.docx`
- `.pptx`
- `.xlsx`
- 常见图片扩展名

也会优先走 `MinerULocalConverter`

同时要确认：

- 本地不支持的 `DOC / PPT / HTML` 不会误路由到本地 MinerU

### 3. compose / smoke 测试

应至少覆盖：

- GPU override 下 `api` 和 `worker` 的 `MINERU_MODE`
- GPU override 下 `api` 和 `worker` 的 `MINERU_BACKEND`
- `mineru-api` 的健康检查仍为 `/health`
- 是否建立了合理的服务依赖关系

### 4. 文档验收测试

在文档层面应检查：

- GPU 本地支持集是否与官方本地支持集一致
- 是否明确写出“本地与云端能力不同”
- 是否明确写出“本轮不做 router / tasks / 多机多卡”

---

## 三、建议验收口径

本轮完成后，可以用以下口径判断是否达标。

### 必须满足

1. GPU 本地模式下，`PDF / image / DOCX / PPTX / XLSX` 能进入本地 MinerU 路径。
2. PDF 与非 PDF 的本地请求参数不再混用。
3. GPU compose 的 `api` 与 `worker` 使用一致的本地 backend 语义。
4. 关键单测与 smoke 测试补齐并通过。
5. 文档中明确写清本地模式与云端模式的边界。

### 可以暂缓

1. 配置面板开放高级参数。
2. 本地 `/tasks` 异步接口接入。
3. `mineru-router`。
4. 多机多卡。

---

## 四、实施风险

### 风险 1：非 PDF 本地请求参数可能与当前假设不完全一致

虽然官方文档明确给出了支持集，但对于不同文件类型在同步 `/file_parse` 下的参数细节，实际行为仍需要通过本地样本验证。

因此实现时应采用：

- 先补最小可行路径
- 再用真实样本做验证
- 避免一开始就把请求模型设计得过重

### 风险 2：GPU 环境问题可能掩盖功能问题

例如：

- 驱动版本
- 宿主机显卡可见性
- 首次模型下载
- 显存不足

这些问题可能导致“服务没起来”看起来像“代码没适配好”。

因此本轮测试应把：

- 代码路径验证
- compose 配置验证
- GPU 真机连通性验证

分开看待。

### 风险 3：文档容易再次把 cloud 与 local 混写

这轮之后的所有 GPU 文档都应坚持一个原则：

- 先写“本地支持什么”
- 再写“云端支持什么”
- 最后写“二者不同”

不要再使用模糊表述，例如“MinerU 已支持……”但不说明是 cloud 还是 local。

---

## 五、下一步建议

本轮文档确认后，下一步应进入：

1. 编写 improve-3-gpu 的详细实施计划
2. 按计划分任务修改 converter、compose、测试和文档
3. 完成后做单元测试、smoke 测试与 GPU 真机验证

在进入实施计划前，不建议直接开始改代码，否则很容易把“本地支持集补齐”和“router / tasks / 多卡”再次混在一起。
