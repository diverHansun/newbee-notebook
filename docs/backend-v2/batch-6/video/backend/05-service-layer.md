# Video 模块：应用服务层与总结 Pipeline

## 1. VideoService 概述

VideoService 是 Video 模块的核心应用服务，负责两类工作：

- **总结 pipeline 编排** -- 从视频 URL 到持久化总结的完整流程
- **实体生命周期管理** -- VideoSummary 的 CRUD 和关联操作

VideoService 是 Studio 面板操作 和 agent 工具调用 的共享汇聚点，两条路径调用同一套方法，保证业务逻辑一致。

## 2. 依赖注入

```python
class VideoService:
    def __init__(
        self,
        video_repo: VideoSummaryRepository,
        bili_client: BilibiliClient,
        llm_client: Any,
        storage: StorageBackend,
        ref_repo: NotebookDocumentRefRepository | None = None,
    ): ...
```

| 依赖 | 来源 | 用途 |
|------|------|------|
| video_repo | infrastructure/persistence | VideoSummary 实体的持久化 |
| bili_client | infrastructure/bilibili | B 站 API 交互 |
| llm_client | 现有 LLM 配置 | 总结文本生成 |
| storage | 现有 StorageBackend | 字幕原文存储 |
| ref_repo | 现有基础设施 | 校验 document 是否属于 notebook |

依赖注入链在 `api/dependencies.py` 中组装，遵循现有的 `get_*_service` 工厂模式。

## 3. 总结 Pipeline

### 3.1 方法签名

```python
async def summarize(
    self,
    url_or_bvid: str,
    notebook_id: str | None = None,
    progress_callback: Callable[[str, dict], Awaitable[None]] | None = None,
) -> VideoSummary:
```

`progress_callback` 的签名为 `async (event: str, data: dict) -> None`，用于推送各阶段进度。

### 3.2 Pipeline 步骤

```
输入: url_or_bvid
    |
    v
1. 提取 BV 号 (BilibiliClient.extract_bvid)
    |
    v
2. 去重检查 (video_repo 按 platform + video_id 查询)
   -> 已存在且 status=completed: 直接返回已有总结
   -> 已存在且 status=failed: 重置状态为 processing，继续
    |
    v
3. 获取视频元信息 (BilibiliClient.get_video_info)
   -> callback("info", {title, duration, author_name, cover_url})
    |
    v
4. 创建 VideoSummary 实体 (status=processing)
    |
    v
5. 获取字幕 (BilibiliClient.get_video_subtitle)
   -> callback("subtitle", {available: bool, char_count: int})
    |
    +--- 有字幕 ---> summary_type = "subtitle"
    |
    +--- 无字幕 ---> 6. ASR Pipeline
                         -> callback("asr", {step: "download" | "segment" | "transcribe", ...})
                         -> summary_type = "asr"
    |
    v
7. 保存字幕原文到对象存储
   -> storage.save_file(subtitle_path, text/json)
    |
    v
8. 构建总结 Prompt，调用 LLM 生成总结
   -> callback("summarize", {model: str})
   -> 将字幕文本（前 30000 字符）+ 视频标题发送给 LLM
   -> 获取 Markdown 格式的总结内容
    |
    v
9. 更新 VideoSummary 实体
   -> summary_content = LLM 输出
   -> status = "completed"
   -> video_repo.update(entity)
   -> callback("done", {summary_id, duration_sec})
```

### 3.3 错误处理

Pipeline 中任何步骤失败时：

- 将 VideoSummary 的 status 更新为 `"failed"`，error_message 记录错误信息
- 通过 callback 发送 `("error", {message: str})` 事件
- 不抛出异常到调用者（面板和 agent 工具都需要优雅处理失败）

BilibiliClient 层的异常（NotFoundError、NetworkError 等）在 VideoService 内部捕获并转为上述失败处理。

### 3.4 总结 Prompt

移植自 bilibili-summary 的 prompt 设计，指导 LLM 生成三段式结构化总结：

1. **内容整理** -- 将口语化的字幕整理为书面表达，去除冗余但不遗漏实质内容
2. **核心观点** -- 逐条列出视频中的重要观点，每条附带支撑性的例子或数据
3. **行动建议** -- 如果视频包含可操作的方法论，列出具体行动步骤；否则省略

Prompt 使用中文，输入为视频标题和字幕文本（截取前 30000 字符），LLM 最大输出 token 数为 8192。

## 4. CRUD 操作

### 4.1 查询

| 方法 | 说明 |
|------|------|
| `get(summary_id) -> VideoSummary` | 获取单个总结，不存在时抛出 VideoSummaryNotFoundError |
| `list_by_notebook(notebook_id) -> list[VideoSummary]` | 获取 notebook 下所有关联的总结 |
| `list_all() -> list[VideoSummary]` | 获取所有总结（管理用途） |

### 4.2 删除

`delete(summary_id)` 同时执行：
- 从数据库删除 VideoSummary 记录
- 从对象存储删除字幕文件（通过 subtitle_path）

### 4.3 Notebook 关联

| 方法 | 说明 |
|------|------|
| `associate_notebook(summary_id, notebook_id)` | 将总结关联到 notebook |
| `disassociate_notebook(summary_id)` | 取消关联（notebook_id 置为 NULL） |

关联操作只修改 video_summaries 表的 notebook_id 字段，不涉及其他表的变更。

### 4.4 Document 关联

| 方法 | 说明 |
|------|------|
| `add_document_tag(summary_id, document_id)` | 添加 document 关联 |
| `remove_document_tag(summary_id, document_id)` | 移除 document 关联 |

添加关联前通过 ref_repo 校验 document 是否属于总结所在的 notebook。如果总结未关联 notebook，则不允许添加 document 关联。

## 5. 视频信息代理

VideoService 也提供不触发总结的视频信息查询方法，直接委托给 BilibiliClient：

| 方法 | 委托目标 |
|------|---------|
| `fetch_video_info(url_or_bvid)` | BilibiliClient.get_video_info |
| `search_videos(keyword, page)` | BilibiliClient.search_video |
| `get_hot_videos(page)` | BilibiliClient.get_hot_videos |
| `get_rank_videos(day)` | BilibiliClient.get_rank_videos |
| `get_related_videos(bvid)` | BilibiliClient.get_related_videos |

这些方法不创建或修改 VideoSummary 实体，仅做数据的获取和转发。

## 6. 自定义异常

| 异常 | 场景 |
|------|------|
| VideoSummaryNotFoundError | 查询不存在的总结 |
| VideoAlreadyExistsError | 同一视频重复提交总结（去重检查） |
| VideoSummarizeError | 总结 pipeline 内部错误（包装 BiliError 等底层异常） |
