# 01 - 问题分析：MinerU 批处理的内存/显存泄漏

## 1. 问题发现

### 1.1 测试场景

使用 MinerU Local GPU 模式处理一本 462 页的 PDF 教材（31 MB），通过前端上传至 Library 触发文档处理流水线。

| 项目 | 值 |
|------|------|
| 文档 | 数字电子技术基础简明教程_11695986.pdf |
| 页数 | 462 |
| 大小 | 31 MB |
| GPU | NVIDIA RTX 5060 Ti 16 GB (Blackwell) |
| WSL2 VM 内存 | 16 GB |
| MinerU 后端 | hybrid-auto-engine |

### 1.2 故障表现

前序修复已将 PDF 分批发送（20 页/批），但在第 2 批开始时，MinerU 容器进程被 Linux OOM Killer 终止。

`wsl dmesg` 输出确认：

```
oom-kill:constraint=CONSTRAINT_NONE, ...
Killed process <pid> (python3) total-vm:...kB
```

将批大小从 50 降至 20 后可勉强通过，但处理时间长达 17 分钟（24 个批次），且后续批次处理速度逐渐下降，表明内存仍在累积。

### 1.3 核心矛盾

每批 60 页约需 640 MB 图像内存（200 DPI，每页约 10.7 MB），加上模型权重约 4 GB，理论上 16 GB 内存完全可以容纳单批处理。问题在于**前一批次的内存在下一批次开始前没有被释放**，导致内存随批次数线性增长。

## 2. MinerU 源码分析

通过分析 MinerU 源码（本地克隆版本，仅用于阅读，不直接使用），定位了以下三处根因。

### 2.1 根因一：`clean_vram()` 阈值陷阱

**位置**：`mineru/utils/model_utils.py`

```python
def clean_vram(device, vram_threshold=8):
    total_memory = get_vram(device)
    if total_memory and total_memory <= vram_threshold:
        clean_memory(device)   # gc.collect() + torch.cuda.empty_cache()
```

`clean_vram()` 是 MinerU 在推理阶段间释放显存的唯一入口。**但它使用硬编码阈值 8 GB**——仅当 GPU 总显存不超过 8 GB 时才执行清理。

RTX 5060 Ti 有 16 GB 显存，`get_vram()` 返回 16，`16 <= 8` 为 `False`，因此清理永远不执行。

以下是 `clean_vram()` 在 MinerU 中的所有调用点：

| 调用位置 | 触发时机 |
|----------|----------|
| `pipeline_analyze.py` L209 | `batch_image_analyze` 结束后 |
| `batch_analyze.py` L74 | 公式识别完成后 |
| `batch_analyze.py` L191 | 表格 OCR 完成后 |
| `model_json_to_middle_json.py` L249-251 | 中间 JSON 生成结束后 |
| `hybrid_analyze.py` L452, L524 | Hybrid 文档分析结束后 |

以上所有调用在 16 GB GPU 上均为空操作。

### 2.2 根因二：FastAPI 端点无内存清理

**位置**：`mineru/cli/fast_api.py`

MinerU 的 `/file_parse` 端点在请求完成后仅通过 `BackgroundTasks` 清理临时文件目录：

```python
@app.post(path="/file_parse", ...)
async def parse_pdf(...):
    unique_dir = os.path.join(output_dir, str(uuid.uuid4()))
    background_tasks.add_task(cleanup_file, unique_dir)  # 仅清理文件
    await aio_do_parse(...)
    return ...  # 无 gc.collect()，无 torch.cuda.empty_cache()
```

请求返回后，Python 仅靠 GC 分代回收惰性释放页面图像和中间数据。在连续批次请求场景下，Python GC 可能来不及在下一个请求到达前完成回收。

### 2.3 根因三：页面图像双份驻留

**位置**：`mineru/backend/pipeline/pipeline_analyze.py`，`mineru/backend/pipeline/batch_analyze.py`

MinerU 的推理流程中，每页 PDF 会同时存在 PIL Image 和 NumPy 数组两份副本：

```python
# pipeline_analyze.py — 加载所有页面图像
images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)

# batch_analyze.py — 创建 NumPy 副本
pil_images = [image for image, _, _ in images_with_extra_info]
np_images = [np.asarray(image) for image, _, _ in images_with_extra_info]
```

对于 60 页批次，仅图像数据就占用约 1.28 GB（640 MB PIL + 640 MB NumPy）。如果 GC 未及时回收上一批次的数据，两批合计将达 2.56 GB，加上模型权重约 4 GB，足以触发 OOM。

### 2.4 补充：模型缓存是设计行为

MinerU 使用 `ModelSingleton` 全局缓存模型实例（Layout、MFD、MFR、OCR、Table 等子模型），在进程生命周期内永不卸载。这是正确的设计——模型加载耗时较长（约 30 秒），不应在请求间反复加载。

问题不在于模型常驻，而在于**临时数据（页面图像、推理中间结果）未被及时回收**。

## 3. 后端 Converter 侧的问题

**位置**：`newbee_notebook/infrastructure/document_processing/converters/mineru_local_converter.py`

当前 Converter 的批循环实现存在两个缺陷：

### 3.1 批次结果引用未释放

```python
for batch_start in range(0, total_pages, self._max_pages_per_batch):
    result = await self._convert_range(...)
    all_markdown.append(result.markdown)
    # ... 合并到 all_images, all_metadata ...
    # result 引用一直保持到下一次循环覆盖
```

