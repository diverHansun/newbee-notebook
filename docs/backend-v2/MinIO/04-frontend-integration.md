# 前端集成: Markdown 图片路径转换与 Presigned URL

本文档描述 MinIO 存储后端下前端获取和渲染文档内容的完整方案，重点解决 Markdown 中嵌入图片的路径转换问题。

---

## 1. 问题定义

### 1.1 当前 Markdown 中的图片路径

MinerU 处理流程在将 PDF 转换为 Markdown 后，会将图片引用重写为后端 API 路径:

```markdown
![](/api/v1/documents/393f579b-2318-42eb-8a0a-9b5232900108/assets/images/a267b503d04e27b3714e833eec9c079135c700adbe9783e90474d34ce4e7e6be.jpg)
```

### 1.2 当前请求链路

```
Browser (react-markdown 渲染)
    |
    |  1. GET /api/v1/documents/{id}/content  → 获取 Markdown 文本
    |  2. 解析到 N 个 ![](/api/v1/documents/{id}/assets/images/...) 引用
    |  3. 对每张图片发起 GET 请求
    |
    v
Next.js rewrites (代理)
    |
    v
FastAPI  (每张图片经过路由匹配 → Service → 磁盘读取 → FileResponse)
    |
    v
文件系统 (data/documents/{id}/assets/images/{hash}.jpg)
```

**核心问题**: N 张图片 = N 次 FastAPI 请求，后端成为图片代理瓶颈。

### 1.3 目标链路 (MinIO 方案)

```
Browser (react-markdown 渲染)
    |
    |  1. GET /api/v1/documents/{id}/content  → 获取 Markdown 文本 (图片路径已替换为 Presigned URL)
    |  2. 解析到 N 个 ![](http://localhost:9000/documents/...?X-Amz-...) 引用
    |  3. 对每张图片直接请求 MinIO
    |
    v
MinIO (专业文件服务，高并发，无需经过 FastAPI)
```

**效果**: 后端只处理 1 次 Markdown 文本请求，图片由 MinIO 直接服务。

---

## 2. 内容服务层改造

### 2.1 ContentService: Markdown 路径转换

在 DocumentService 返回 Markdown 内容时，动态替换图片路径为存储后端的 URL:

```python
# newbee_notebook/application/services/content_service.py

import re
from datetime import timedelta

from newbee_notebook.infrastructure.storage.base import StorageBackend


class ContentService:
    """文档内容服务，负责读取和预处理 Markdown 内容。

    主要职责: 将 Markdown 中的图片引用路径替换为存储后端提供的可访问 URL。
    """

    # 匹配 MinerU 生成的图片引用格式
    # 捕获 document_id 和 asset_path
    IMAGE_PATTERN = re.compile(
        r'!\[([^\]]*)\]\(/api/v1/documents/([0-9a-f-]{36})/assets/(images/[^)]+)\)'
    )

    def __init__(self, storage: StorageBackend):
        self._storage = storage

    async def get_enriched_content(
        self,
        document_id: str,
        content_path: str,
        url_expires: timedelta = timedelta(hours=2),
    ) -> str:
        """读取 Markdown 内容并替换图片路径。

        Args:
            document_id: 文档 ID
            content_path: Markdown 文件的对象键 (如 {document_id}/markdown/content.md)
            url_expires: Presigned URL 有效期

        Returns:
            图片路径已替换的 Markdown 文本
        """
        # 读取原始 Markdown
        raw_content = await self._storage.get_text(content_path)

        # 收集所有图片引用
        matches = list(self.IMAGE_PATTERN.finditer(raw_content))
        if not matches:
            return raw_content

        # 批量生成 URL
        replacements = {}
        for match in matches:
            alt_text = match.group(1)
            doc_id = match.group(2)
            asset_path = match.group(3)  # e.g., images/a267b5...jpg
            object_key = f"{doc_id}/assets/{asset_path}"

            if object_key not in replacements:
                url = await self._storage.get_file_url(
                    object_key, expires=url_expires
                )
                replacements[object_key] = url

        # 执行替换
        def replace_match(match):
            alt_text = match.group(1)
            doc_id = match.group(2)
            asset_path = match.group(3)
            object_key = f"{doc_id}/assets/{asset_path}"
            url = replacements[object_key]
            return f"![{alt_text}]({url})"

        return self.IMAGE_PATTERN.sub(replace_match, raw_content)
```

### 2.2 替换效果示例

**LocalStorageBackend (开发环境)**:

输入:
```markdown
![](/api/v1/documents/393f579b-.../assets/images/a267b5...jpg)
```

