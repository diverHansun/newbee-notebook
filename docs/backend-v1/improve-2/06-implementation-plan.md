# 实施计划

## 1. 任务概览

### 1.1 任务分组

| 分组 | 任务数 | 预计工时 | 优先级 | 描述 |
|------|--------|----------|--------|------|
| Phase 1: 依赖与配置 | 3 | 1h | P0 | SDK 安装、配置文件更新 |
| Phase 2: Converter 实现 | 4 | 4h | P0 | 云服务 Converter、本地 Converter 重构 |
| Phase 3: Docker 配置 | 3 | 2h | P0 | Compose 文件修改、Profile 配置 |
| Phase 4: 测试 | 4 | 3h | P1 | 单元测试、集成测试、手动测试 |
| Phase 5: 文档 | 2 | 2h | P1 | README 更新、环境变量文档 |
| **总计** | **16** | **12h** | - | 约 1.5-2 个工作日 |

### 1.2 依赖关系

```
Phase 1 (依赖与配置)
    │
    ├─▶ Task 1.1: 添加 SDK 依赖
    ├─▶ Task 1.2: 更新配置文件
    └─▶ Task 1.3: 更新环境变量模板
         │
         ▼
Phase 2 (Converter 实现)
    │
    ├─▶ Task 2.1: 实现 MinerUCloudConverter
    ├─▶ Task 2.2: 重构 MinerULocalConverter
    ├─▶ Task 2.3: 更新 DocumentProcessor
    └─▶ Task 2.4: 更新导入路径
         │
         ▼
Phase 3 (Docker 配置)
    │
    ├─▶ Task 3.1: 修改 docker-compose.yml
    ├─▶ Task 3.2: 更新 docker-compose.gpu.yml
    └─▶ Task 3.3: 验证 Profile 机制
         │
         ▼
Phase 4 (测试)
    │
    ├─▶ Task 4.1: Converter 单元测试
    ├─▶ Task 4.2: 集成测试
    ├─▶ Task 4.3: 模式切换测试
    └─▶ Task 4.4: 手动功能测试
         │
         ▼
Phase 5 (文档)
    │
    ├─▶ Task 5.1: 更新 README
    └─▶ Task 5.2: 更新 .env.example
```

## 2. Phase 1: 依赖与配置

### Task 1.1: 添加 SDK 依赖

**文件**：`requirements.txt`

**变更内容**：

```diff
+ # MinerU Cloud Service SDK
+ mineru-kie-sdk>=0.1.1
```

**验收标准**：
- [ ] requirements.txt 已添加 mineru-kie-sdk
- [ ] pip install -r requirements.txt 成功
- [ ] 可以 import mineru_kie_sdk

**预计工时**：15min

---

### Task 1.2: 更新配置文件

**文件**：`newbee_notebook/configs/document_processing.yaml`

**变更内容**：

```yaml
document_processing:
  mineru_enabled: ${MINERU_ENABLED:true}
  mineru_mode: ${MINERU_MODE:cloud}

  mineru_cloud:
    pipeline_id: ${MINERU_PIPELINE_ID:}
    base_url: ${MINERU_CLOUD_BASE_URL:https://mineru.net/api/kie}
    timeout_seconds: ${MINERU_CLOUD_TIMEOUT:300}
    poll_interval: ${MINERU_CLOUD_POLL_INTERVAL:5}

  mineru_local:
    api_url: ${MINERU_LOCAL_API_URL:http://mineru-api:8000}
    backend: ${MINERU_BACKEND:pipeline}
    lang_list: ${MINERU_LANG_LIST:ch}
    timeout_seconds: ${MINERU_LOCAL_TIMEOUT:0}

  unavailable_cooldown_seconds: 300
  documents_dir: ${DOCUMENTS_DIR:data/documents}
```

**验收标准**：
- [ ] 配置文件语法正确（YAML 格式）
- [ ] 所有字段都有默认值或环境变量
- [ ] 配置可以被正确加载

**预计工时**：15min

---

### Task 1.3: 更新环境变量模板

**文件**：`.env.example`

**变更内容**：

