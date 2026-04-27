<div align="center">

<img src="assets/pic/logo.png" alt="Newbee Notebook" width="120">

# 🐝Newbee Notebook

**AI-Powered Interactive Document Reader**

AI-driven interactive document reader. High-accuracy content parsing & retrieval, Agent notes & diagrams, Bilibili video summarization — self-hosted, your data stays yours.

Read, search, and interact with your documents through AI agents — self-hosted, private, extensible.

[Quick Start](#quick-start) · [Detailed Config](quickstart.md) · [Features](#core-features) · [中文](README.md)

[![License](https://img.shields.io/github/license/diverHansun/newbee-notebook)](LICENSE.md)
[![GitHub Stars](https://img.shields.io/github/stars/diverHansun/newbee-notebook?style=social)](https://github.com/diverHansun/newbee-notebook/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/diverHansun/newbee-notebook)](https://github.com/diverHansun/newbee-notebook/issues)

</div>

---

## Preview

<div align="center">
  <a href="https://github.com/user-attachments/assets/ec24276f-4adf-4986-98fc-8fadb01867f5">
    <img src="assets/screenshots/markdown-viewer.png" alt="Newbee Notebook Demo Video" width="720">
  </a>
  <p><em>video</em></p>
  <p><a href="https://github.com/user-attachments/assets/250fcf42-a863-4a92-8e30-2693cd2da6e3">Watch Demo Video</a></p>
</div>

<div align="center">
  <img src="assets/screenshots/notebook-dashboard.png" alt="Notebook Dashboard" width="720">
  <p><em>Notebook Dashboard — Create and manage your knowledge spaces</em></p>
</div>

<div align="center">
  <img src="assets/screenshots/markdown-viewer.png" alt="Interactive Document Reading" width="720">
  <p><em>Interactive Document Reading — Source panel on the left, Markdown rendering in the center, Studio panel on the right</em></p>
</div>

<details>
<summary>More Screenshots</summary>
<br>

<div align="center">
  <img src="assets/screenshots/AI.png" alt="AI Agent Chat" width="720">
  <p><em>AI Agent Chat — Intelligent Q&A with citation tracing based on document content</em></p>
</div>

<div align="center">
  <img src="assets/screenshots/diagram-display.png" alt="Agent Diagram Generation" width="480">
  <p><em>Agent Diagram Generation — /diagram automatically creates knowledge graphs and mind maps</em></p>
</div>

<div align="center">
  <img src="assets/screenshots/video-summary.png" alt="Bilibili Video Summarization" width="480">
  <p><em>Bilibili Video Summarization — Video transcription and structured summaries</em></p>
</div>

</details>

---

## Core Features

**Interactive Document Reading** — Not just reading documents, but conversing with them. Select any paragraph to trigger Conclude or Explain on the spot, resolving questions as you read. The bookmark system helps you mark and revisit important content so you never lose an insight.

**High-Accuracy Document Parsing & Retrieval** — High-fidelity PDF parsing powered by [MinerU](https://github.com/opendatalab/MinerU), accurately restoring tables, formulas, and multi-column layouts to Markdown, handling files hundreds of pages long with ease. Hybrid vector and full-text retrieval (pgvector + Elasticsearch) work together, with citation tracing precise to the original paragraph — find exactly what you're looking for.

**Agent Notes, Diagrams & Video** — Type `/note` to let the Agent organize your notes, and `/diagram` to automatically generate mind maps and knowledge graphs. Supports Bilibili and YouTube video transcription and intelligent summarization, quickly extracting key information from video content. Chat supports image generation, with AI-created images displayed inline in the conversation. Notes and video summaries can be exported to Markdown in one click. Agents aren't a gimmick — they're a genuine tool for extracting structured knowledge from your documents.

**Configurable MCP Toolchain** — Through MCP (Model Context Protocol) and the Skills system, you can freely extend the Agent's capability boundaries. Need to connect external tools and services? Configure it yourself.

**Self-Hosted, Privacy First** — Fully local deployment with no dependency on any third-party cloud services to store your data. Documents and conversations stay entirely on your own server — no data reporting, no usage tracking. Open source and free (AGPL-3.0). All you need is your own API Key.

---

## Comparison

| Feature | Google NotebookLM | Open Notebook | Newbee Notebook |
|---|:---:|:---:|:---:|
| Open Source | - | MIT | AGPL-3.0 |
| Self-Hosted | - | ✓ | ✓ |
| Data Privacy | Cloud Storage | Local | Local |
| Document Parsing | Black Box | Basic Parsing | MinerU High-Accuracy |
| Interactive Reading (Conclude / Explain) | Limited | - | ✓ Select to Trigger |
| Bookmark System | - | - | ✓ |
| Agent Notes / Diagrams | - | Transformations | /note · /diagram |
| Video Summarization | YouTube | - | Bilibili + YouTube |
| Retrieval Method | Black Box | Vector Search | Hybrid Search + Citation Tracing |
| Large File Support | Limited | Limited | MinerU chunking, hundreds of pages |
| LLM Choice | Gemini only | Multi-model | Configurable (Zhipu / Qwen, etc.) |
| Extension Mechanism | Closed | Plugins | MCP + Skills |

---

## Quick Start

Three steps to get started. For advanced configuration (GPU mode, MinIO storage, local Embedding, etc.) see [quickstart.md](quickstart.md).

### 1. Configure Environment Variables

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux / Git Bash:

```bash
cp .env.example .env
```

Edit `.env` and fill in the required API Keys:

```bash
# LLM Services (recommended to fill in both)
# Zhipu AI — Get key at: https://open.bigmodel.cn/
ZHIPU_API_KEY=your_key_here

# Qwen (Tongyi) — Get key at: https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=your_key_here

# Enable LLM / Embedding / MinerU switching in the frontend settings panel / API
FEATURE_MODEL_SWITCH=true

# Database password
POSTGRES_PASSWORD=your_password

# PDF parsing (default Docker mode uses cloud MinerU)
# MinerU API Key — Get key at: https://mineru.net/apiManage/token
MINERU_MODE=cloud
MINERU_API_KEY=your_mineru_key
```

### 2. Choose a Startup Mode

Choose the appropriate mode based on your hardware:

> You can use the app without a dedicated GPU — just choose the "Default Docker Mode".
> "CPU-Only Full Local" specifically means running both MinerU and Embedding on the host CPU, which is different from the default Docker mode.

| Common Device | Recommended Mode | Command |
|---|---|---|
| Windows / macOS / Linux laptop or desktop (no dedicated GPU, integrated GPU only) | **Default Docker Mode** | `docker compose up -d` |
| Apple Silicon Mac / Intel Mac | **Default Docker Mode** | `docker compose up -d` |
| AMD / Intel GPU devices | **Default Docker Mode** | `docker compose up -d` |
| NVIDIA GPU, VRAM ≥ 8GB, RAM ≥ 32GB | **GPU Local Enhanced Mode** | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` |

| Mode | Hardware Requirements | Command |
|---|---|---|
| **Default Docker Mode** (recommended) | No special requirements | `docker compose up -d` |
| **GPU Local Enhanced Mode** | NVIDIA GPU, VRAM ≥ 8GB, RAM ≥ 32GB | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` |
| **CPU-Only Full Local** (not recommended) | No dedicated GPU, RAM ≥ 32GB | No official one-click Compose provided; extend manually |

**Default Docker Mode** (simplest, works out of the box):

```bash
docker compose up -d
```

The first launch will automatically build the frontend, API, and Celery Worker images and install Python dependencies during the build phase — please be patient. Default Docker Mode installs the CPU version of torch for the API / Worker so that subsequent restarts of `celery-worker` don't repeat `pip install`. This mode uses `MinIO + cloud MinerU + API Embedding` by default and does not start a local `mineru-api` container.

This mode works for most devices, including Windows / macOS / Linux machines without a GPU, machines with integrated graphics only, Apple Silicon, and AMD / Intel GPU devices that currently lack an official GPU override config.

If you need to adjust the CPU torch version in Default Docker Mode, set `PYTHON_RUNTIME_TORCH_VERSION` in `.env` and re-run `docker compose up -d --build`.

If you have an NVIDIA GPU (VRAM ≥ 8GB, system RAM ≥ 32GB), you can switch to GPU Local Enhanced Mode to run both MinerU and Embedding on the local GPU. You'll need to download the Embedding model first — see [quickstart.md — GPU Local Mode](quickstart.md#mode-2-gpu-local-enhanced-mode-nvidia-vram--8gb-system-ram--32gb).

If you're using Apple Silicon, an AMD GPU, or an Intel GPU, the repository currently doesn't provide Metal / ROCm / oneAPI local acceleration override configs — continue using Default Docker Mode.

If you're using an NVIDIA GPU, avoid changing `torch==x.y.z` directly; instead set `CELERY_WORKER_BASE_IMAGE` in `.env` to a `pytorch/pytorch` image tag that matches your driver, then run the GPU mode `--build` startup command.

### 3. Start Using

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/docs |

> Having issues? See the FAQ section in [quickstart.md](quickstart.md).

---

## Documentation

| Document | Description |
|---|---|
| [quickstart.md](quickstart.md) | Complete installation and configuration guide, including GPU mode, MinIO storage, and other advanced options |
| [API Docs](http://localhost:8000/docs) | Swagger UI, accessible after starting the service |
| [docs/](docs/) | Architecture design and technical documentation |

---

## Roadmap

- [ ] Skill mechanism extensions
- [ ] Add ECharts chart support
- [ ] New features for the Studio module

Have an idea? Feel free to share it via [Issues](https://github.com/diverHansun/newbee-notebook/issues).

---

## Acknowledgements

The PDF document parsing capability of this project is powered by [MinerU](https://github.com/opendatalab/MinerU). Thanks to the [OpenDataLab](https://github.com/opendatalab) team for their excellent work.

## Contributing

Issues and Pull Requests are welcome.

## Official WeChat Group

You are welcome to join the official WeChat group for release updates, community discussion, and support.

<img src="assets/screenshots/weixin.png" alt="Official WeChat Group QR Code" width="320" />

## License

[AGPL-3.0](LICENSE.md)

---

