# MinerU 云端集成 — Backend-v2

本目录记录 backend-v2 阶段对 MinerU 文档处理集成的现状分析与扩展方案。

## 背景

backend-v1 中，MinerU 转换器（云端与本地）均只处理 `.pdf` 格式，其余格式统一由 MarkItDown 兜底。经调研，MinerU 云端 API（v4）原生支持 `.doc`、`.docx`、`.ppt`、`.pptx` 等 Office 格式，且已通过实际文件上传验证。backend-v2 计划将云端转换器的格式支持扩展至上述格式。

## 调研结论

| 模式 | docx 支持 | 改动成本 |
|------|-----------|----------|
| MinerU 云端 | 已验证可用，官方支持 | 极低，仅改 `can_handle()` 与页数逻辑 |
| MinerU 本地（Docker） | 不支持，硬编码拒绝非 PDF/图像 | 不扩展，docx 走 MarkItDown fallback |
| MarkItDown | 已支持 docx/doc/pptx/xlsx 等 | 保持不变，作为兜底 |

## 文档列表

| 文档 | 职责 |
|------|------|
| [01-converter-architecture.md](01-converter-architecture.md) | 转换器链组装规则、fallback 机制、断路器逻辑 |
| [02-cloud-api.md](02-cloud-api.md) | MinerU v4 云端 API 接口、格式支持、请求流程、响应结构 |
| [03-docx-extension.md](03-docx-extension.md) | docx/doc/pptx 扩展方案、改动点、边界情况 |
| [04-config-reference.md](04-config-reference.md) | 所有环境变量与 YAML 配置项完整参考 |

## 关键文件路径

```
newbee_notebook/infrastructure/document_processing/
├── processor.py                         # 转换器链组装与 fallback 调度
├── converters/
│   ├── base.py                          # Converter 协议与 ConversionResult 定义
│   ├── mineru_cloud_converter.py        # MinerU 云端转换器
│   ├── mineru_local_converter.py        # MinerU 本地转换器
│   └── markitdown_converter.py          # MarkItDown 兜底转换器
newbee_notebook/configs/
└── document_processing.yaml             # 配置定义（含环境变量映射）
```
