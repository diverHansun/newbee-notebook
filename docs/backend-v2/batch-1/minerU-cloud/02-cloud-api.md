# MinerU v4 云端 API 参考

本文记录 MinerU v4 Smart Parsing 云端 API 的接口定义、格式支持、请求流程和响应结构，供 `MinerUCloudConverter` 实现和运维参考。

## 1. 支持的文件格式

MinerU 云端 API 官方支持以下格式（来源：官方文档 + 实际验证）：

| 格式 | 说明 |
|------|------|
| `.pdf` | PDF 文档，当前已接入 |
| `.doc` / `.docx` | Word 文档，已验证（见第 6 节） |
| `.ppt` / `.pptx` | PowerPoint 演示文稿 |
| `.png` / `.jpg` / `.jpeg` | 图像文件 |
| `.html` | 网页文件（需指定 `model_version=MinerU-HTML`） |

上传时文件名必须带有正确后缀，API 通过后缀识别格式。

## 2. 接口一览

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 申请上传 URL | POST | `/api/v4/file-urls/batch` | 获取 OSS 预签名上传链接 |
| 上传文件 | PUT | `{file_url}` | 将文件写入 OSS |
| 查询批次结果 | GET | `/api/v4/extract-results/batch/{batch_id}` | 轮询解析状态与结果 |

API Base URL：`https://mineru.net`

所有请求需在 Header 中携带：
```
Authorization: Bearer {token}
Content-Type: application/json   # 仅适用于 POST 请求
```

## 3. 申请上传 URL

**请求**

```
POST /api/v4/file-urls/batch

{
    "files": [
        {
            "name": "document.docx",
            "data_id": "可选的业务标识符"
        }
    ],
    "model_version": "vlm"
}
```

**请求体参数**

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `files[].name` | string | 是 | — | 文件名，**必须带正确后缀** |
| `files[].data_id` | string | 否 | — | 业务数据 ID，原样返回 |
| `files[].is_ocr` | bool | 否 | false | 强制启用 OCR（pipeline/vlm 模型有效） |
| `files[].page_ranges` | string | 否 | — | 指定页码范围，如 `"2,4-6"` |
| `model_version` | string | 否 | pipeline | `pipeline` / `vlm` / `MinerU-HTML` |
| `enable_formula` | bool | 否 | true | 开启公式识别 |
| `enable_table` | bool | 否 | true | 开启表格识别 |
| `language` | string | 否 | ch | 文档语言代码 |
| `extra_formats` | [string] | 否 | — | 额外导出格式，可选 `docx`、`html`、`latex` |
| `callback` | string | 否 | — | 结果回调 URL（POST 方式） |

**响应**

```json
{
    "code": 0,
    "msg": "ok",
    "data": {
        "batch_id": "fa7d797e-a050-4a56-ae67-13a8698d3109",
        "file_urls": [
            "https://mineru.oss-cn-shanghai.aliyuncs.com/api-upload/..."
        ]
    }
}
```

`file_urls` 与 `files` 数组一一对应。上传链接有效期 **24 小时**。

## 4. 上传文件

```
PUT {file_url}
Content-Type: （不设置，OSS 预签名 URL 已内置）

Body: 文件二进制内容
```

响应 HTTP 200 表示上传成功。文件上传完成后，解析任务由系统**自动提交**，无需额外调用。

## 5. 查询批次结果

**请求**

```
GET /api/v4/extract-results/batch/{batch_id}
```

**响应（进行中）**

```json
{
    "code": 0,
    "data": {
        "batch_id": "fa7d797e-...",
        "extract_result": [
            {
                "state": "running",
                "extract_progress": {
                    "extracted_pages": 3,
                    "total_pages": 10,
                    "start_time": "2026-02-24 12:00:00"
                }
            }
        ]
    }
}
```

**响应（完成）**

```json
{
    "code": 0,
    "data": {
        "batch_id": "fa7d797e-...",
        "extract_result": [
            {
                "state": "done",
                "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/...",
                "err_msg": ""
            }
        ]
    }
}
```

**任务状态值**

| state | 含义 |
|-------|------|
| `waiting-file` | 等待文件上传 |
| `pending` | 排队中 |
| `running` | 解析中 |
| `converting` | 格式转换中 |
| `done` | 完成，`full_zip_url` 可用 |
| `failed` | 失败，原因见 `err_msg` |

## 6. 结果 ZIP 内容

下载 `full_zip_url` 得到 ZIP 文件，典型目录结构：

```
full.md                              # 主 Markdown 文档（优先使用）
content_list_v2.json                 # 结构化内容列表（含段落、表格等）
layout.json                          # 布局信息（含 pdf_info，用于提取页数）
{uuid}_origin.pdf                    # 内部中间文件（docx 转 pdf 产物）
{uuid}_model.json                    # 模型输出原始数据
images/
    {image_name}.png                 # 提取的图像资源
```

`MinerUCloudConverter._parse_result_zip()` 的处理规则：
- Markdown：优先 `full.md`，其次第一个 `.md` 文件
- `image_assets`：`images/` 目录下所有文件，以文件名为 key
- `metadata_assets`：所有 `.json` 文件，以文件名为 key
- 页数：从 `layout.json` → `pdf_info[].length` 提取

## 7. 限制与约束

| 限制项 | 值 |
|--------|-----|
| 单文件大小 | 最大 200 MB |
| 单文件页数 | 最多 600 页 |
| 每日免费额度 | 2000 页（超出后优先级降低） |
| 单次批量申请 | 最多 200 个文件 |
| 上传链接有效期 | 24 小时 |
| 国外 URL | 不可用（GitHub、AWS 等域名超时） |
| 该接口不支持文件直接上传 | 必须先申请预签名 URL |

## 8. 常用错误码

| 错误码 | 含义 | 处理建议 |
|--------|------|----------|
| `A0202` | Token 错误 | 检查 Bearer 格式与 Token 有效性 |
| `A0211` | Token 过期 | 更换新 Token |
| `-60002` | 文件格式不支持 | 确认文件名后缀在支持列表内 |
| `-60005` | 文件大小超限 | 文件不得超过 200 MB |
| `-60006` | 页数超限 | 拆分后重试 |
| `-60015` | docx/pptx 转换失败 | 可手动转为 PDF 后上传 |
| `-60010` | 解析失败 | 稍后重试 |

## 9. docx 解析验证记录

**验证时间**：2026-02-24

**测试文件**：`7.28-tiktok-bans.docx`（16,379 字节，英文短文档）

**验证结果**：

| 步骤 | 结果 |
|------|------|
| POST /api/v4/file-urls/batch（`name: "7.28-tiktok-bans.docx"`） | code=0，获取 batch_id 和 upload_url |
| PUT presigned URL | HTTP 200，上传成功 |
| GET 轮询（首次 pending，次次 done） | 极快完成（约 5-10 秒） |
| 下载 ZIP | HTTP 200，27,252 字节 |
| ZIP 内容 | 含 `full.md`、`content_list_v2.json`、`layout.json`、`_origin.pdf`、`_model.json` |
| markdown 质量 | 正文内容完整提取，3,371 字符 |

> 注意：MinerU 内部将 docx 先转换为 PDF（`*_origin.pdf`），再走 OCR/VLM 流水线。这意味着 docx 的页数计算需要通过 `layout.json` 获取，不能直接用 `PdfReader` 读取原始 docx。
