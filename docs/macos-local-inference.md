# Mac 本机 MinerU 4 与 Embedding

## 版本、硬件与改动边界

核查日期：2026-10-25。官方 GitHub 和 PyPI 的稳定版均为 **MinerU 4.0.12**（不是 0.4.x）。本机为 Apple M5 Pro / 48 GB / macOS 27.0.1 / ARM64，约 495 GiB 可用磁盘。MPS 可用且实际张量计算通过。

- [官方版本](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.12-released)
- [平台与运行时](https://opendatalab.github.io/MinerU/usage/tiers/)
- [3.x → 4.x 迁移](https://opendatalab.github.io/MinerU/reference/migration_4/)

Docker Desktop 的 Linux 容器不能直接使用 Apple MPS/Metal。应用、数据库和队列继续运行在 Docker；MinerU 和 Qwen3-Embedding 原生运行在 Mac，只监听 `127.0.0.1`。容器通过 `host.docker.internal` 调用它们。

MinerU 4 要求 Transformers >=5.10.1，而现有 Embedding 使用 4.57.1，所以保留两个独立 Python 环境。`requirements.txt`、主应用锁文件和 Windows 现有 Torch/Transformers 版本不变；新解析服务固定为下方安装命令中的 4.0.12。Embedding 服务与 Windows 本地路径共用模型加载、归一化、维度截取实现。

新 V1 协议显式启用；默认仍为旧协议，旧 Windows/GPU Compose 与云 API 不变。没有引入服务注册、自动下载代理或额外调度框架。

## 安装与模型准备

在项目根目录执行（首次下载模型需要网络）：

```sh
uv venv --python 3.12 .venv/mineru
uv pip install --python .venv/mineru/bin/python "mineru[torch]==4.0.12"
uv venv --python 3.11 .venv/embedding
uv pip install --python .venv/embedding/bin/python \
  "torch==2.9.0" "transformers==4.57.1" "sentence-transformers==5.1.1" \
  "numpy==2.2.6" "fastapi==0.128.0" "pydantic==2.12.3" "uvicorn==0.40.0"

export MINERU_HOME="$PWD/models/mineru4"
export MINERU_MODEL_BASE_DIR="$MINERU_HOME/weights"
.venv/mineru/bin/mineru-kit models download --tier standard --small-backend torch --vlm-engine llama-cpp --source huggingface
.venv/mineru/bin/mineru-kit models verify --tier standard --small-backend torch --vlm-engine llama-cpp
.venv/embedding/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("Qwen/Qwen3-Embedding-0.6B", local_dir="models/Qwen3-Embedding-0.6B", ignore_patterns=["onnx/*", "*.gguf"])'
```

本机下载结果：MinerU 权重约 2.0 GiB，Qwen3-Embedding-0.6B 约 1.1 GiB，另有环境和下载缓存占用。模型与虚拟环境不提交、不打入应用镜像。不要用旧 MinerU 3 模型目录代替 4.x 权重。

## 启动与切换

一个终端保持原生服务运行：

```sh
bash scripts/start_mac_models.sh
```

脚本离线加载已下载的模型：MinerU Standard 使用 Torch/MPS 小模型及 llama.cpp VLM；Embedding 使用 MPS，推理 batch 为 4。Ctrl-C 仅停止脚本启动的两个服务，不停止 Docker 或其他进程。

另一个终端启动应用：

```sh
docker compose -f docker-compose.yml -f docker-compose.mac.yml -f docker-compose.mac-local.yml up -d --build
curl -f http://127.0.0.1:8001/v1/health
curl -f http://127.0.0.1:8002/health
```

这个可选 Compose 覆盖文件会启用模型设置页面。应用保留数据库中已保存的偏好。在模型设置中分别切换 MinerU、Embedding 到 Local；也可以分别切回 Cloud/API。LLM、ASR 等原有 API 不受影响。API 对模型目录的只读挂载用于模型发现，Embedding 计算由原生服务完成。

云端 text-embedding-v4 与本地 Qwen3-Embedding-0.6B 即使同为 1024 维，也不能混用向量。新增原生服务的 Local 模式使用带 `_qwen3_local` 后缀的 PostgreSQL 表和 Elasticsearch 索引；API 模式继续使用原索引。首次切换需重新为需要检索的已有文档建立本地索引；不会自动重建、覆盖或删除用户已有索引。本地服务配置启用时，删除文档会清理两个命名空间中的节点。

只使用原来的 Mac API 链路：去掉最后一个 Compose 覆盖文件重新启动；`NEWBEE_API_ONLY=true` 会约束实际运行模式，保留已保存偏好。跨模式新增、修改或删除文档后，重新使用另一模式前应重建其索引，保证与当前文档一致。

## MinerU 4 接口区别

- `MINERU_LOCAL_API_VERSION=v1`：`/v1/file_parse`，解析参数放 query，分页为 1-based `page_range`；超过同步等待窗口后轮询同一个 task。旧 Windows 服务默认 `legacy`，继续 `/file_parse` 和原 form 参数。
- `MINERU_LOCAL_TIER=standard`：PDF/图片默认 Standard；DOCX/PPTX/XLSX 按官方要求使用 Flash，整文档解析。
- ZIP 保留 Markdown、图片、`middle_json.json`、`structured_content.json` 等原始元数据；页数读取新版 `pages`，不伪造旧版布局格式。
- 旧版 `backend`、语言列表、formula/table 开关不是 V1 的参数，不会发给新版服务。新版档位控制解析能力。
- 旧版自定义“标题辅助识别”补丁不适用于 MinerU 4；V1 部署不显示该开关，不覆写已保存的旧偏好。Windows 旧接口仍保留原行为。
- 未配置新的本地 Embedding URL 时，Windows 原有进程内 CPU/CUDA 推理保持原路径；自动设备选择优先 CUDA，其次 MPS，再 CPU。

## Windows 后续验收

现有 GPU Compose 依赖旧版 `mineru-api` 和标题辅助补丁，继续使用已验证的旧镜像；不要把 MinerU 4 的镜像直接覆盖到它的 `mineru:latest`。升级服务可在独立环境运行 `mineru-kit api-server --host 127.0.0.1 --port 8001 --tier standard --upload-dir .tmp/mineru4-server`，应用设置 `MINERU_LOCAL_API_VERSION=v1` 和对应地址。Python 安装命令在 PowerShell 中将 `bin/python` 换成 `Scripts/python.exe`；CUDA Torch 的安装按官方平台说明选择。

新版客户端和共享 Embedding 代码使用平台无关路径。Windows 原生运行、CUDA 驱动与模型推理仍需在 Windows 真机验收；Mac 的结果不替代这些测试。

## 验收记录

本机离线权重模式通过：两页合成 PDF Standard 解析（首次约 17.3 秒，2 页）、DOCX Flash 解析（约 0.53 秒，1 页），均由 Docker 内应用适配器调用原生服务。Embedding 通过 Docker 调用，得到 3×1024 的有限、单位长度向量，正确检索出蓝色笔记本价格段落。时间仅描述测试样本，不是性能承诺。

- 扫描图片 OCR 识别出测试编号与数字；带图 PDF 返回可引用的图片资产。分批解析图片重名的回归测试覆盖 legacy / V1，合并 Markdown 与 HTML 图片链接会随资产重命名。
- 完整应用链路：上传合成 PDF → 加入 Notebook → Celery 调用本机解析和 Embedding → 两页、两条分块完成 → Ask 返回“42 美元”和对应文档来源。浏览器确认文档可读、回答可见；通过电脑操控和应用接口验收，未使用 Playwright。
- 原 API 路径：DashScope Embedding 实际返回 1024 维有限向量，聊天 LLM API 正常。模型设置可切换 Local / API；V1 隐藏不支持的标题辅助开关。当前未配置 MinerU 云端密钥，其解析只完成兼容性回归，未进行真实云端解析。
- 后端 unit + contract：正常环境与 `NEWBEE_API_ONLY=true` 环境各 **901 passed**；前端 TypeScript 检查和 **252 项测试**通过；Mac 原生/API-only 与 Windows GPU Compose 合并检查共 **15 passed**。现有 5 条依赖弃用或可选 ffmpeg 警告不影响这些结果。
- 两个原生 Python 环境依赖检查通过；API、worker、前端镜像构建成功，容器健康。Windows 真机/CUDA 推理留待 Windows 验收。
- 删除测试 Notebook、会话与文档后，文档和 Notebook 接口均返回 404；原 API 表、本地表及 ES 中该测试文档节点均为 0，对象存储中的文档文件为 0。测试样本和 MinerU 上传目录已清理，临时模式切换已恢复为启动环境默认值。
- 保留下载的模型与原生环境供后续使用；不提交模型、环境、日志、样本、`blobs/` 或额外的 `requirements-embedding.txt` / `requirements-mineru.txt`。原生服务启动器将运行数据限制在已忽略的 `.tmp/mineru4-server/`。
