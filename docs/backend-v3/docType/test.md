# test.md — 文档类型扩展模块

> 前置：测试目标对应阶段一交付标准，即“稳定支持上传、检索、总结”，而非追求结构语义完美。

## Test Scope

### 必测范围

- `DocumentType` 是否正确识别 `.pptx/.epub`
- 上传白名单是否正式允许 `.pptx/.epub`
- `MarkItDownConverter` 是否能接住 `.epub`
- `DocumentProcessor` 是否把 `.pptx/.epub` 路由到 `MarkItDown`
- 真实 `.pptx/.epub` 文件是否能转换出非空 Markdown
- 新类型是否不会破坏下游索引/总结入口

### 不在本次强制范围

- `MarkItDown` 内部解析质量的细粒度断言
- 复杂排版、图片、注释、EPUB 样式保真的完美性
- 阶段二专用 converter 的任何验证

## Acceptance Criteria

阶段一通过标准：

1. `.pptx/.epub` 可成功上传到 Library
2. 数据库 `content_type` 正确写入
3. Worker 转换成功，生成非空 Markdown
4. 文档能进入后续索引/检索/总结链路
5. 既有格式回归测试通过

## Critical Scenarios

### 1. 类型识别

| 场景 | 输入 | 预期 |
|---|---|---|
| PPTX 扩展名识别 | `from_extension("pptx")` | `DocumentType.PPTX` |
| EPUB 扩展名识别 | `from_extension("epub")` | `DocumentType.EPUB` |
| 支持列表同步 | `supported_extensions()` | 包含 `pptx`、`epub` |

### 2. 上传准入

| 场景 | 输入 | 预期 |
|---|---|---|
| 上传白名单包含 PPTX | `.pptx` 文件 | 不报 `Unsupported file type` |
| 上传白名单包含 EPUB | `.epub` 文件 | 不报 `Unsupported file type` |
| 旧格式不回归 | `.pdf/.docx/.md` | 行为与改动前一致 |

### 3. 转换路由

| 场景 | 条件 | 预期 |
|---|---|---|
| PPTX 路由 | MinerU 启用 | `MarkItDown` 接管 |
| EPUB 路由 | MinerU 启用 | `MarkItDown` 接管 |
| PPTX 路由 | MinerU 禁用 | `MarkItDown` 接管 |
| EPUB 路由 | MinerU 禁用 | `MarkItDown` 接管 |

### 4. 真实转换

| 场景 | 输入 | 预期 |
|---|---|---|
| PPTX 转换成功 | 最小有效 `.pptx` 夹具 | `markdown.strip()` 非空 |
| EPUB 转换成功 | 最小有效 `.epub` 夹具 | `markdown.strip()` 非空 |
| PPTX page_count | 含多页 slide 的 `.pptx` | `page_count` 为合理值或保持明确 fallback |
| EPUB page_count | 最小有效 `.epub` | 保持当前约定值，不引发异常 |

### 5. 回归

| 场景 | 预期 |
|---|---|
| PDF 路由回归 | 仍然优先 MinerU |
| DOCX 路由回归 | 仍然保持现有兼容策略 |
| 未知扩展名行为 | 不引入新的异常放宽 |

## Verification Strategy

### 单元测试

优先补以下测试：

- `DocumentType.from_extension()`
- `DocumentType.supported_extensions()`
- 上传白名单集合 / 上传存储函数
- `MarkItDownConverter.can_handle(".epub")`
- `DocumentProcessor._get_converters_for_ext(".pptx")`
- `DocumentProcessor._get_converters_for_ext(".epub")`

### 转换测试

准备最小化夹具：

- `tests/fixtures/sample.pptx`
- `tests/fixtures/sample.epub`

验证：

- `await MarkItDownConverter.convert(path)` 成功
- 返回 Markdown 非空
- 不因缺失新类型注册而失败

### 端到端验证

如果本轮实现完成，至少做一次人工或自动化验证：

1. 在 Library 页面上传 `.pptx`
2. 在 Library 页面上传 `.epub`
3. 观察状态进入处理完成
4. 确认文档可被 notebook 引用
5. 确认可参与总结或问答

## Regression Checklist

实现完成前必须重新确认：

- `.pdf` 转换测试未坏
- `test_document_processing_processor.py` 既有 MinerU 相关测试仍通过
- 前端上传入口未破坏已有多文件上传行为
- 不会因为前端 `accept` 或后端白名单修改而误伤现有文件类型
