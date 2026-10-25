# macOS 适配全面验收记录

日期：2026-10-25（Asia/Taipei）。环境：Apple Silicon 主机，Docker Desktop Linux ARM64，Docker 内存约 8 GB。

## 结论

Mac Docker 主应用与 PDF 知识库问答链路已完成适配并通过实测。不能将此结论扩大为所有外部平台、模型或可选功能均可用。Intel Mac 未在真实硬件上验收；配置没有强制 amd64 模拟。

`requirements.txt`、`pyproject.toml`、MinerU CPU/GPU Dockerfile 中的版本均未修改。运行服务启用 `NEWBEE_API_ONLY=true`，不运行本地模型。安装 CPU Torch 依赖不等于执行本地推理。MarkItDown 的本地 Magika 分类模型也已绕开。

## 自动化验证

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| 后端 unit + contract | 877 passed | 独立容器、断网、API-only；未执行真实模型推理 |
| 前端 Vitest | 59 文件，251 passed | NODE_ENV=test，独立断网容器 |
| TypeScript | 通过 | tsc --noEmit |
| Compose smoke | 12 passed | 包括 Mac 覆盖、监控配置及原 GPU 合并配置 |
| 生产构建 | 通过 | API、worker、frontend、同版源码 MinIO、可选 Flower |
| pip check | 通过 | No broken requirements found |
| git diff --check | 通过 | 未提交代码 |

后端存在 5 条已有依赖警告，包含 Pydantic 配置弃用、TestClient 和 pydub 的 ffmpeg 检测警告。本项目的视频转码实际使用 PyAV；ARM64 音频转码与 ASR 适配器已实测通过，不能据 pydub 警告直接认定视频处理不可用。

## 实际运行验证

| 功能 | 结果与范围 |
| --- | --- |
| 页面 | 笔记本首页和 Library 浏览器渲染正常 |
| PostgreSQL / Redis / ES / MinIO | 数据库 ready、Celery pong、ES green、MinIO 健康及对象读写删除通过 |
| PDF 全链路 | 合成 PDF 上传、关联笔记本、MinerU 云解析、Embedding API、向量索引、检索问答均通过；回答引用测试文档对应 chunk，warnings 为空 |
| 中文与空格文件名 | DOCX、PPTX 直接格式转换通过；另有 TXT/HTML/CSV/XLSX 的自动化实转测试 |
| 百炼聊天 / Embedding | 真实请求通过，Embedding 输出 1024 维 |
| 智谱聊天 | glm-5v-turbo 真实请求通过 |
| Tavily | 一次 basic 搜索返回结果 |
| 百炼图片 | 应用的 qwen_generate_image 适配器返回一张图片 URL；未将其扩大为完整 UI 保存/导出验收 |
| 音频 / ASR | PyAV 转为 16 kHz 单声道；使用官方公开 welcome.mp3 样本，经应用 QwenTranscriber 得到非空中文转写。早先纯音测试无可识别语音，不能用于判定语音模型准确性 |
| 流式聊天 | 应用 SSE 返回 content 和 done，没有 error 事件 |
| 笔记与导出 | 创建中文笔记，重建容器后仍可读取；Markdown 导出和 Notebook ZIP 导出含正确正文 |
| 冷启动 | 新建断网前端容器能够启动并返回页面 HTTP 200；新建断网 API 镜像能初始化 TokenCounter 并计数 |
| Flower | 可选监控镜像启动，页面 HTTP 200，连接内部 Redis，能 ping 到 worker；验收后已停止监控容器 |
| YouTube | 公开视频元数据取得标题；未执行完整下载、字幕/ASR和总结验收 |
| Bilibili | 公开视频元数据请求收到 HTTP 412，平台访问风控导致该项未通过 |

公开音频样本来源：[阿里云官方示例](https://www.alibabacloud.com/help/en/milvus/user-guide/ai-multi-modal-generate)。测试只使用合成内容或官方公开样本；未上传用户私人资料。测试创建的笔记本、文档和关联数据已通过应用接口清理。所有密钥均未写入报告。

## 本轮补充修复

1. 前端运行命令直接调用已安装的 Next.js，不再在首次启动时通过 Corepack 下载 pnpm。
2. 构建阶段缓存 cl100k_base token 词表；运行时不再依赖首次词表下载。此词表用于字符分词计数，不是推理模型。
3. 前后端构建上下文排除 `.env`；API 镜像确认没有 `/app/.env`。
4. 可选 Flower 单独镜像安装固定版本 2.0.1，修正内部 Redis URL。默认 API/worker 不安装 Flower；原 requirements 文件不变。
5. 修正过期测试：permission gateway 参数、PPT 云解析路由预期、测试明确声明本地能力模式，以及 Node/jsdom Blob 混用。未以跳过或删除测试来掩盖失败。

## 剩余限制

- **Shell / Bash 后续已修复**：见下方补充验收。API 现在作为可信调度服务访问 Docker socket；子容器仍与 socket、密钥和其他 Notebook 的数据隔离。
- **B 站 HTTP 412**：当前网络/账号条件下访问受限。需要在应用中完成正常登录并按实际视频重测；不能承诺登录后一定解除风控。
- **完整视频流程**：YouTube 下载、B 站字幕及受限资源、长视频、平台 cookie 状态尚未完成端到端验收。与音频转码/ASR 适配器成功是不同层次的结论。
- **硬件覆盖**：只验证本机 ARM64，不代表 Intel Mac、Windows GPU 或不同 Docker Desktop 资源配置也已实测。
- **规模与复杂文档**：单页 PDF 和基本 Office 样本通过，不代表大批量、复杂公式表格、长时任务、恢复与压力测试已完成。

## 复现测试

```sh
docker run --rm --network none -v "$PWD:/app" \
  -e NEWBEE_API_ONLY=true -e HF_HUB_OFFLINE=1 \
  newbee-notebook/api:latest python -m pytest \
  newbee_notebook/tests/unit newbee_notebook/tests/contract

docker run --rm --network none -e NODE_ENV=test newbee-notebook/frontend:latest \
  sh -c 'unset INTERNAL_API_URL; node node_modules/typescript/bin/tsc --noEmit && node node_modules/vitest/vitest.mjs run'

docker compose -f docker-compose.yml -f docker-compose.mac.yml --profile monitor up -d --build flower
docker compose -f docker-compose.yml -f docker-compose.mac.yml --profile monitor stop flower
```

构建和日常运行见 [Mac Docker 部署指南](macos-docker.md)。

## 2026-10-25 Shell 补充验收

- 历史提交 `8f07402` 修复的是 Windows selector event loop 不支持 asyncio 子进程的问题，该 fallback 仍保留。本次是容器部署缺少 Docker CLI/socket 和宿主 bind 路径映射。
- 补齐 CLI/socket，仅 API 持有 socket；容器部署时使用镜像内工作区、只读技能目录及独立可写工作目录，不挂整个宿主项目。
- 真实 ShellExecutor 执行 `printf` 成功；`/work` 写入、读回成功；命令以 UID 1000 运行，无法看到 socket、`.env`、`configs/mcp.json` 和应用数据目录。
- Chrome 原生电脑操控：Agent 发起 Shell 请求 → 点击“允许本次” → 返回 `MAC_SHELL_FIXED_4827`。没有使用 Playwright。
- Compose smoke：12 passed。沙箱现有测试及新增的冷/热启动挂载、越界拒绝测试通过。