输出 (不变，因为 LocalStorage 返回相同的 API 路径):
```markdown
![](/api/v1/documents/393f579b-.../assets/images/a267b5...jpg)
```

**MinIOStorageBackend (生产环境)**:

输入:
```markdown
![](/api/v1/documents/393f579b-.../assets/images/a267b5...jpg)
```

输出 (替换为 Presigned URL):
```markdown
![](http://localhost:9000/documents/393f579b-.../assets/images/a267b5...jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Expires=7200&X-Amz-Signature=...)
```

### 2.3 为什么在后端做替换而非前端

| 方案 | 优点 | 缺点 |
|------|------|------|
| 后端替换 (选定) | 前端零改动；URL 生成逻辑集中管理；可控制过期时间 | 后端处理略增延迟 (正则替换 + URL 生成) |
| 前端替换 | 后端 content API 不变 | 前端需要知道存储后端类型；需要额外 API 获取 URL；增加前端复杂度 |
| 前端直接拼接 MinIO URL | 最简单 | 暴露 MinIO 地址细节；无签名认证；前端与存储层强耦合 |

后端替换的延迟开销:
- 正则匹配: 对于包含 100 个图片引用的 Markdown，耗时可忽略 (<1ms)
- Presigned URL 生成: 纯计算操作 (HMAC-SHA256 签名)，无网络 I/O，每个 URL ~0.1ms
- 总计额外延迟: <20ms，完全可接受

---

## 3. API 改造

### 3.1 GET /documents/{id}/content 端点

路由层无需修改，Service 层内部调用 ContentService:

```python
# document_service.py 中的改造

async def get_document_content(
    self,
    document_id: str,
    format: str = "markdown",
) -> tuple[Document, str]:
    doc = await self._document_repo.get(document_id)
    if not doc:
        raise ValueError("Document not found")
    if doc.status != DocumentStatus.COMPLETED:
        raise ValueError("Document not ready")
    if not doc.content_path:
        raise ValueError("No content available")

    # 改造点: 使用 ContentService 读取并预处理内容
    content = await self._content_service.get_enriched_content(
        document_id=document_id,
        content_path=f"{document_id}/markdown/content.md",
    )

    return doc, content
```

### 3.2 GET /documents/{id}/assets/{path} 端点

在 MinIO 模式下，此端点仍然保留作为**降级路径**:
- 如果 Presigned URL 过期或失效，前端重试时仍可通过此路径获取
- LocalStorage 模式下继续作为主要图片服务路径

```python
# documents.py 中的改造 (可选优化)

@router.get("/{document_id}/assets/{asset_path:path}")
async def get_document_asset(
    document_id: str,
    asset_path: str,
    storage: StorageBackend = Depends(get_storage),
):
    """Serve document assets. In MinIO mode, prefer presigned URLs from content API."""
    object_key = f"{document_id}/assets/{asset_path}"

    if not await storage.exists(object_key):
        raise HTTPException(status_code=404, detail="Asset not found")

    # 对于 MinIO 后端: 重定向到 Presigned URL
    if isinstance(storage, MinIOStorageBackend):
        url = await storage.get_file_url(object_key)
        return RedirectResponse(url=url, status_code=307)

    # 对于本地后端: 直接返回文件
    file_path = storage._resolve_path(object_key)
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=file_path, media_type=media_type or "application/octet-stream")
```

---

## 4. 前端影响分析

### 4.1 前端代码无需修改

以下前端组件在两种存储模式下行为一致:

| 组件 | 行为 | 原因 |
|------|------|------|
| `MarkdownViewer` | `react-markdown` 渲染 Markdown 内容 | 图片 URL 已在后端替换完成，对组件透明 |
| `useDocumentContent` | TanStack Query 获取内容 | API 路径不变: `GET /documents/{id}/content` |
| `DocumentReader` | 加载并展示内容 | 上层组件，不直接处理图片 URL |

### 4.2 图片加载行为变化

| 场景 | LocalStorage | MinIO |
|------|-------------|-------|
| 图片 URL 格式 | `/api/v1/documents/{id}/assets/...` | `http://localhost:9000/documents/...?signature` |
| 请求路径 | Browser → Next.js rewrite → FastAPI → 磁盘 | Browser → MinIO (直连) |
| 缓存行为 | 依赖 FastAPI 响应头 | MinIO 自动返回 `ETag` 和 `Last-Modified` |
| 并发能力 | 受限于 FastAPI 工作线程 | MinIO 原生高并发 |

### 4.3 CORS 配置

