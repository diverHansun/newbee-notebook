# 05 · 实施步骤

本文给出 improve-2 的推荐实施顺序、验证方式与风险控制。

---

## 阶段 1：补齐上传与类型支持

### 目标

先让仓库真正“收得进”本轮目标文件类型。

### 涉及文件

- [document_type.py](../../../newbee_notebook/domain/value_objects/document_type.py)
- [local_storage.py](../../../newbee_notebook/infrastructure/storage/local_storage.py)
- 相关类型测试

### 操作

1. 扩展 `DocumentType` 的映射与 `supported_extensions`
2. 扩展上传层允许的扩展名
3. 补齐 `ppt/html/image` 相关测试

### 验证

- Library 上传接口可接收目标扩展名
- 类型测试全部通过

---

## 阶段 2：升级 cloud converter

### 目标

让默认 cloud 模式具备：

- 新文件类型识别
- HTML 特殊路由
- 官方限制预检
- 限制型错误 fallback

### 涉及文件

- [mineru_cloud_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py)
- [processor.py](../../../newbee_notebook/infrastructure/document_processing/processor.py)

### 操作

1. 扩大 cloud converter 的 `SUPPORTED_EXTENSIONS`
2. 增加 HTML 的 `model_version` 解析逻辑
3. 增加文件大小与 PDF 页数预检
4. 为限制型错误定义清晰异常类型
5. 确保 fallback 时不误伤 circuit breaker

### 验证

- HTML 路由测试通过
- 超限 PDF / 大文件触发 fallback 的测试通过
- 非网络错误不会被当成 MinerU 不可用

---

## 阶段 3：实现 cloud batch 编排

### 目标

把“同一次多文件处理”真正变成 shared batch。

### 涉及文件

- 新增 cloud batch 服务
- [notebook_document_service.py](../../../newbee_notebook/application/services/notebook_document_service.py)
- [document_tasks.py](../../../newbee_notebook/infrastructure/tasks/document_tasks.py)

### 操作

1. 新增 batch 服务，负责：
   - 请求 batch upload url
   - 批量上传
   - 轮询结果
   - 按 `data_id` 映射结果
2. 在 notebook add 流程中收集 full pipeline 文档
3. 将 cloud eligible 文档分组、切片并入队新 batch 任务
4. batch 成功后，继续派发现有 `index_document_task`
5. 对不适合 batch 的文档维持单文档路径

### 验证

- 同一次文档加入笔记本操作可共享 batch
- HTML 与非 HTML 分组正确
- 文件数超过 `50` 时能拆成多个 batch

---

## 阶段 4：更新 smoke 与用户文档

### 目标

把能力变化同步到手工验证工具与项目文档。

### 涉及文件

- `scripts/mineru_v4_smoke_test.py` 或等价 smoke 工具
- [quickstart.md](../../../quickstart.md)
- [scripts/README.md](../../../scripts/README.md)
- 删除 [up-mineru.ps1](../../../scripts/up-mineru.ps1)

### 操作

1. 升级 smoke 工具支持多文件与 HTML 路由
2. 更新 quickstart 对默认 cloud 模式的说明
3. 删除遗留 CPU/GPU 启动脚本
4. 清理脚本文档中的过时描述

### 验证

- smoke 工具能展示 batch 结果
- quickstart 文档与当前实现一致
- 仓库不再引用 `up-mineru.ps1`

---

## 阶段 5：补齐自动化测试

### 测试放置原则

所有自动化测试放在：

- `newbee_notebook/tests/unit/`
- `newbee_notebook/tests/smoke/`

### 建议覆盖

1. `DocumentType` 与上传扩展名支持
2. cloud converter 的：
   - 扩展名识别
   - HTML 特殊路由
   - 超限预检
   - payload 构造
3. batch 编排：
   - 文档分组
   - `50` 个文件切片
   - `data_id` 映射
   - HTML / 非 HTML 分流
4. notebook add 调度：
   - batch 与单文档任务的混合分发
5. 文档整理：
   - 关键文档不再出现 `up-mineru.ps1`

### 本轮不做

- GPU 真机测试
- 真实 API 配额的大规模回归
- 主动切分上传

---

## 风险与回滚

### 主要风险

1. 批处理调度改动会触及文档处理主路径
2. HTML 特殊路由若处理不严，可能误影响非 HTML
3. 图片支持虽然主路径增强，但 fallback 仍不完整

### 回滚建议

若 batch 编排实现过重或回归风险过大，可临时采用分段回滚：

1. 保留文件类型扩展与 HTML 路由
2. 保留 smoke / quickstart / 脚本清理
3. 暂时撤回“真 batch 编排”，回到单文档处理

这样至少可以先完成默认 cloud 模式的文件类型补齐。

---

## 验收清单

- [ ] 默认 cloud 模式支持 `pdf/doc/docx/ppt/pptx/html/图片`
- [ ] HTML 自动走 `MinerU-HTML`
- [ ] 多文件处理可共用一个或多个 MinerU batch
- [ ] 超过 `200 MB` 的文档触发 fallback
- [ ] 超过 `200 页` 的 PDF 触发 fallback
- [ ] `quickstart.md` 已同步更新
- [ ] `scripts/up-mineru.ps1` 已删除
- [ ] 单元测试与 smoke 测试位于 `newbee_notebook/tests/`
- [ ] 本地 CPU / GPU 范围边界在文档中写清楚
