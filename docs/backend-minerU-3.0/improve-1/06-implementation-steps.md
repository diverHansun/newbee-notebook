# 06 · 实施步骤

本文给出 improve-1 的**完整实施顺序**，每个阶段包含具体操作、验证方式和失败回滚预案。

---

## 前提条件

- 已完成分支创建（见 [README.md](./README.md) 的分支策略章节）：
  ```bash
  git checkout -b backend-minerU-3.0
  ```
- 本地 Docker Desktop 已启动，且 NVIDIA GPU 驱动已就绪（GPU 实施步骤要求）
- 项目根目录下 `.env` 文件已配置好现有参数（`MINERU_API_KEY`、`MINERU_MODE` 等）

---

## 阶段 1：Docker 基础设施（前置必做）

### 操作步骤

**1.1** 编辑 [docker/mineru/Dockerfile.gpu](../../../docker/mineru/Dockerfile.gpu)，替换版本：

```
FROM docker.m.daocloud.io/vllm/vllm-openai:v0.11.0
→ FROM docker.m.daocloud.io/vllm/vllm-openai:v0.11.2

'mineru[core]>=2.7.0'
→ 'mineru[core]>=3.0.0'
```

详见 [02-docker-infrastructure.md § 变更 1](./02-docker-infrastructure.md)

**1.2** 编辑 [docker/mineru/Dockerfile.cpu](../../../docker/mineru/Dockerfile.cpu)，替换版本：

```
"mineru[api,pipeline]>=2.7.0"
→ "mineru[api,pipeline]>=3.0.0"
```

**1.3** 编辑 [docker-compose.gpu.yml](../../../docker-compose.gpu.yml)，修改 healthcheck：

```
curl -f http://localhost:8000/docs >/dev/null 2>&1 || exit 1
→ curl -f http://localhost:8000/health || exit 1
```

**1.4** 提交这三个文件的变更：

```bash
git add docker/mineru/Dockerfile.gpu docker/mineru/Dockerfile.cpu docker-compose.gpu.yml
git commit -m "chore(docker): upgrade MinerU to 3.0, vLLM to 0.11.2, fix healthcheck endpoint"
```

### 验证

```bash
# 构建 GPU 镜像（--no-cache 确保拉取新版本）
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build --no-cache mineru-api

# 启动服务（首次启动会下载模型，约 10-20 分钟，取决于网速）
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d mineru-api

# 持续观察容器状态，等待 (healthy)
watch -n 10 'docker compose -f docker-compose.yml -f docker-compose.gpu.yml ps mineru-api'

# 手动检查 /health 端点
docker exec newbee-notebook-mineru-api curl -s http://localhost:8000/health | python3 -m json.tool
# 期望：{"status": "healthy", "version": "3.x.x", ...}
```

### 失败回滚

```bash
# 若构建失败或 healthcheck 一直不通过，回滚 Dockerfile.gpu
git checkout HEAD -- docker/mineru/Dockerfile.gpu docker/mineru/Dockerfile.cpu docker-compose.gpu.yml
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build --no-cache mineru-api
```

---

## 阶段 2：本地转换器新参数

Docker 阶段验证通过后再进行此步。

### 操作步骤

**2.1** 编辑 [mineru_local_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py)：

- 在 `__init__` 末尾新增三个参数（`parse_method`、`formula_enable`、`table_enable`）及对应实例变量
- 在 `_convert_range` 的 `form_data` 列表末尾新增三个条目

详见 [03-local-converter.md § 代码变更](./03-local-converter.md)

**2.2** 提交：

```bash
git add newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py
git commit -m "feat(local-converter): add parse_method, formula_enable, table_enable params for MinerU 3.0"
```

### 验证

```bash
# 单元验证：构造器参数
python -c "
from newbee_notebook.infrastructure.document_processing.converters.mineru_local_converter import MinerULocalConverter
c = MinerULocalConverter(parse_method='ocr', formula_enable=False, table_enable=True)
assert c._parse_method == 'ocr'
assert c._formula_enable == False
assert c._table_enable == True
print('Local converter constructor: OK')
"

# 集成验证：实际解析一份 PDF（GPU 容器运行时）
# 用已知样本 PDF，对比 parse_method=auto 和 parse_method=ocr 的输出差异
```

---

## 阶段 3：云端转换器新参数

### 操作步骤

**3.1** 编辑 [mineru_cloud_converter.py](../../../newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py)：

- 在 `__init__` 新增五个参数及实例变量（`model_version`、`enable_formula`、`enable_table`、`is_ocr`、`language`）
- 在 `_request_upload_url` 中扩展 payload 构建逻辑

详见 [04-cloud-converter.md § 代码变更](./04-cloud-converter.md)

**3.2** 提交：

```bash
git add newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py
git commit -m "feat(cloud-converter): add model_version, enable_formula, enable_table, is_ocr, language params for v4 API"
```

### 验证

```bash
# 构造器与空字符串转 None 验证
python -c "
from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import MinerUCloudConverter
c = MinerUCloudConverter(api_key='test', model_version='', is_ocr=None)
assert c._model_version is None, 'empty model_version should be None'
assert c._is_ocr is None
print('Cloud converter constructor: OK')
"

# 如有 API Key，做一次真实的云端转换验证（注意消耗配额）
# 验证 model_version=vlm 时 payload 包含 model_version 字段
# 验证 model_version=None 时 payload 不包含 model_version 字段
```

---

## 阶段 4：配置层

### 操作步骤

**4.1** 编辑 [document_processing.yaml](../../../newbee_notebook/configs/document_processing.yaml)：

