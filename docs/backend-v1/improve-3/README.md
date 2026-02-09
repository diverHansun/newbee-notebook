# MinerU V4 接入改造（improve-3）

## 1. 本轮目标

本轮改造目标是把 PDF 转换主链路切换为 MinerU V4 Smart Parsing，并统一云端与本地 MinerU 处理后的落盘结构，保证前端读取逻辑一致。

## 2. 已确认的产品决策

1. PDF 处理链路固定为：`PDF -> MinerU V4 -> PyPDF`  
2. 非 PDF 文件保持现状：`MarkItDown -> Markdown`  
3. 不再使用 KIE 作为路由兜底（保留历史代码可后续清理，但不进入主流程）  
4. 云端凭证统一使用 `MINERU_API_KEY`，不再使用 `MINERU_PIPELINE_ID`  
5. 当前阶段不强制使用 `user_token` 与 `model_version`（后续如需可扩展）  
6. 云端与本地 GPU 的输出落盘路径和文件组织必须一致，便于前端统一渲染  

## 3. 官方能力与约束（V4）

基于 MinerU 官方 Smart Parsing 文档，V4 支持通过 API 上传并异步解析，返回结果压缩包（含 markdown/json/images），其能力边界显著高于当前 KIE 路线，更适合多页书籍场景。

已确认的关键差异：

- KIE SDK 文档 FAQ 说明限制为：单文件 100MB、10 页以内（并且主要面向 KIE 流程）
- V4 Smart Parsing 文档说明限制为：单文件 200MB、600 页以内（以 token 额度与账号配额为准）

说明：最终可用额度、并发与限流策略仍以线上账号权限为准。

## 4. 后端实施原则

1. Converter 只负责“解析 + 标准化结果对象”，不直接耦合业务数据库。  
2. Processor 只负责“按扩展名路由 + fallback 次序控制”。  
3. Store 负责统一落盘协议，确保不同 MinerU 来源（云端 v4 / 本地 GPU）输出一致。  
4. API 层负责向前端暴露统一读取路径，不让前端关心云端还是本地。  

## 5. 文档索引

- `01-design.md`：总体设计、路由策略、配置与落盘协议