`result` 对象包含整批的 ZIP 解压数据、Markdown 文本、图像字节。在被下一次循环覆盖前，上一批次的 `result` 引用持续占用内存。

### 3.2 无本地 GC 调用

Converter 没有在批次间调用 `gc.collect()`，依赖 Python GC 的自动分代回收。在连续调用、大量临时对象的场景下，自动 GC 的回收频率不足以应对每批约 640 MB 的分配量。

## 4. 运行态补充分析（本次新增）

在排查中发现，代码层修复并不等于运行态已经生效。问题还来自以下运行态偏差：

### 4.1 `MINERU_VIRTUAL_VRAM_SIZE` 未真正注入运行进程

虽然 `docker-compose.gpu.yml` 已声明该环境变量，但在容器未重建或进程未重启时，运行中的 `mineru-api` 进程仍可能读取不到该变量。  
结果是 `get_vram(device)` 仍返回真实 16GB，`clean_vram(..., vram_threshold=8)` 继续失效。

### 4.2 Celery 并发远高于 GPU 文档任务可承受范围

运行日志显示 worker 为 `concurrency: 16 (prefork)`。这意味着同一台机器上可同时运行多个文档任务子进程，叠加了：

- 文档转换（大对象分配）
- 本地 embedding（GPU/CPU 占用）
- 索引写入（ES/PG）

即使单文档分批策略正确，高并发仍会放大总内存占用，造成“看似泄漏、实则持续高压”。

### 4.3 单批返回数据体积与元数据取舍

本地 converter 默认请求字段包括：

- `return_md=true`
- `return_images=true`
- `return_content_list=true`
- `return_model_output=true`

`content_list/model_output` 会显著增加响应 ZIP 大小与堆对象数量，但它们在当前项目里并非“纯调试数据”：

- `content_list` 含有图像/表格块位置信息，可作为前端图片渲染兜底来源；
- `model_output` 便于定位 MinerU 分析异常，支撑线上问题复盘。

因此该问题的关键不是“一刀切关闭元数据”，而是：

1. 默认保留元数据，保证可观察性与可恢复能力；
2. 在极端资源压力场景下允许配置关闭，作为降级开关。

## 4. 错误方案回顾：wrapper 脚本注入

前次迭代尝试通过创建 `docker/mineru/mineru_wrapper.py`（一个 FastAPI wrapper 脚本）为 MinerU API 注入 `/cleanup` 端点：

```python
from mineru.cli.fast_api import app  # 导入 MinerU 的 FastAPI app
@app.post("/cleanup")
async def cleanup_memory():
    gc.collect()
    torch.cuda.empty_cache()
    ...
```

然后修改 Dockerfile 的 CMD 使用此 wrapper 替代 `mineru-api` CLI。

**此方案存在以下问题：**

1. **侵入第三方包**：MinerU 是通过 pip 安装的第三方依赖，不应修改其启动入口或注入额外代码。
2. **维护脆弱性**：MinerU 每次升级，FastAPI app 的内部结构可能变化，wrapper 的 import 可能失效。
3. **绕过官方入口**：`mineru-api` CLI 包含必要的初始化逻辑（命令行参数解析、config 注入），wrapper 需要手动复制这些逻辑。
4. **方向错误**：MinerU 已有内置的 `clean_vram()` 清理机制，只是阈值参数不适用于我们的 GPU。正确做法是通过其预留的环境变量接口修正配置，而非绕过整个启动入口。

## 5. 并发概念澄清（便于运维沟通）

“并发”在本问题中不是单一指标，而是三层：

1. `Celery 并发`：同一时刻可执行多少文档任务（文档级并行）。
2. `MinerU API 并发`：同一时刻可接收多少 `file_parse` 请求（服务级并行）。
3. `单文档分批`：同一文档内部分页批次（通常串行，不等于并行）。

排障时必须同时看三层，否则容易只改“批大小”而忽略总并发压力。

## 6. 问题总结

| 层级 | 问题 | 影响 |
|------|------|------|
| MinerU 容器 | `clean_vram()` 阈值 8 GB，16 GB GPU 上永不触发 | 推理阶段间 CUDA 缓存和 IPC 共享张量无法释放 |
| MinerU 容器 | FastAPI 端点无 `gc.collect()` | 页面图像和中间数据在请求返回后惰性回收 |
| MinerU 容器 | PIL + NumPy 双份图像副本 | 单批内存需求翻倍 |
| 后端 Converter | 批次结果引用未显式释放 | 前一批的 ZIP/Markdown/图像数据驻留到下一批覆盖 |
| 后端 Converter | 无本地 GC 调用 | Python 分代 GC 回收频率不足 |
| 部署配置 | 未配置 `MINERU_VIRTUAL_VRAM_SIZE` 环境变量 | MinerU 使用真实 VRAM 大小判断，绕过了清理逻辑 |
| 运行态 | 容器进程未重建，声明配置未生效 | 代码“已修复”但线上行为仍旧 |
| 任务调度 | Celery 并发过高（prefork=16） | 多任务叠加导致内存/显存峰值放大 |
| API 负载 | 元数据返回体积较大（但有业务价值） | 响应体积偏大，需通过并发控制/分批与可配置开关平衡 |
| 前端渲染 | 超长 markdown 一次性同步渲染 | 主线程阻塞，`View` 页面滚动明显卡顿 |
| 前端图片 | 缺少对 `images/...` 相对路径的统一兜底 | 部分文档可能出现图片不展示 |
