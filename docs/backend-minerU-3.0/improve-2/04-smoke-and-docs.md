# 04 · Smoke 与文档整理

本文覆盖三个面向交付的工作：

1. 升级 MinerU cloud smoke 验证
2. 更新 `quickstart.md`
3. 删除遗留脚本 `up-mineru.ps1`

---

## 1. smoke 验证如何升级

### 现状

当前遗留的 [scripts/mineru_v4_smoke_test.py](../../../scripts/mineru_v4_smoke_test.py) 主要验证：

- 单文件 PDF
- `file-urls/batch`
- 基础轮询链路

它还没有覆盖：

- 多文件 batch
- `html -> MinerU-HTML`
- `enable_formula`
- `enable_table`
- `language`
- `data_id`

### 建议

本轮不删除，而是升级：

1. 支持输入一个或多个文件路径
2. 支持在一次运行中构造真正的 batch 请求
3. 支持输出每个文件的：
   - `data_id`
   - `state`
   - `full_zip_url`
   - markdown 文件路径
4. HTML 文件自动走 `MinerU-HTML`
5. 在日志里明确展示本次被拆成了几个 batch

### 与自动化测试的关系

这个 smoke 工具更适合作为“手工 live 验证工具”，因为它依赖：

- 真实 Token
- 真实样本文件
- 实际配额

自动化测试仍然应放在：

- `newbee_notebook/tests/unit/`
- `newbee_notebook/tests/smoke/`

前者做 mock/patch，后者做仓库内可重复的轻量验证。

---

## 2. `quickstart.md` 需要怎么改

### 必须更新的点

1. 默认 `docker compose up -d` 使用的是官方 v4 cloud API
2. 默认模式支持的文件类型需要扩到：
   - `pdf/doc/docx/ppt/pptx/html/图片`
3. HTML 需要特殊路由到 `MinerU-HTML`
4. 官方限制要写清楚：
   - `200 MB`
   - `200 页`
   - batch 安全上限按 `50` 个文件处理
5. 超限处理说明：
   - 文档类文件会触发 fallback
   - 图片类文件的 fallback 能力有限，需要单独注明

### 还要同步的描述

- GPU 本地模式当前仍主要按 PDF 说明，不要在本轮文档里提前承诺“GPU 本地已支持更多类型”
- `up-mineru.ps1` 的内容要从 quickstart 与 scripts 文档中移除

---

## 3. `scripts/up-mineru.ps1` 为什么应删除

当前 [up-mineru.ps1](../../../scripts/up-mineru.ps1) 属于历史遗留脚本，主要问题有两个：

1. 它把“无 GPU 时使用 CPU MinerU”当成现状，但仓库现在并没有正式的 CPU 本地一键 compose 路径
2. 它容易让读文档的人误以为“本地 CPU MinerU”仍然是当前主推模式

既然本轮已经明确：

- 默认模式是 cloud
- CPU 本地能力暂不继续推进

那这个脚本就没有保留价值了，建议直接删除，并同步更新：

- [scripts/README.md](../../../scripts/README.md)
- [quickstart.md](../../../quickstart.md)

---

## 4. 推荐测试布局

按本轮范围，测试建议放在：

- 单元测试：
  - `newbee_notebook/tests/unit/`
- smoke 测试：
  - `newbee_notebook/tests/smoke/`

建议覆盖的用例：

1. 文件类型扩展：
   - `ppt/html/image` 的上传与类型映射
2. cloud converter：
   - 扩展名识别
   - HTML 特殊路由
   - 超限预检
3. batch 编排：
   - 文档分组
   - 按 `50` 个文件切片
   - `data_id -> document_id` 映射
4. 文档/脚本整理：
   - `scripts/README.md` 与 `quickstart.md` 中不再引用 `up-mineru.ps1`

---

## 验收标准

1. 手工 smoke 工具支持多文件 cloud batch 验证
2. `quickstart.md` 与项目真实能力对齐
3. `scripts/up-mineru.ps1` 被删除
4. 自动化测试全部放在 `newbee_notebook/tests/` 下
