# 问题分析

与 [fix-plan.md](fix-plan.md) 配合阅读，本文档专注于根因定位与风险梳理，不包含修复方案。

---

## 一、问题描述

当用户未登录 Bilibili（即后端未配置有效的 sessdata 凭据）时，
发起视频总结请求会触发以下服务端输出：

```
Traceback (most recent call last):
  File "newbee_notebook/infrastructure/bilibili/client.py", line 259, in _call_api
    return await awaitable
  ...
  File "bilibili_api/utils/network.py", line 1300, in raise_for_no_sessdata
    raise CredentialNoSessdataException()
bilibili_api.exceptions.CredentialNoSessdataException: Credential 类未提供 sessdata

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "newbee_notebook/application/services/video_service.py", line 142, in _summarize_bilibili
    transcript_text, _tracks = await self._bili_client.get_video_subtitle(bvid)
  ...
newbee_notebook.infrastructure.bilibili.exceptions.AuthenticationError: get_player_info: ...
```

前端收到了正确的 SSE `error` 事件并展示了登录引导 UI，
说明数据面的错误传递链路是正确的。
上述 traceback 只出现在服务端日志，不影响用户侧行为。

---

## 二、调用链追踪

```
VideoRouter.POST /videos/summarize
  └─ _summarize_stream()
       └─ VideoService.summarize()
            └─ _summarize_bilibili()
                 ├─ _bili_client.get_video_info()         [成功，不需要 sessdata]
                 └─ _bili_client.get_video_subtitle()
                       └─ _call_api("get_player_info", ...)
                             ├─ bilibili_api 抛 CredentialNoSessdataException
                             └─ _map_api_error() 捕获，映射为 AuthenticationError
                                   [re-raise]
                      [AuthenticationError 向上传播]
                 [except Exception as exc]
                 └─ _handle_failure(summary, bvid, exc, progress_callback)
                       ├─ build_stream_error_payload(exc) --> E_BILIBILI_AUTH  [正确]
                       ├─ logger.exception(...)            --> 输出完整 traceback [问题所在]
                       ├─ summary.status = "failed"        [正确]
                       ├─ DB 写入                          [正确]
                       └─ emit SSE error 事件              [正确]
                 [re-raise]
       └─ _run() 的 except 块：error_emitted=True，不重复发送 error 事件  [正确]
```

---

## 三、根因

`_handle_failure` 对所有异常统一调用 `logger.exception()`：

```python
# newbee_notebook/application/services/video_service.py
async def _handle_failure(self, summary, video_id, exc, progress_callback):
    safe_error = self.build_stream_error_payload(exc)
    logger.exception("Video summarize failed for %s", video_id)  # <-- 无差别 traceback
    ...
```

`logger.exception()` 等价于 `logger.error()` 加上当前异常的完整 traceback 输出。
这对系统级错误（网络超时、数据库异常等）是合理的，
但对 `AuthenticationError` 这类预期用户行为来说同等对待，会在日志中制造噪音，
掩盖真正需要处理的系统级错误信号。

---

## 四、关联风险点

### 4.1 凭据检查时机过晚

当前调用顺序：

```
get_video_info()      <- 不需要 sessdata，成功执行（一次网络请求）
get_video_subtitle()  <- 需要 sessdata，此时才触发认证失败
```

用户未登录时，仍然会完成一次 `get_video_info` 的网络调用才发现认证失败，
这次调用从结果上看是无效的。

凭据缺失是可以在请求真正开始之前通过检查本地状态得知的，
没有必要先消耗一次 API 调用。

### 4.2 `/videos/info` 端点缺少异常兜底

```python
# newbee_notebook/api/routers/videos.py
@router.get("/videos/info", response_model=VideoInfoResponse)
async def get_video_info(...):
    return VideoInfoResponse(**(await service.fetch_video_info(value)))
```

`fetch_video_info` 内部调用 `_bili_client.get_video_info()`，
后者通过 `_call_api` 可以抛出 `AuthenticationError`、`NetworkError`、`NotFoundError` 等。

这些异常在当前代码中没有被捕获，会直接穿透为 FastAPI 的 500 Internal Server Error，
这与 `/videos/summarize` 通过 `_handle_failure` 将异常转化为 SSE 错误事件的行为不一致。

就 Bilibili 的 `get_video_info` 接口而言，目前实测不需要 sessdata 即可成功，
此风险暂时没有实际触发。但随着 API 行为变化，
或访问权限需要认证的视频时（充电视频、高清版权等），该风险会变为实际错误。

---

## 五、`build_stream_error_payload` 已覆盖的错误类型

`AuthenticationError` 已在 `build_stream_error_payload` 中有明确映射，
说明当前代码设计层面已将其视为预期用户错误，只是日志侧尚未做对应的区分。

```python
# newbee_notebook/application/services/video_service.py
@staticmethod
def build_stream_error_payload(exc: Exception) -> dict[str, str]:
    if isinstance(exc, AuthenticationError):
        return {
            "error_code": "E_BILIBILI_AUTH",
            "message": "Bilibili session expired or not logged in. Please login and try again.",
        }
    ...
```

这是修复方向的重要依据：`build_stream_error_payload` 中能映射到具体 `error_code` 的异常，
均可视为预期用户错误，日志级别应降为 `warning`，而不应输出 traceback。
