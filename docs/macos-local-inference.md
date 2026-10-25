# Mac 本机 MinerU 4 与 Embedding

这套部署让应用继续运行在 Docker 中，让 MinerU 和 Qwen3 Embedding 在 Mac 上使用 Apple GPU。聊天、语音等功能仍调用原来的云端 API。

本文适用于 Apple Silicon Mac。Intel Mac 或暂时不想下载模型的用户，可以使用 [Mac 仅 API 部署](macos-docker.md)。

## 服务在哪运行，权重放在哪里

“模型权重”就是推理时要读取的大文件。程序在容器里运行，并不代表这些文件必须打进镜像；也可以保存在主机目录，再挂载给容器读取。

本项目目前采用以下安排：

| 部署方式 | MinerU 在哪里运行 | MinerU 权重在哪里 |
| --- | --- | --- |
| 现有 Windows / NVIDIA GPU 部署 | `mineru-api` 容器 | 沿用 `mineru:latest` 基础镜像预置的权重；缓存使用 `mineru_cache` 卷 |
| Mac 本机推理 | Mac 上独立的 Python 环境 | 本机项目目录 `models/mineru4/weights/` |
| Mac 仅 API 部署 | MinerU 云端服务 | 本机不需要 MinerU 权重 |

Windows 的 NVIDIA GPU 可以通过 WSL 2 提供给 Linux 容器使用。Mac 的普通 Docker Linux 容器不能用同一套方式直接调用 Apple MPS/Metal，所以这里让模型直接在 macOS 上运行。Docker 的 GPU 直通说明见[官方文档](https://docs.docker.com/desktop/features/gpu/)；MinerU 也[建议 Apple Silicon 使用 macOS 原生安装](https://opendatalab.github.io/MinerU/usage/tiers/)。Docker Model Runner 是另一套推理服务，本项目没有接入它。

Mac 上的 API 和 Celery worker 把解析请求发给 `host.docker.internal:8001`，把 Embedding 请求发给 `host.docker.internal:8002/v1`。这两个服务都在本机运行，只监听 `127.0.0.1`。请求没有因为使用 HTTP 就变成云端调用。

## 项目目录怎么分工

以下路径都相对于项目根目录：

| 路径 | 用途 | 清理建议 |
| --- | --- | --- |
| `models/mineru4/weights/` | MinerU 4 的正式权重，当前约 2.0 GiB | 使用本机 MinerU 时保留 |
| `models/Qwen3-Embedding-0.6B/` | Qwen3 Embedding 的正式权重，当前约 1.1 GiB | 使用本机 Embedding 时保留 |
| `.venv/mineru/`、`.venv/embedding/` | 两个模型服务各自的 Python 依赖 | 保留，避免重复安装 |
| `.tmp/mineru4-server/` | MinerU 收到的文件和解析过程数据 | 停止本机服务后可清理 |

`models/` 用来集中存放下载的模型，当前目录安排可以继续使用。`models/mineru4/weights/` 是正在使用的权重，不能当作测试文件删除。启动脚本按这个路径离线加载模型，删掉后，下次加载模型或重启服务就会失败，需要重新下载。

这些模型和环境已被 `.gitignore`、`.dockerignore` 排除，保存在项目目录里不会让它们进入 Git 提交或应用镜像。Mac 的应用容器无需额外挂载 MinerU 权重。API 对 Qwen3 目录的只读挂载用于在设置页发现模型，实际 Embedding 推理由 Mac 服务完成。

以后如果要把模型放到其他磁盘，可以移动完整目录，但要同时更新下面的下载路径和 `scripts/start_mac_models.sh` 中的路径。只调整目录位置，不需要改动 Windows 部署。

## 版本与硬件

核查日期为 2026-10-25。本次安装固定使用 [MinerU 4.0.12](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.12-released)。本机是 Apple M5 Pro、48 GB 内存、macOS 27.0.1，已验证 MPS 可用，并完成实际解析和 Embedding 推理。其他配置的 Mac 仍需根据内存和文档大小验证。

MinerU 4 要求 Transformers >=5.10.1，现有 Embedding 使用 4.57.1，因此它们各用一个 Python 环境，避免依赖冲突。主应用的 `requirements.txt`、锁文件和 Windows 现有 Torch/Transformers 版本保持不变。

Mac 新服务使用 V1 接口。Windows 现有服务继续使用旧接口，云端 API 也保留。接口变化可参考 [MinerU 4 迁移说明](https://opendatalab.github.io/MinerU/reference/migration_4/)。

## 安装与模型准备

已有完整环境和权重时，直接跳到“启动与切换”。首次安装时，在 Mac 终端进入项目根目录，再执行以下命令；模型下载需要网络。这些命令不在容器里执行。

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

`MINERU_HOME` 是本机 MinerU 的工作目录，`MINERU_MODEL_BASE_DIR` 指向其中的权重目录。下载命令和启动脚本使用相同路径。这两个变量由本机终端或脚本设置；修改项目 `.env` 不会改变当前启动脚本里的路径。MinerU 4 需要对应版本的权重，不能直接拿旧版权重目录替代。

## 启动与切换

一个终端保持原生服务运行：

```sh
bash scripts/start_mac_models.sh
```

脚本会从上述目录离线加载模型：MinerU Standard 使用 Torch/MPS 和 llama.cpp；Embedding 使用 MPS，每批处理 4 条文本。保持这个终端运行。按 Ctrl-C 会停止这两个服务，Docker 应用仍然运行。Mac 重启后，需要重新运行脚本。

另一个终端启动应用：

```sh
docker compose -f docker-compose.yml -f docker-compose.mac.yml -f docker-compose.mac-local.yml up -d --build
curl -f http://127.0.0.1:8001/v1/health
curl -f http://127.0.0.1:8002/health
```

最后一个 Compose 文件负责把 Docker 应用连接到本机模型服务，并启用模型设置页面。它不会在容器中启动 MinerU，也不会下载权重。已有的模型偏好会保留；如有需要，在设置中分别把 MinerU、Embedding 切到“本地”，也可以切回“云端”或“API”。LLM、ASR 等继续使用原来的 API。

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
