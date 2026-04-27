# 02 · Docker 基础设施变更

本文涵盖 Docker 层的三项变更：GPU 镜像升级、CPU 镜像同步升级、`docker-compose.gpu.yml` healthcheck 修复。

Docker 层变更是整个 improve-1 的前置依赖 —— 本地转换器的新参数只有在新版 MinerU 容器中才能生效。

---

## 变更 1 · Dockerfile.gpu 升级

### 目标文件

[docker/mineru/Dockerfile.gpu](../../../docker/mineru/Dockerfile.gpu)

### 变更 diff

```diff
  # RTX 5060 Ti (Blackwell, Compute Capability >= 10.0) requires vllm v0.11.0
  # vllm v0.10.x only supports CC 8.0-9.0 (Ampere / Ada Lovelace / Hopper)
- # vllm v0.11.0 supports CC 7.0-7.9 (Volta/Turing) AND CC >= 10.0 (Blackwell)
+ # vllm v0.11.2 supports CC 7.0-7.9 (Volta/Turing) AND CC >= 10.0 (Blackwell)
+ # v0.11.2 fixes several Blackwell scheduling issues present in v0.11.0.
  # DaoCloud mirror for China-region pull acceleration
- FROM docker.m.daocloud.io/vllm/vllm-openai:v0.11.0
+ FROM docker.m.daocloud.io/vllm/vllm-openai:v0.11.2

  # Install libgl for opencv support & Noto fonts for Chinese characters
  RUN apt-get update && \
      apt-get install -y --no-install-recommends \
          curl \
          fonts-noto-core \
          fonts-noto-cjk \
          fontconfig \
          libgl1 && \
      fc-cache -fv && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/*

- # Install MinerU (GPU runtime is provided by the vllm base image)
+ # Install MinerU 3.0+ (GPU runtime is provided by the vllm base image).
+ # 3.0 rewrote the VLM inference engine to async (aio_do_parse), so new
+ # hybrid-auto-engine improvements are gated on this major version.
  # Use Aliyun PyPI mirror for faster installs in China
- RUN python3 -m pip install -U --no-cache-dir 'mineru[core]>=2.7.0' \
+ RUN python3 -m pip install -U --no-cache-dir 'mineru[core]>=3.0.0' \
          -i https://mirrors.aliyun.com/pypi/simple \
          --break-system-packages && \
      python3 -m pip cache purge
```

### 官方依据

- `mineru/docker/global/Dockerfile` 第 4 行：`FROM vllm/vllm-openai:v0.11.2`
- `mineru/docker/global/Dockerfile` 第 18 行：`RUN python3 -m pip install -U 'mineru[core]>=3.0.0' --break-system-packages`
- `mineru/pyproject.toml` 第 84 行：`vllm>=0.10.1.1,<0.12`（确认 vLLM 0.11.2 在 mineru 3.0 支持范围内）
- `mineru/mineru/cli/fast_api.py` 第 1012-1015 行：
  ```python
  if request_options.backend == "pipeline":
      await asyncio.to_thread(do_parse, **parse_kwargs)
  else:
      await aio_do_parse(**parse_kwargs)
  ```
  这段代码证明 3.0 里非 pipeline backend（包括 `hybrid-auto-engine`）走的是 async 版本 `aio_do_parse`，旧版 2.7 的同步路径已废弃。

### 升级影响

1. **模型缓存会重新下载**：vLLM 升级后 CUDA kernel 缓存失效，MinerU 升级后模型权重格式可能有微调；首次启动容器需要 5-15 分钟（取决于网络）。由于 compose 挂载了 `mineru_cache:/root/.cache`，后续重启不受影响。
2. **基础镜像体积增加约 200 MB**（vLLM 0.11.2 带了新的 Blackwell kernel）。
3. **API 行为默认不变**：同步端点 `POST /file_parse` 行为与 2.7 一致；新增的 `POST /tasks` 异步端点本轮不接入。

---

## 变更 2 · Dockerfile.cpu 同步升级

### 目标文件

[docker/mineru/Dockerfile.cpu](../../../docker/mineru/Dockerfile.cpu)

### 变更 diff

