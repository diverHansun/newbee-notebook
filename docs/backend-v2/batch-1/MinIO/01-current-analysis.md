# 现状分析: Bind Mount 存储方案与前端集成痛点

本文档复盘当前 Bind Mount 存储方案的完整数据流，分析其在前后端联调场景下的局限性，为 MinIO 迁移提供决策依据。

> 注: 本文档描述的是 MinIO 落地前的旧架构。文中的 `data/documents` 引用仅用于历史分析；当前运行时持久真源已切换为 MinIO，本地目录只保留给 legacy/offline/test 场景。

---

## 1. 当前存储架构

### 1.1 文件系统结构

```
data/documents/{document_id}/
├── original/                    # 原始上传文件
│   └── filename.pdf
├── markdown/
│   └── content.md               # MinerU 转换后的 Markdown
└── assets/
    ├── images/                  # MinerU 提取的图片
    │   ├── {sha256_hash}.jpg
    │   ├── {sha256_hash}.png
    │   └── ...
    └── meta/                    # 处理元数据
        ├── layout.json
        └── {uuid}_content_list.json
```

### 1.2 数据分布

| 存储位置 | 数据内容 | 访问方式 |
|----------|----------|----------|
| PostgreSQL (pgvector) | 文档元数据、向量索引、会话记录 | SQLAlchemy ORM |
| Elasticsearch | 全文检索索引 (BM25) | elasticsearch-py |
| 文件系统 (Bind Mount) | PDF原件、Markdown、图片、元数据 | Python pathlib / FastAPI FileResponse |

### 1.3 Docker Compose 中的挂载方式

```yaml
services:
  celery-worker:
    volumes:
      - ./:/app    # 整个项目目录挂载，包含 data/documents/
```

Celery Worker 通过 Bind Mount 直接读写宿主机的 `data/documents/` 目录。FastAPI 应用在宿主机直接运行(非容器化)，同样直接访问该目录。

---

## 2. 当前数据流分析

### 2.1 文档上传与处理流程

```
用户上传 PDF
    |
    v
FastAPI 接收文件 → local_storage.save_upload_file()
    |                 保存到 data/documents/{id}/original/
    v
Celery 异步任务 → MinerU 转换
    |                 生成 markdown/ 和 assets/images/
    v
图片路径重写 → 将 MinerU 原始路径替换为 API 路径
    |             (/api/v1/documents/{id}/assets/images/{hash}.jpg)
    v
文本分块 → 向量化 → 索引到 pgvector + Elasticsearch
    |
    v
更新 PostgreSQL 文档状态: COMPLETED
```

### 2.2 MinerU Markdown 中的图片引用格式

MinerU 处理后，Markdown 中的图片引用已被重写为完整的 API 路径:

```markdown
![](/api/v1/documents/393f579b-2318-42eb-8a0a-9b5232900108/assets/images/a267b503d04e27b3714e833eec9c079135c700adbe9783e90474d34ce4e7e6be.jpg)
```

特征:
- 使用标准 Markdown 图片语法 `![alt](url)`
- alt text 为空
- URL 是以 `/api/v1/` 开头的绝对路径
- 图片文件名是 SHA-256 哈希值

这意味着**图片路径已经和后端 API 强耦合**，每张图片的获取都必须经过 FastAPI 后端。

### 2.3 前端获取内容的完整链路

```
前端请求 Markdown 内容
    |
    v
GET /api/v1/documents/{id}/content?format=markdown
    |
    v
DocumentService.get_document_content()
    |  读取 data/documents/{id}/markdown/content.md
    |  原样返回 Markdown 文本(不做路径转换)
    v
前端 react-markdown 渲染
    |  解析到 ![](/api/v1/documents/{id}/assets/images/{hash}.jpg)
    |  浏览器发起图片请求
    v
GET /api/v1/documents/{id}/assets/images/{hash}.jpg    (每张图片一次请求)
    |
    v
DocumentService.get_asset_path()
    |  路径校验 (UUID格式、防遍历)
    |  解析到 data/documents/{id}/assets/images/{hash}.jpg
    v
FastAPI FileResponse → 读取磁盘文件 → 返回图片字节流
    |
    v
浏览器渲染图片
```

---

## 3. 前端集成痛点

### 3.1 后端成为图片代理瓶颈

**问题描述**: 每张图片请求都经过 FastAPI → DocumentService → 磁盘读取 → HTTP 响应的完整链路。

**量化影响**:
- 实际文档中，单份 PDF 转换后可产生 **100+ 张图片** (已验证: document `3bebffae` 包含 100+ 张图片)
- 用户打开文档阅读器时，浏览器会并发请求所有可见图片
- FastAPI 作为 ASGI 应用，处理大量同步文件 I/O 会占用工作线程
- 如果多个用户同时查看不同文档，并发图片请求量会成倍增长

**对比**: 静态文件服务器(如 Nginx)或对象存储(如 MinIO)专门为高并发文件服务设计，吞吐量远高于应用层代理。

### 3.2 缺乏 HTTP 缓存机制

**问题描述**: 当前 asset 路由返回的 `FileResponse` 没有设置缓存相关的 HTTP 头。

```python
# 当前实现 (documents.py)
return FileResponse(path=file_path, media_type=media_type or "application/octet-stream")
# 缺少: Cache-Control, ETag, Last-Modified
```

**影响**:
- 用户每次打开同一文档，浏览器都会重新请求所有图片
- 对于经常查阅的文档，网络流量和后端负载被不必要地放大
- 即使添加缓存头，仍然需要后端处理条件请求 (304 Not Modified)

### 3.3 图片路径与后端 API 强耦合

**问题描述**: MinerU 生成的 Markdown 中硬编码了 `/api/v1/documents/{id}/assets/images/...` 路径。

**影响**:
- API 路径变更需要同步修改所有已处理文档的 Markdown 文件
- 无法在不修改内容的情况下切换图片来源(如 CDN、对象存储)
- 前端 Next.js 的 `rewrites` 配置将所有 `/api/v1/` 请求代理到后端，图片流量也不例外

### 3.4 单机存储限制

**问题描述**: Bind Mount 将文件绑定到运行 Docker 的单台宿主机。

**影响**:
- 无法水平扩展: 多实例部署时文件不共享
- 备份依赖操作系统层面工具: 需要手动 `rsync` 或文件系统快照
- 部署迁移时需要手动复制 `data/documents/` 目录

---

## 4. 当前方案的优势(需保留)

尽管存在上述痛点，当前方案在开发阶段有明确的优势:

| 优势 | 说明 |
|------|------|
| 零额外服务 | 不需要运行额外的存储服务，Docker 资源占用低 |
| 直接调试 | 开发者可以在文件管理器中直接查看 MinerU 转换结果 |
| 路径简单 | `data/documents/{id}/` 结构清晰，排查问题快速 |
| 已有清理工具 | `make clean-doc` 和孤儿检测机制已完善 |

迁移方案必须保留这些优势在开发环境中的可用性。

---

## 5. 结论

当前 Bind Mount 方案在**后端独立开发期**表现良好，但在**前后端联调和部署场景**下存在结构性瓶颈:

1. **性能**: FastAPI 不适合作为静态文件代理服务器
2. **缓存**: 缺乏标准化的 HTTP 缓存支持
3. **耦合**: 图片路径硬编码在 Markdown 内容中
4. **扩展**: 单机存储无法支撑多实例部署

引入 MinIO 对象存储可以解决以上全部问题，同时通过 Presigned URL 机制将图片服务从后端卸载到专用存储服务。具体架构设计见 [02-storage-abstraction.md](./02-storage-abstraction.md)。