- `mineru_cloud` 块新增 5 个配置项
- `mineru_local` 块新增 3 个配置项

详见 [05-config-layer.md § document_processing.yaml 变更](./05-config-layer.md)

**4.2** 编辑 [processor.py](../../../newbee_notebook/infrastructure/document_processing/processor.py)：

- Cloud 构造调用新增 5 个参数的读取与透传
- Local 构造调用新增 3 个参数的读取与透传
- 添加 `_model_version` 和 `_is_ocr` 的空字符串 → `None` 转换

详见 [05-config-layer.md § processor.py 变更](./05-config-layer.md)

**4.3** 提交：

```bash
git add newbee_notebook/configs/document_processing.yaml \
        newbee_notebook/infrastructure/document_processing/processor.py
git commit -m "feat(config): expose MinerU 3.0 new params via YAML/env vars, wire through processor"
```

### 验证

```bash
# 验证配置读取
python -c "
from newbee_notebook.infrastructure.document_processing.processor import DocumentProcessor
p = DocumentProcessor()
print('DocumentProcessor init: OK')
# 若有 MINERU_API_KEY，应看到 MinerUCloudConverter 初始化成功的 log
# 若 MINERU_MODE=local，应看到 MinerULocalConverter 初始化成功的 log
"

# 端到端：用一份样本 PDF 走完整个 process_and_save 链路
```

---

## 阶段 5：ZIP 解析回归验证

验证 MinerU 3.0 新版 ZIP 结构与现有 `_parse_result_zip` 的兼容性。

### 操作步骤（仅验证，无代码修改）

```bash
# 1. 用 GPU 模式（hybrid-auto-engine）处理一份样本 PDF
#    拿到返回的 ZIP，检查内部路径结构
docker exec newbee-notebook-mineru-api \
  curl -s -X POST http://localhost:8000/file_parse \
       -F "files=@/path/to/test.pdf" \
       -F "backend=hybrid-auto-engine" \
       -F "response_format_zip=true" \
       -F "return_md=true" \
       -F "return_content_list=true" \
       -F "return_images=true" \
       --output /tmp/test_output.zip

# 2. 检查 ZIP 内部路径（应有两层嵌套）
unzip -l /tmp/test_output.zip
# 期望类似：
# test/test_hybrid-auto-engine_auto/test.md
# test/test_hybrid-auto-engine_auto/images/xxx.png
# test/test_hybrid-auto-engine_auto/test_content_list_v2.json

# 3. 在应用层跑一次 end-to-end，检查 markdown 和图片资产能正常存储
# 用一份包含图片的 PDF 文档上传到应用，检查：
# - markdown 内容可读
# - 图片链接 /api/v1/documents/{id}/assets/images/{img} 能正常访问
# - 文档状态变为 PROCESSED
```

---

## 阶段 6：运行现有测试套件

```bash
# 运行 MinerU 相关单元测试
pytest tests/ -k "mineru" -v

# 运行文档处理相关测试
pytest tests/ -k "document" -v

# 如有 smoke test 脚本
python tests/smoke/test_document_pipeline.py
```

---

## 阶段 7：提交 PR 并合并

所有阶段验证通过后：

```bash
# 确保分支与 main 同步
git fetch origin
git rebase origin/main

# 推送到远端
git push origin backend-minerU-3.0

# 在 GitHub/Gitea 创建 PR：
# title: feat(mineru): upgrade to MinerU 3.0 and enhance API parameters
# base: main
# head: backend-minerU-3.0
```

PR 描述建议包含：

- 变更摘要（4 个阶段的 commit 链接）
- smoke test 截图或日志片段（证明 GPU 模式、cloud 模式均正常工作）
- 已知风险说明（CPU 镜像升级后 pipeline 行为可能有细微差异）

---

## 回滚总方案

若生产合并后发现问题：

```bash
# 方案 A：在 main 上 revert PR merge commit
git revert -m 1 <merge-commit-hash>
git push origin main

# 方案 B：直接回滚到合并前的 commit
git reset --hard <pre-merge-hash>
git push --force-with-lease origin main
# 注意：force-push main 需要 repo 权限，且要通知团队

# Docker 层回滚：重新构建旧版镜像
# 修改 Dockerfile.gpu 回 v0.11.0 + >=2.7.0
# docker compose build --no-cache mineru-api && docker compose up -d mineru-api
```

---

## 实施检查清单

实施前打钩确认：

- [ ] 分支 `backend-minerU-3.0` 已创建并推送到远端
- [ ] Docker Desktop 内存 ≥ 8GB（防止构建 OOM）
- [ ] 网络可访问 DaoCloud mirror（`docker.m.daocloud.io`）或已准备好科学上网
- [ ] `mineru_cache` volume 已挂载（防止每次重启重新下载模型）
- [ ] 已备份当前 `docker-compose.gpu.yml` 和两个 Dockerfile（或确认 git 可回滚）
- [ ] 测试样本 PDF 已准备（含文字、图片、表格、公式各一份）

实施后打钩确认：

- [ ] `docker compose ps mineru-api` 显示 `Up (healthy)`
- [ ] `/health` 返回 `{"status": "healthy"}`
- [ ] 本地转换器构造器验证脚本通过
- [ ] 云端转换器构造器验证脚本通过
- [ ] 配置读取验证脚本通过
- [ ] ZIP 解析回归验证通过（新版两层嵌套路径正确解析）
- [ ] 现有测试套件 `pytest tests/ -k "mineru"` 全部通过
- [ ] 端到端文档处理（上传 → 转换 → 索引 → 访问图片）正常工作