MinIO 需要允许前端域名的跨域请求。在 MinIO 的桶策略或环境变量中配置:

```bash
# docker-compose.yml 中 MinIO 的环境变量
environment:
  MINIO_BROWSER_REDIRECT_URL: "http://localhost:9001"
  # CORS 由 MinIO 自动处理 Presigned URL 请求
```

如果出现 CORS 问题，可通过 `mc` 设置桶的 CORS 规则:

```bash
# 创建 cors.json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["http://localhost:3000", "http://localhost:5173"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}

# 应用 CORS 配置 (通过 mc admin 或桶策略)
```

实际上，Presigned URL 的请求通常不受 CORS 限制，因为浏览器将其视为普通资源请求 (如 `<img src="...">`)。只有通过 `fetch()` 或 `XMLHttpRequest` 访问时才会触发 CORS 检查。`react-markdown` 渲染的 `<img>` 标签属于前者，不会有 CORS 问题。

---

## 5. Next.js 配置调整

### 5.1 images 域名白名单

Next.js 的 `<Image>` 组件 (如果使用) 需要配置允许的外部图片域名:

```javascript
// next.config.js
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '9000',
        pathname: '/documents/**',
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
};
```

注意: 当前前端设计中 `MarkdownViewer` 使用 `react-markdown` 渲染，生成的是原生 `<img>` 标签而非 Next.js 的 `<Image>` 组件，因此这一配置是可选的。如果后续优化为 `<Image>` 组件以利用 Next.js 的图片优化功能，则需要此配置。

### 5.2 rewrites 不需要新增

MinIO 的 Presigned URL 是完整的 `http://localhost:9000/...` 地址，浏览器直接请求 MinIO，不经过 Next.js 代理。因此 `rewrites` 配置无需修改。

---

## 6. Presigned URL 生命周期管理

### 6.1 URL 过期策略

| 场景 | 建议过期时间 | 理由 |
|------|-------------|------|
| 文档内容中的图片 | 2 小时 | 用户阅读时长通常不超过 2 小时 |
| 原始文件下载链接 | 1 小时 | 一次性下载操作 |
| 缩略图 / 预览图 | 4 小时 | 文档列表页停留较久 |

### 6.2 URL 过期后的处理

当用户长时间打开文档阅读器 (超过 Presigned URL 有效期) 时，图片会加载失败。处理策略:

**方案 A: 前端重新请求内容 (推荐)**

```typescript
// 前端: 定时刷新文档内容
const { data: content, refetch } = useDocumentContent(documentId);

useEffect(() => {
  // 每 90 分钟刷新一次内容 (URL 有效期 120 分钟)
  const interval = setInterval(() => {
    refetch();
  }, 90 * 60 * 1000);
  return () => clearInterval(interval);
}, [refetch]);
```

**方案 B: 后端缓存 URL 映射**

后端可缓存 (document_id, object_key) → presigned_url 的映射，在 URL 即将过期时自动刷新。但这增加了后端复杂度，在 MVP 阶段不建议实现。

### 6.3 LocalStorage 模式下的行为

LocalStorage 模式返回的 URL 是 `/api/v1/documents/{id}/assets/...` 格式，不存在过期问题。`expires` 参数在 LocalStorageBackend 中被忽略。

---

## 7. 性能对比预估

### 7.1 单份文档 (100 张图片) 的加载场景

| 指标 | Bind Mount (当前) | MinIO (Presigned URL) |
|------|-------------------|----------------------|
| Markdown 内容请求 | 1 次 FastAPI 请求 | 1 次 FastAPI 请求 (含路径替换) |
| 图片请求 | 100 次 FastAPI 请求 | 100 次 MinIO 直接请求 |
| 后端负载 | 101 次请求处理 | 1 次请求处理 |
| 图片加载延迟 | FastAPI 文件 I/O + HTTP | MinIO 原生文件服务 |
| 浏览器缓存 | 无 (缺少缓存头) | MinIO 返回 ETag + Last-Modified |

### 7.2 多用户并发场景 (5 用户同时查看不同文档)

| 指标 | Bind Mount | MinIO |
|------|-----------|-------|
| 后端总请求量 | ~505 次 (5 * 101) | ~5 次 (5 * 1) |
| 后端 CPU 占用 | 高 (大量文件 I/O 和 HTTP 处理) | 极低 (仅文本处理) |
| 响应延迟 | 随并发增加而升高 | 几乎不受影响 |

迁移的具体实施步骤和时间线见 [05-migration-plan.md](./05-migration-plan.md)。
