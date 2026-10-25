# macOS Docker 部署（仅 API 模型）

支持 Apple Silicon 和 Intel Mac，使用 Docker Desktop Linux 容器。保留 requirements.txt、pyproject.toml 和 MinerU Dockerfile 的既有版本。镜像仍安装原 requirements 的 CPU Torch 等依赖，但不运行本地模型。

## 启动

Docker Desktop 建议至少分配 8 GB 内存，并预留首次构建磁盘空间。Docker Compose 需 >= 2.24.4（覆盖配置使用 `!override` 合并端口）。

在项目根目录创建 `.env`；已有文件时不要覆盖：

```sh
cp .env.example .env
chmod 600 .env
```

填写 `.env`：

```dotenv
DASHSCOPE_API_KEY=你的百炼密钥
MINERU_API_KEY=你的MinerU密钥
MINERU_MODE=cloud
QWEN3_EMBEDDING_MODE=api
```

默认聊天使用 `qwen3.5-plus`，Embedding 使用 `text-embedding-v4`（1024 维）；确保账号有对应权限。语音等功能也复用百炼 API。智谱、Tavily 为相应功能的可选密钥。没有密钥可以启动基础服务，但不能验证模型功能。切换 Embedding 模型后，旧向量索引可能需要重建。

```sh
docker compose -f docker-compose.yml -f docker-compose.mac.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.mac.yml ps
```

- 应用：http://localhost:3000
- API：http://localhost:8000/api/v1/health
- MinIO 控制台：http://localhost:9001

服务仅监听 `127.0.0.1`。浏览器通过 `localhost:9000` 访问 MinIO，容器间使用 `minio:9000`。不要叠加 `docker-compose.gpu.yml`。

修改密钥后重新执行 `up -d`，仅 `restart` 不会更新环境变量。代码修改后使用 `up -d --build`。API 的 `data`、`configs` 挂载到主机，数据库和对象存储使用命名卷。

## 仅 API 约束

Mac 配置设置 `NEWBEE_API_ONLY=true`。数据库继承 Windows/GPU 机器的本地 Embedding/MinerU 偏好时，实际运行选择 API/cloud，不改写原偏好。Windows/GPU 配置不启用此约束。不会启动 `mineru-api` 或下载模型权重；不要在 Mac 手动调用模型下载脚本。

MarkItDown 默认的 Magika 文件类型识别也使用本地模型，Mac 模式改为按扩展名调用其格式转换器。TXT/Markdown、HTML、CSV、PDF 文本提取、DOCX、XLS/XLSX、PPTX、EPUB 解析不需要模型；旧 `.doc`/`.ppt` 依赖 MinerU 云解析；本地无模型兜底不支持时需先转为 DOCX/PPTX。OCR 与语义理解仍通过云端 API。

## MinIO 镜像来源

原官方 Docker Hub 镜像、Quay 镜像和二进制下载在此次部署时不可公开获取。Mac 配置从同一发行版 `RELEASE.2025-09-07T16-13-09Z` 的官方 Git 对象 `01ce918d8279a20e4706b96a64396146894adee4` 构建，指向源码提交 `07c3a429bfed433e49018cb0f78a52145d4bedeb`。未换用第三方镜像。首次构建需要访问 GitHub 和 Go 模块服务。源码与许可证：[minio/minio](https://github.com/minio/minio)。

## 检查与停止

```sh
curl -f http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/health/ready
curl -f http://localhost:9200/_cluster/health
docker compose -f docker-compose.yml -f docker-compose.mac.yml logs --tail=100 api celery-worker
docker compose -f docker-compose.yml -f docker-compose.mac.yml stop
```

`health/ready` 当前只检查 PostgreSQL，不代表模型 API、Redis 或 Elasticsearch 已验证。完整验收还需上传 PDF 验证 MinerU、Embedding 入库，再执行检索和聊天。停止时保留卷，不使用 `down -v` 或全局 Docker 清理命令。

## 应用内 Shell / Bash

Mac Compose 为 API 挂载 `/var/run/docker.sock`，API 镜像包含官方 Docker CLI。
API 是可信的容器调度进程，持有 Docker 控制权限；因此服务继续只监听本机，不能作为无鉴权的公网服务部署。
沙箱子容器不挂载 socket，不接收 API 密钥，以 UID 1000 执行命令，保留只读根文件系统、资源限制和现有独立网络限制。

请在项目根目录执行 Compose 命令。`NEWBEE_SANDBOX_HOST_PROJECT_ROOT` 默认取 `$PWD`，用于把 API 内部 `/app/data/sandbox/...` 映射到 Mac 上的真实目录；若从其他目录启动，必须显式设置该变量为项目绝对路径。
子容器使用镜像内的代码，只读挂载 `configs/skills`，仅本 Notebook 的工作目录挂载为可写 `/work`。
不会把宿主整个项目（包括 `.env`）或其他 Notebook 数据挂进去。代码修改仍需重建镜像；技能文件无需重建。
原生 Windows/Linux 后端不设置此变量，继续使用原有路径和执行方式。

基础 Compose 为 API 挂载 `./configs:/app/configs`，Mac 与 Windows/GPU 部署均从宿主读取运行配置。MCP 配置 `configs/mcp/mcp.json` 和旧 Bilibili 凭据不打入镜像；请在宿主配置目录保存。

这是 Docker 部署的路径要求：bind mount 的源由 daemon 所在主机解析，而不是由调用 CLI 的容器解析，见 [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)。
Docker socket 的控制权限边界见 [Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)。

可选监控：`docker compose -f docker-compose.yml -f docker-compose.mac.yml --profile monitor up -d --build flower`，访问 http://localhost:5555。Flower 使用独立镜像，默认不启动。

扩大后的测试结果与剩余限制见 [全面验收记录](macos-verification.md)。

## 本机验收（2026-10-25）

- Apple Silicon / Linux ARM64：前后端镜像构建成功，七个服务启动。
- 浏览器访问笔记本首页正常；经前端代理完成笔记本创建、读取、修改、删除。
- PostgreSQL ready、Elasticsearch green、MinIO 健康检查及对象写入/读取/删除、Celery ping 通过。
- 54 项相关后端测试通过；另有 Docker Compose 配置测试。
- 模型链路实测通过：使用一页合成 PDF，经前端上传、关联笔记本，由 Celery 调用 MinerU 云解析，完成 Embedding API 调用与向量索引（1 个文本块）。任务完成，无处理错误。
- 应用知识库问答实测通过：`ask` 模式正确回答测试文档中的唯一验证码 `NBN-MAC-739251`、预算 `18,437 USD`、负责人 `Mira Vale`；响应包含对应文档和文本块的 `sources`，`warnings` 为空。
- 测试笔记本与测试文档已通过应用接口删除，并验证返回 404。仅使用合成测试数据，未上传用户资料。
- 后续已补充验证语音转码/ASR、图片生成 API、Tavily 和智谱聊天等，详见全面验收记录。视频完整链路和 Shell 沙箱仍有限制。
