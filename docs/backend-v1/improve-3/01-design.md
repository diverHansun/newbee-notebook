# MinerU V4 改造设计（讨论稿）

## 1. 适用范围

本设计仅覆盖文档转换链路与落盘规范，不涉及前端 UI 方案选型。

## 2. 目标架构

### 2.1 文件类型路由

- `.pdf`：`MinerUV4Converter -> PyPdfConverter`
- 其他支持类型（csv/doc/docx/txt/md/...）：`MarkItDownConverter`

说明：
- PDF 不再进入 MarkItDown。
- KIE 不再作为 PDF 路由兜底。

### 2.2 云端/本地统一输出协议

无论来源是：
- MinerU V4 云端（zip 结果）
- 本地 MinerU（CPU/GPU）

都归一为同一份 `ConversionResult` 扩展结构，并通过同一存储函数落盘到统一目录。

## 3. 配置设计（.env / yaml）

## 3.1 关键环境变量

- `MINERU_ENABLED=true|false`
- `MINERU_MODE=cloud|local`
- `MINERU_API_KEY=...`（仅 cloud 必填）
- `MINERU_V4_API_BASE=https://mineru.net`
- `MINERU_V4_TIMEOUT=60`
- `MINERU_V4_POLL_INTERVAL=5`
- `MINERU_V4_MAX_WAIT_SECONDS=1800`
- `MINERU_LOCAL_API_URL=http://mineru-api:8000`
- `MINERU_BACKEND=pipeline|hybrid-auto-engine`
- `MINERU_LANG_LIST=ch,en`
- `MINERU_LOCAL_TIMEOUT=0`

说明：
- `MINERU_PIPELINE_ID` 从主流程移除。
- 当前阶段不引入 `MINERU_USER_TOKEN`、`MINERU_V4_MODEL_VERSION` 必填项；后续若有需要可加可选配置。

## 3.2 官方限制差异（用于路线决策）

- KIE SDK 文档（`/doc/docs/kie`）FAQ 给出的约束是：单文件 100MB、10 页以内。  
- V4 Smart Parsing 文档（`/doc/docs`）给出的约束是：单文件 200MB、600 页以内。  

结论：书籍类长文档优先走 V4；KIE 适合结构化字段抽取而非通用大体量 PDF 转 Markdown。

## 4. 存储规范（核心）

## 4.1 目标目录结构

统一采用以下目录，确保前端读取稳定：

```text
data/documents/{document_id}/
  original/
    <原始上传文件>
  markdown/
    content.md
  assets/
    images/
      <image files>
    meta/
      layout.json
      content_list_v2.json
      manifest.json
```

约束：
- markdown 主文件固定为 `markdown/content.md`。
- 图片固定落在 `assets/images/`，禁止写 `*.bin`。
- 任何来源的 markdown 图片链接都重写为统一 API 路径：`/api/v1/documents/{document_id}/assets/images/<name>`。

## 4.2 markdown 链接重写策略

对 markdown 内图片链接执行标准化：

1. 识别 `![](...)` / `![alt](...)` 与 `<img src=\"...\">` 链接。
2. 若链接是结果包内相对路径（如 `images/xxx.jpg`），映射到 `/api/v1/documents/{document_id}/assets/images/xxx.jpg`。
3. 若链接指向外部 URL（http/https/data），默认保留。
4. 若 markdown 中引用了图片但结果包缺失图片资产，视为解析失败并抛错，交由 Processor fallback。

## 4.3 前端可渲染原则

前端预览中图片能显示，前提是：
- markdown 的图片路径可被浏览器访问；
- 后端提供对应静态读取能力或受控下载能力。

建议接口：
- `GET /api/v1/documents/{document_id}/assets/{asset_path:path}`

用途：
- 允许前端通过文档 ID 访问 `assets/images/*`。
- 与 markdown 链接重写后的路径一一对应。

## 5. Converter 设计

## 5.1 MinerUV4Converter（新增主链路）

职责：
1. 使用 `MINERU_API_KEY` 调用 v4 接口申请上传 URL。
2. 上传 PDF。
3. 轮询任务状态直到 done/failed/timeout。
4. 下载结果 zip 并解析出：
   - `full.md`（或 markdown 主文件）
   - `images/*`
   - 可选元数据 json
5. 返回标准化结果对象（markdown 文本 + 图片资产 + 元信息）。

错误策略：
- 网络错误、任务失败、超时 -> 抛出异常给 Processor。
- Processor 按既定链路 fallback 到 `PyPdfConverter`。

## 5.2 MinerULocalConverter（保留）

职责保持 PDF 本地解析，但输出必须对齐统一协议：
- 返回 markdown 与图片资产；
- 不允许继续以 `images: bytes[] -> *.bin` 的形式存储。

## 6. Processor 路由规则

推荐逻辑：

1. 识别扩展名。
2. 如果是 PDF：
   - `mode=cloud` -> `MinerUV4Converter`
   - `mode=local` -> `MinerULocalConverter`
   - 若上述失败 -> `PyPdfConverter`
3. 非 PDF：
   - `MarkItDownConverter`

明确不包含：
- KIE Converter 路由。
- PDF -> MarkItDown。

## 7. 与当前实现的主要差异

1. 云端从 KIE 切到 V4（认证从 pipeline_id 切到 api_key）。
2. 取消 PDF 的 KIE 路径兜底。
3. 存储层改为“资产目录 + 图片可渲染路径”。
4. 本地 GPU 与云端输出结构对齐。

## 8. 开发顺序建议

1. 增加 V4 converter 与配置读取。
2. 改造 processor 路由（移除 KIE 路由入口）。
3. 改造 store：统一 `assets/images`，实现 markdown 链接重写。
4. 增加 `assets` API 读取接口。
5. 更新 `.env.example`、`document_processing.yaml`、`quickstart.md`、`README.md`。

## 9. 验收标准（本轮）

1. 相同 PDF 在 cloud/local 两种 MinerU 跑完后，目录结构一致。  
2. `content.md` 的图片链接可直接被前端请求到。  
3. PDF 转换链路严格符合 `PDF -> V4(or local) -> PyPDF`。  
4. 非 PDF 文件处理结果与现状一致（仍由 MarkItDown 负责）。  

## 10. 待最终确认项

1. `assets` API 是做文档级鉴权下载，还是临时先开放只读。  
2. local 模式下若 MinerU API 不返回原图文件，是否允许只保留 markdown 文本并告警。  
