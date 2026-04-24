# 02 · 默认 API 模式扩容

本文描述默认 cloud 模式下的三组核心改动：

1. 扩展支持的文件类型
2. 为 HTML 做 `MinerU-HTML` 特殊路由
3. 对 `200 MB / 200 页` 限制做工程化 fallback

---

## 现状问题

### 1. 上传层还没有放行目标类型

当前仓库里，上传与文档类型识别还没有覆盖本轮目标范围：

- [document_type.py](../../../newbee_notebook/domain/value_objects/document_type.py)
- [local_storage.py](../../../newbee_notebook/infrastructure/storage/local_storage.py)

这意味着就算 cloud converter 能处理，文件也可能在“上传到 Library”这一步就被挡掉。

### 2. Cloud converter 当前只支持三类扩展

当前 [mineru_cloud_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py) 只支持：

- `.pdf`
- `.doc`
- `.docx`

这与官方 cloud 精准解析 API 的支持范围明显不一致。

### 3. `model_version` 现在还是“全局配置思维”

目前 `model_version` 是配置项，而不是按文件类型解析的路由规则。对 HTML 来说这不够，因为：

- HTML 必须路由到 `MinerU-HTML`
- 其他文件则不应误用 `MinerU-HTML`

### 4. 对官方大小 / 页数限制还没有显式处理

默认 cloud 模式缺少两类工程动作：

- 预检：在本地就能判断超限时，直接不要调用官方 API
- 限制报错归一化：当官方返回超限错误时，应触发 fallback，而不是把它当成“外部服务不可达”

---

## 目标支持范围

### 1. 本轮目标扩展名

本轮默认 cloud 模式按如下范围补齐：

- 文档类：
  - `.pdf`
  - `.doc`
  - `.docx`
  - `.ppt`
  - `.pptx`
  - `.html`
  - `.htm`
- 常见静态图片：
  - `.png`
  - `.jpg`
  - `.jpeg`
  - `.bmp`
  - `.webp`
  - `.tif`
  - `.tiff`

说明：

- `ppt` 可以继续映射到现有的 `PPTX` 语义层，避免新增过多值对象复杂度
- `html/htm` 建议新增 `HTML` 文档类型
- 图片建议新增统一的 `IMAGE` 文档类型，而不是细分成 `PNG/JPEG/...`

### 2. 对现有 fallback 能力的真实覆盖

按当前仓库状态，本轮可期待的 fallback 覆盖是：

- `pdf` -> MinerU cloud 失败时回退到 MarkItDown
- `doc/docx/ppt/pptx/html` -> MinerU cloud 失败时回退到 MarkItDown
- `图片` -> 主路径由 MinerU cloud 处理，但 fallback 不完整

这部分会在用户文档里明确写出来。

---

## HTML 特殊路由

### 设计目标

HTML 需要特殊路由，但不应该污染其他文件类型的行为。

### 路由规则

建议在 cloud converter 内引入按扩展名解析的模型选择逻辑：

1. 若文件是 `.html` 或 `.htm`
   - 强制 `model_version=MinerU-HTML`
2. 若文件不是 HTML
   - 只允许使用：
     - `pipeline`
     - `vlm`
     - 空值（交给官方默认）
3. 若全局配置被设置成 `MinerU-HTML`，但当前文件不是 HTML
   - 忽略该值并回落到默认策略
   - 同时记录 warning，避免管理员误以为配置已生效

### 这样设计的原因

- 可以保证 HTML 能用到官方专用能力
- 可以防止 PDF / DOC / PPT 被错误送入 HTML 模型
- 配置仍然保留运维自由度，但不会放大误配风险

---

## 超限 fallback 设计

### 1. 本地可预检的部分

建议在 cloud converter 或其上层 batch 服务中统一加入预检：

- 对所有文件：
  - 读取文件大小，若 `> 200 MB`，直接判定为 cloud 不可用，触发 fallback
- 对 PDF 文件：
  - 用 `pypdf` 读取页数，若 `> 200 页`，直接触发 fallback

### 2. 本地不可预检的部分

对于 `doc/docx/ppt/pptx/html/图片`，页数/页片数量并不总能低成本拿到。因此本轮采用保守策略：

- 优先做文件大小预检
- 页数相关限制交给官方接口判断
- 一旦官方返回明确的限制型错误，再触发 fallback

### 3. 错误分类

建议新增一个“非网络型、可回退”的 cloud 例外类型，例如：

- `MinerUCloudLimitExceededError`
- 或 `MinerUCloudFallbackSignal`

它与现有 `MinerUCloudTransientError` 的语义不同：

- `TransientError`：表示网络 / CDN / TLS / 瞬时错误，可能触发熔断
- `LimitExceeded / FallbackSignal`：表示接口限制、模型路由不适用、文件不应继续走 cloud；应直接回退，不应记作服务不可用

### 4. fallback 的实际落点

对文档类文件，fallback 继续落到现有 MarkItDown 路径即可。

对图片文件，本轮做如下保守处理：

- 默认 cloud 主路径可用
- 但若图片在 cloud 侧被限制或拒绝，当前 fallback 无法保证等价 OCR 结果
- 因此实现中需要在错误信息里明确“当前图片 fallback 能力有限”

---

## 需要同步修改的仓库位置

### 上传 / 类型层

- [document_type.py](../../../newbee_notebook/domain/value_objects/document_type.py)
- [local_storage.py](../../../newbee_notebook/infrastructure/storage/local_storage.py)
- 相关类型测试：
  - [test_document_type_support.py](../../../newbee_notebook/tests/unit/infrastructure/document_processing/test_document_type_support.py)

### Cloud converter 层

- [mineru_cloud_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py)
- [processor.py](../../../newbee_notebook/infrastructure/document_processing/processor.py)

---

## 验收标准

完成本节实现后，应满足：

1. Library 上传能接收目标扩展名
2. 默认 cloud 模式能正确识别这些扩展名并选择 MinerU cloud
3. HTML 文件上传时强制走 `MinerU-HTML`
4. 非 HTML 文件不会误用 `MinerU-HTML`
5. `> 200 MB` 文件能直接触发 fallback
6. `> 200 页` 的 PDF 能直接触发 fallback
7. 限制型错误不会错误触发 circuit breaker