```diff
  FROM python:3.11-slim

  ENV PYTHONDONTWRITEBYTECODE=1 \
      PYTHONUNBUFFERED=1 \
      PIP_DISABLE_PIP_VERSION_CHECK=1

  # System deps:
  # - libgl1/libglib2.0-0: OpenCV runtime
  # - fonts-noto-*: Chinese/Japanese/Korean rendering in some PDF/image paths
  # - curl: optional healthcheck/debug
  RUN apt-get update && \
      apt-get install -y --no-install-recommends \
          curl \
          fontconfig \
          fonts-noto-core \
          fonts-noto-cjk \
          libgl1 \
          libglib2.0-0 \
          libgomp1 && \
      fc-cache -fv && \
      rm -rf /var/lib/apt/lists/*

  # Install CPU-only PyTorch first so pip won't pull in CUDA/cuDNN (saves ~700MB+ and avoids long "stuck" downloads)
  RUN python -m pip install -U --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
- # CPU pipeline + FastAPI server (no GPU required)
- RUN python -m pip install -U --no-cache-dir "mineru[api,pipeline]>=2.7.0"
+ # CPU pipeline + FastAPI server (no GPU required). Upgrade to 3.0+ to keep
+ # GPU/CPU major-version parity; pipeline backend internals in 3.0 have minor
+ # refactors but the API surface (/file_parse form fields) is backward compatible.
+ RUN python -m pip install -U --no-cache-dir "mineru[api,pipeline]>=3.0.0"

  # Pre-download models during build to avoid first-request delay (~3min download + ~2min init)
  # Models are downloaded to /root/.cache/modelscope which should be mounted as a volume for persistence
  ENV MINERU_MODEL_SOURCE=modelscope
  RUN python -c "\
  from mineru.backend.pipeline.model_init import DocAnalysis; \
  print('Pre-downloading MinerU models...'); \
  _ = DocAnalysis(device_mode='cpu'); \
  print('Model download complete!')" || echo "Model pre-download skipped (will download on first use)"
```

### 官方依据

- `mineru/pyproject.toml` 第 92-104 行：`pipeline` optional 依赖组包含 `torch>=2.6.0,<3` + `transformers>=4.57.3,<5.0.0` + `onnxruntime>1.17.0`；3.0 与 2.7 的 CPU pipeline 依赖范围一致，主要差异在内部模型加载流程。
- `mineru/mineru/backend/pipeline/model_init.py` 中的 `DocAnalysis` 在 3.0 仍然保留，但初始化流程有调整 —— 这也是 Dockerfile 里预下载模型的代码后面跟了 `|| echo "... skipped"` 的原因：即使 3.0 接口小变化，也不会阻塞镜像构建，首次请求时会自动补下载。

### 升级风险

CPU pipeline 的风险评估：

- **API 表面（`/file_parse` 的 form fields）完全向后兼容**：新增的 `parse_method`、`formula_enable`、`table_enable` 都是新参数，不传就用默认值；老的 `backend`、`lang_list` 等行为不变。
- **内部模型加载变化**：3.0 的 `DocAnalysis(device_mode='cpu')` 构造签名未变，但内部有重构（模型注册表调整）。构建时用了 `|| echo "... skipped"` 做兜底，即使预下载失败，首次请求时模型会自动下载。
- **建议在升级后跑一次 smoke test**：用已知样本 PDF 跑一次，确认 markdown 输出结构与图片资产符合预期。

如果 CPU 镜像升级测试失败：

- **回滚策略**：在 `Dockerfile.cpu` 单独改回 `>=2.7.0`，GPU 镜像保持 3.0；短期可以接受 GPU/CPU 版本分叉，但需要在 issue 里记录后续再做 CPU 升级。

---

## 变更 3 · docker-compose.gpu.yml healthcheck 修复

### 目标文件

[docker-compose.gpu.yml](../../../docker-compose.gpu.yml)

### 变更 diff