```bash
# MinerU Configuration
MINERU_MODE=cloud
MINERU_PIPELINE_ID=

# Cloud Service
# MINERU_CLOUD_BASE_URL=https://mineru.net/api/kie
# MINERU_CLOUD_TIMEOUT=300
# MINERU_CLOUD_POLL_INTERVAL=5

# Local Service
# MINERU_LOCAL_API_URL=http://mineru-api:8000
# MINERU_BACKEND=pipeline
# MINERU_LANG_LIST=ch
# MINERU_LOCAL_TIMEOUT=0
```

**验收标准**：
- [ ] .env.example 已更新
- [ ] 包含所有必要的环境变量
- [ ] 注释清晰，说明每个变量的用途

**预计工时**：30min

## 3. Phase 2: Converter 实现

### Task 2.1: 实现 MinerUCloudConverter

**文件**：新建 `newbee_notebook/infrastructure/document_processing/converters/mineru_cloud_converter.py`

**关键代码**：参考 [03-sdk-integration.md](./03-sdk-integration.md#41-类设计)

**验收标准**：
- [ ] MinerUCloudConverter 类已实现
- [ ] can_handle 方法正确
- [ ] convert 方法支持异步
- [ ] 限制检查逻辑完整
- [ ] 错误处理完善

**预计工时**：2h

---

### Task 2.2: 重构 MinerULocalConverter

**文件**：
- 重命名：`mineru_converter.py` -> `mineru_local_converter.py`
- 类名：`MinerUConverter` -> `MinerULocalConverter`

**变更内容**：

```diff
- class MinerUConverter(Converter):
+ class MinerULocalConverter(Converter):
    """Converter for PDFs via MinerU HTTP API (local Docker service)"""
```

**验收标准**：
- [ ] 文件已重命名
- [ ] 类名已更新
- [ ] 原有逻辑保持不变
- [ ] 注释更新说明用途

**预计工时**：30min

---

### Task 2.3: 更新 DocumentProcessor

**文件**：`newbee_notebook/infrastructure/document_processing/processor.py`

**变更内容**：

```python
from .converters.mineru_cloud_converter import MinerUCloudConverter
from .converters.mineru_local_converter import MinerULocalConverter

class DocumentProcessor:
    def __init__(self, config: Optional[dict] = None):
        # 根据 mode 选择 Converter
        mode = dp_cfg.get("mineru_mode", "cloud")

        if mode == "cloud":
            # 初始化 MinerUCloudConverter
            ...
        elif mode == "local":
            # 初始化 MinerULocalConverter
            ...

        # Fallback converters
        converters.extend([PyPdfConverter(), MarkItDownConverter()])
```

**验收标准**：
- [ ] 导入语句已更新
- [ ] 初始化逻辑根据 mode 分支
- [ ] Fallback 机制保持不变
- [ ] 熔断机制适配云服务

**预计工时**：1h

---

### Task 2.4: 更新导入路径

**文件**：`newbee_notebook/infrastructure/document_processing/converters/__init__.py`

**变更内容**：

```diff
  from .base import Converter, ConversionResult
- from .mineru_converter import MinerUConverter
+ from .mineru_cloud_converter import MinerUCloudConverter
+ from .mineru_local_converter import MinerULocalConverter
  from .pypdf_converter import PyPdfConverter
  from .markitdown_converter import MarkItDownConverter

  __all__ = [
      "Converter",
      "ConversionResult",
-     "MinerUConverter",
+     "MinerUCloudConverter",
+     "MinerULocalConverter",
      "PyPdfConverter",
      "MarkItDownConverter",
  ]
```

**验收标准**：
- [ ] __init__.py 已更新
- [ ] 所有 Converter 正确导出
- [ ] 无导入错误

**预计工时**：30min

## 4. Phase 3: Docker 配置

### Task 3.1: 修改 docker-compose.yml

**文件**：`docker-compose.yml`

**关键变更**：

1. celery-worker 环境变量：

```yaml
environment:
  MINERU_MODE: ${MINERU_MODE:-cloud}
  MINERU_PIPELINE_ID: ${MINERU_PIPELINE_ID:-}
  MINERU_LOCAL_API_URL: ${MINERU_LOCAL_API_URL:-http://mineru-api:8000}
  # ...
```

2. celery-worker depends_on：

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_started
  elasticsearch:
    condition: service_healthy
  # 移除 mineru-api
```

3. mineru-api profile：

```yaml
mineru-api:
  # ... 其他配置 ...
  profiles:
    - mineru-local
```

**验收标准**：
- [ ] celery-worker 环境变量已更新
- [ ] celery-worker 不再强依赖 mineru-api
- [ ] mineru-api 添加了 profile
- [ ] YAML 语法正确

**预计工时**：1h

---

### Task 3.2: 更新 docker-compose.gpu.yml

**文件**：`docker-compose.gpu.yml`

**变更内容**：

```yaml
services:
  # 移除 celery-worker 覆盖（通过 .env 管理）

  mineru-api:
    # ... GPU 配置保持 ...
    profiles:
      - mineru-local
```

**验收标准**：
- [ ] 移除 celery-worker 环境变量覆盖
- [ ] mineru-api 继承 profile 配置
- [ ] GPU 相关配置保持不变

**预计工时**：30min

---

### Task 3.3: 验证 Profile 机制

**验证步骤**：

```bash
# 1. 默认启动（不包含 mineru-api）
docker-compose up -d
docker-compose ps | grep mineru
# 应该没有输出

# 2. Profile 启动（包含 mineru-api）
docker-compose --profile mineru-local up -d
docker-compose ps | grep mineru
# 应该有 newbee-notebook-mineru-api

# 3. 清理
docker-compose down
```

**验收标准**：
- [ ] 默认启动不包含 mineru-api
- [ ] --profile mineru-local 启动包含 mineru-api
- [ ] Profile 可以正确组合使用

**预计工时**：30min

## 5. Phase 4: 测试

### Task 4.1: Converter 单元测试

**文件**：新建 `tests/unit/infrastructure/document_processing/test_mineru_cloud_converter.py`

**测试内容**：

```python
def test_cloud_converter_init()
def test_cloud_converter_can_handle()
def test_cloud_converter_check_limits_size()
def test_cloud_converter_check_limits_pages()
def test_cloud_converter_convert_success()
def test_cloud_converter_convert_network_error()
def test_cloud_converter_convert_timeout()
```

**验收标准**：
- [ ] 覆盖主要功能点
- [ ] Mock 外部依赖（SDK）
- [ ] 测试通过率 100%

**预计工时**：2h

---

### Task 4.2: 集成测试

**文件**：新建 `tests/integration/test_document_processor_modes.py`

**测试内容**：

```python
def test_processor_cloud_mode_init()
def test_processor_local_mode_init()
def test_processor_fallback_mechanism()
def test_processor_circuit_breaker()
```

**验收标准**：
- [ ] 测试模式切换
- [ ] 测试 Fallback 机制
- [ ] 测试熔断机制
- [ ] 测试通过率 100%

**预计工时**：1h

---

### Task 4.3: 模式切换测试

**测试场景**：

| 场景 | MINERU_MODE | MINERU_PIPELINE_ID | 预期结果 |
|------|-------------|-------------------|----------|
| 场景 1 | cloud | valid-id | 使用云服务 |
| 场景 2 | cloud | 空 | 跳过云服务，使用 PyPDF |
| 场景 3 | local | 任意 | 使用本地服务 |

**验收标准**：
- [ ] 所有场景测试通过
- [ ] 日志输出符合预期
- [ ] 无异常错误

**预计工时**：30min

---

### Task 4.4: 手动功能测试

**测试步骤**：

```bash
# 1. 云服务模式测试
export MINERU_MODE=cloud
export MINERU_PIPELINE_ID=your-id
docker-compose up -d
# 上传测试文档，验证处理成功

# 2. 本地 CPU 模式测试
export MINERU_MODE=local
docker-compose --profile mineru-local up -d
# 上传测试文档，验证处理成功

# 3. 本地 GPU 模式测试（如有 GPU）
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile mineru-local up -d
# 上传测试文档，验证处理成功
```

**验收标准**：
- [ ] 云服务模式文档处理成功
- [ ] 本地 CPU 模式文档处理成功
- [ ] 本地 GPU 模式文档处理成功（如有 GPU）
- [ ] 各模式切换正常

**预计工时**：1.5h

## 6. Phase 5: 文档

### Task 5.1: 更新 README

**文件**：`README.md`

**更新内容**：

```markdown
## Quick Start

### Cloud Service Mode (Recommended)
...

### Local Mode
...

## Configuration

- MINERU_MODE: cloud | local
- MINERU_PIPELINE_ID: Pipeline ID for cloud service
...
```

**验收标准**：
- [ ] 快速开始章节已更新
- [ ] 配置说明已添加
- [ ] 包含三种模式的使用示例

**预计工时**：1h

---

### Task 5.2: 更新 .env.example

**文件**：`.env.example`

**验收标准**：
- [ ] 包含所有 MinerU 相关变量
- [ ] 注释清晰
- [ ] 示例值正确

**预计工时**：30min

---

### Task 5.3: 更新改进文档

**文件**：`docs/backend-v1/improve-2/*.md`

**验收标准**：
- [ ] 所有文档已完成
- [ ] 文档结构清晰
- [ ] 代码示例正确

**预计工时**：已完成

## 7. 验收标准

### 7.1 功能验收

- [ ] 云服务模式可以正常处理文档
- [ ] 本地 CPU 模式可以正常处理文档
- [ ] 本地 GPU 模式可以正常处理文档
- [ ] 模式可以无缝切换
- [ ] Fallback 机制正常工作
- [ ] 熔断机制正常工作

### 7.2 性能验收

- [ ] 云服务模式处理速度提升明显
- [ ] 默认启动时间减少（无 mineru-api）
- [ ] 内存占用减少（云服务模式）

### 7.3 兼容性验收

- [ ] API 端点无变更
- [ ] 数据模型无变更
- [ ] 存储结构无变更
- [ ] 现有功能全部正常

### 7.4 文档验收

- [ ] 所有改进文档已撰写
- [ ] README 已更新
- [ ] .env.example 已更新
- [ ] 代码注释完整

### 7.5 测试验收

- [ ] 单元测试通过率 100%
- [ ] 集成测试通过率 100%
- [ ] 手动测试全部通过
- [ ] 无遗留 bug

## 8. 风险评估

### 8.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| SDK 不稳定 | 高 | 低 | Fallback 机制，降级到 PyPDF |
| 云服务限制 | 中 | 中 | 提前检查，超限降级本地 |
| 网络不稳定 | 中 | 中 | 熔断机制，自动降级 |
| 配置错误 | 低 | 中 | 启动时验证，清晰错误提示 |

### 8.2 运营风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Pipeline 额度用尽 | 高 | 中 | 监控使用量，提前清理 |
| 云服务故障 | 高 | 低 | 保留本地部署能力 |
| 迁移中断业务 | 高 | 低 | 灰度发布，准备回滚方案 |

## 9. 上线计划

### 9.1 开发环境

**时间**：第 1 天

```
上午: Phase 1, 2 (依赖、Converter)
下午: Phase 3 (Docker)
晚上: Phase 4 (测试)
```

### 9.2 预发环境

**时间**：第 2 天上午

```
1. 部署代码
2. 配置云服务
3. 功能验证
4. 性能测试
```

### 9.3 生产环境

**时间**：第 2 天下午（非高峰期）

```
1. 灰度发布（10% 流量）
2. 监控指标
3. 逐步扩大（50%）
4. 全量发布（100%）
5. 持续监控 24h
```

## 10. 回滚方案

### 10.1 触发条件

- 错误率超过 5%
- 处理失败率超过 10%
- 性能下降超过 30%
- 出现重大 bug

### 10.2 回滚步骤

```bash
# 1. 停止服务
docker-compose down

# 2. 切换代码
git checkout main

# 3. 恢复配置
cp .env.backup .env

# 4. 启动服务
docker-compose up -d

# 5. 验证
curl http://localhost:8000/health
```

### 10.3 回滚时间

预计回滚时间：5 分钟

## 11. 后续优化

### 11.1 短期优化（1 周内）

- [ ] 监控指标面板
- [ ] 告警规则配置
- [ ] 性能基准测试
- [ ] 用户使用文档

### 11.2 中期优化（1 个月内）

- [ ] 多 Pipeline 轮换机制
- [ ] 自动清理旧文件
- [ ] 成本分析报告
- [ ] A/B 测试对比

### 11.3 长期优化（3 个月内）

- [ ] 智能模式选择（根据文件大小自动选择）
- [ ] 批量处理优化
- [ ] 缓存机制（重复文档）
- [ ] 费用优化策略
