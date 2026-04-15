# Bilibili Fix — Improve-1

## 背景

Studio 的 Video 模块在用户未登录 Bilibili 的情况下发起视频总结请求时，
底层 `bilibili_api` 库会抛出 `CredentialNoSessdataException`。
基础设施层已将其映射为 `AuthenticationError`，应用服务层也已将其转化为前端可读的 SSE `error` 事件，前端也已实现登录引导 UI。

问题在于：`_handle_failure` 对所有异常使用 `logger.exception()` 记录，
导致这个在业务上属于预期的用户错误仍然输出完整的 Python traceback，
在日志侧制造噪音，干扰真正需要关注的系统级错误。

此外，`/videos/info` 端点以及其他直接调用基础设施层的入口缺少异常兜底，
存在将 `AuthenticationError` 等基础设施异常穿透为 FastAPI 500 的风险。

## 目标

1. 将 `AuthenticationError` 等预期用户错误从 `logger.exception`（打印 traceback）
   降级为 `logger.warning`（不打印 traceback），保持日志信噪比。
2. 在 `_summarize_bilibili` 入口处增加凭据前置检查（fail-fast），
   在进入昂贵的网络调用之前快速失败，减少无效请求。
3. 为 `/videos/info` 端点加上 `AuthenticationError` / `BiliError` 的 HTTP 层转换，
   消除 500 穿透风险。

## 非目标

- 不修改前端登录引导逻辑（已有实现，本轮不涉及）。
- 不修改 `AuthenticationError` 向 SSE `error` 事件的映射逻辑（已正确）。
- 不修改 Bilibili 认证方式或凭据管理流程。

## 改动范围

| 层级 | 文件 | 改动类型 |
|------|------|---------|
| 基础设施层 | `newbee_notebook/infrastructure/bilibili/client.py` | 新增 `has_credentials()` |
| 应用服务层 | `newbee_notebook/application/services/video_service.py` | 日志分级；入口前置检查 |
| API 路由层 | `newbee_notebook/api/routers/videos.py` | `/videos/info` 异常转换 |

## 文档清单

| 文档 | 说明 |
|------|------|
| [problem-analysis.md](problem-analysis.md) | 根因定位、调用链分析、风险梳理 |
| [fix-plan.md](fix-plan.md) | 具体修复方案与变更说明 |