```diff
  mineru-api:
    build:
      context: ./docker/mineru
      dockerfile: Dockerfile.gpu
    image: newbee-notebook/mineru-api:gpu
    container_name: newbee-notebook-mineru-api
    restart: unless-stopped
    environment:
      MINERU_MODEL_SOURCE: modelscope
      MINERU_DEVICE_MODE: cuda
      MINERU_API_ENABLE_FASTAPI_DOCS: ${MINERU_API_ENABLE_FASTAPI_DOCS:-1}
      MINERU_API_MAX_CONCURRENT_REQUESTS: ${MINERU_API_MAX_CONCURRENT_REQUESTS:-1}
      # Limit PDF rendering parallelism to reduce peak memory usage.
      MINERU_PDF_RENDER_THREADS: "1"
      # Force clean_vram() to trigger after each inference stage.
      MINERU_VIRTUAL_VRAM_SIZE: "8"
    volumes:
      - mineru_cache:/root/.cache
    ports:
      - "8001:8000"
    networks:
      - newbee_notebook_network
    healthcheck:
-     test: ["CMD-SHELL", "curl -f http://localhost:8000/docs >/dev/null 2>&1 || exit 1"]
+     test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 10
```

### 官方依据

- `mineru/mineru/cli/fast_api.py` 第 1498-1538 行：`@app.get(path="/health")` 定义，返回 `{"status": "healthy", "queued_tasks": N, ...}`。
- `mineru/docker/compose.yaml` 第 21 行（openai-server）、第 50 行（api）、第 85 行（router）：官方 compose 对所有 MinerU 服务的 healthcheck 都使用 `/health`。

### 为什么必须修改

当前 healthcheck 使用 `/docs`：

1. **语义错误**：`/docs` 是 FastAPI 自动生成的 Swagger UI 页面，不是健康检查端点；它的可用性不等于服务的可用性（例如 API 能响应文档页但实际 worker 已挂掉）。
2. **环境依赖**：当 `MINERU_API_ENABLE_FASTAPI_DOCS=0` 时，`/docs` 返回 404，healthcheck 永远失败 → 容器标记为 unhealthy → compose 的依赖（例如 `depends_on: condition: service_healthy`）会一直阻塞。
3. **新版有更好的选择**：`/health` 端点不仅能反映服务存活，还返回了任务队列状态（`queued_tasks` / `processing_tasks`），便于后续监控集成。

### 升级影响

- 无 breaking change，旧 `/docs` 在 `MINERU_API_ENABLE_FASTAPI_DOCS=1` 时仍然可用（不影响开发者手动访问 Swagger UI）。
- 生产环境如果已经开始关闭 `MINERU_API_ENABLE_FASTAPI_DOCS` 以减少攻击面，升级后 healthcheck 能正常工作。

---

## 验收方式

Docker 层变更的验收步骤（详细版本见 [06-implementation-steps.md](./06-implementation-steps.md)）：

```bash
# 1. 从头构建 GPU 镜像（清除旧缓存）
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build --no-cache mineru-api

# 2. 启动并观察容器状态
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d mineru-api

# 3. 等待 healthcheck 通过（首次启动可能 5-10 分钟，因为要下载模型）
docker compose ps mineru-api
# 期望状态列：Up (healthy)

# 4. 手动验证 /health 端点
docker exec newbee-notebook-mineru-api curl -s http://localhost:8000/health
# 期望返回：{"status": "healthy", "version": "3.x.x", ...}

# 5. 跑一次 smoke test（用一份 <10 页的样本 PDF）
curl -X POST http://localhost:8001/file_parse \
     -F "files=@samples/test.pdf" \
     -F "backend=hybrid-auto-engine" \
     -F "return_md=true" \
     -F "response_format_zip=true" \
     --output /tmp/mineru-smoke.zip

# 6. 验证 ZIP 结构（关键！确认两层嵌套的新结构）
unzip -l /tmp/mineru-smoke.zip
# 期望：{pdf_name}/{backend_dir_name}/{pdf_name}.md 这种路径
```

### 常见失败场景

| 症状 | 可能原因 | 处理 |
|---|---|---|
| `/health` 返回 503 | MinerU task manager 未完成初始化（模型未下载完） | 等 5-10 分钟；或 `docker logs` 看是否有下载报错 |
| `docker compose ps` 一直 unhealthy | healthcheck 时间窗口太短 | 确认 `interval: 30s, retries: 10` 保留；共 5 分钟上限 |
| 构建阶段 `pip install mineru` OOM | Docker 构建内存不够 | 增加 Docker Desktop 内存到 8GB+；或分层构建 |
| GPU 容器启动报 `CUDA error: no kernel image` | vLLM 镜像与本地驱动不匹配 | 确认 host NVIDIA driver >= 550（支持 CUDA 12.8） |
