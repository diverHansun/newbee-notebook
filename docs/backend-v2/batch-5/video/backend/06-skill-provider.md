# Video 模块：VideoSkillProvider 与工具定义

## 1. 概述

VideoSkillProvider 遵循 batch-3 建立的 SkillProvider 协议，将 VideoService 的能力适配为 agent 可调用的工具集。当用户在 chat 中输入 `/video` 前缀时，SkillRegistry 匹配到 VideoSkillProvider，构建 SkillManifest 并注入 agent loop。

## 2. Provider 结构

```python
class VideoSkillProvider:
    def __init__(self, *, video_service: VideoService) -> None: ...

    @property
    def skill_name(self) -> str:
        return "video"

    @property
    def slash_commands(self) -> list[str]:
        return ["/video"]

    def build_manifest(self, context: SkillContext) -> SkillManifest:
        return SkillManifest(
            name="video",
            slash_command="/video",
            description="视频搜索、信息查询与内容总结",
            system_prompt_addition=SYSTEM_PROMPT_ADDITION,
            tools=self._build_tools(context),
            confirmation_required=frozenset({
                "delete_summary",
                "disassociate_notebook",
            }),
            force_first_tool_call=True,
        )
```

设计要点：

- **force_first_tool_call = True** -- 确保 agent 先调用工具再生成文本，防止 agent 空谈而不执行
- **confirmation_required** -- 仅删除总结和取消 notebook 关联需要用户确认，总结生成等操作不需要确认

## 3. System Prompt Addition

注入到 agent 系统提示词中的补充说明：

```
当前已激活 /video 视频技能。你可以使用以下工具：

- search_video: 通过关键词搜索 Bilibili 视频
- get_video_info: 获取指定视频的元信息（标题、时长、UP主、统计数据等）
- get_video_subtitle: 获取视频字幕文本
- summarize_video: 对视频内容进行 AI 总结，结果会保存并显示在 Video 面板
- list_summaries: 列出当前 notebook 中已有的视频总结
- read_summary: 读取某个视频总结的详细内容
- delete_summary: 删除一个视频总结（需要用户确认）
- get_hot_videos: 获取 Bilibili 热门视频
- get_rank_videos: 获取 Bilibili 排行榜视频
- get_related_videos: 获取某个视频的相关推荐
- associate_notebook: 将视频总结关联到当前 notebook
- disassociate_notebook: 取消视频总结与 notebook 的关联（需要用户确认）

使用指南：
- 当用户提供了具体的视频 URL 或 BV 号时，先用 get_video_info 获取信息，再根据用户需求决定是否调用 summarize_video
- 当用户想搜索特定主题的视频时，使用 search_video
- 当用户想发现热门或高质量内容时，使用 get_hot_videos 或 get_rank_videos
- summarize_video 会启动完整的总结流程（字幕提取/ASR转录 + AI总结），耗时较长，应在调用后告知用户正在处理
```

## 4. 工具定义

### 4.1 工具清单

| 工具名 | 工厂函数 | 必需参数 | 确认 | 说明 |
|--------|---------|---------|------|------|
| search_video | build_search_video_tool | keyword | 否 | 关键词搜索 |
| get_video_info | build_get_video_info_tool | url_or_bvid | 否 | 查询视频元信息 |
| get_video_subtitle | build_get_video_subtitle_tool | url_or_bvid | 否 | 获取字幕文本 |
| summarize_video | build_summarize_video_tool | url_or_bvid | 否 | 触发完整总结 |
| list_summaries | build_list_summaries_tool | （无） | 否 | 列出已有总结 |
| read_summary | build_read_summary_tool | summary_id | 否 | 读取总结内容 |
| delete_summary | build_delete_summary_tool | summary_id | 是 | 删除总结 |
| get_hot_videos | build_get_hot_videos_tool | （无） | 否 | 热门视频 |
| get_rank_videos | build_get_rank_videos_tool | （无） | 否 | 排行榜 |
| get_related_videos | build_get_related_videos_tool | url_or_bvid | 否 | 相关推荐 |
| associate_notebook | build_associate_notebook_tool | summary_id | 否 | 关联 notebook |
| disassociate_notebook | build_disassociate_notebook_tool | summary_id | 是 | 取消关联 |

### 4.2 工具实现模式

所有工具遵循现有 skill 的工厂函数模式：闭包捕获 service 和 notebook_id，返回 ToolDefinition。

```python
def build_summarize_video_tool(
    *, service: VideoService, notebook_id: str
) -> ToolDefinition:
    async def _execute(args: dict[str, Any]) -> ToolCallResult:
        try:
            summary = await service.summarize(
                url_or_bvid=args["url_or_bvid"],
                notebook_id=notebook_id,
            )
            return ToolCallResult(
                content=f"已完成视频总结: {summary.title}\n\n{summary.summary_content}",
                metadata={"summary_id": summary.summary_id},
            )
        except VideoSummaryNotFoundError as exc:
            return ToolCallResult(content=str(exc), error="not_found")
        except Exception as exc:
            return ToolCallResult(content=f"总结失败: {exc}", error="summarize_failed")

    return ToolDefinition(
        name="summarize_video",
        description="对 Bilibili 视频内容进行 AI 总结。输入视频 URL 或 BV 号。",
        parameters={
            "type": "object",
            "properties": {
                "url_or_bvid": {
                    "type": "string",
                    "description": "视频 URL 或 BV 号",
                }
            },
            "required": ["url_or_bvid"],
        },
        execute=_execute,
    )
```

关键规则：

- 工具内部不抛出异常，所有错误通过 ToolCallResult 的 error 字段返回
- metadata 用于传递结构化数据（如 summary_id），前端可据此跳转到对应的总结详情

### 4.3 summarize_video 工具的特殊处理

当通过 agent 调用 `summarize_video` 时，不传入 `progress_callback`。agent 会同步等待总结完成后获取结果。这与面板 UI 的 SSE 进度推送路径不同。

如果总结耗时超过 agent loop 的工具调用超时限制，工具应捕获超时异常并返回友好的错误信息，建议用户在 Video 面板中直接操作。

## 5. 注册

在 `api/dependencies.py` 的 `get_runtime_skill_registry_dep()` 中注册：

```python
async def get_runtime_skill_registry_dep(
    note_service: NoteService = Depends(get_note_service),
    mark_service: MarkService = Depends(get_mark_service),
    diagram_service: DiagramService = Depends(get_diagram_service),
    video_service: VideoService = Depends(get_video_service),  # 新增
) -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(NoteSkillProvider(...))
    registry.register(DiagramSkillProvider(...))
    registry.register(VideoSkillProvider(video_service=video_service))  # 新增
    return registry
```

## 6. 与现有 Skill 的对比

| 维度 | NoteSkillProvider | DiagramSkillProvider | VideoSkillProvider |
|------|-------------------|---------------------|-------------------|
| slash 命令 | /note | /diagram | /video |
| 工具数量 | 8 | 7 | 12 |
| force_first_tool_call | True | True | True |
| required_tool_call_before_response | 无 | 动态（create_diagram 或 None） | 无 |
| confirmation_required | update_note, delete_note, disassociate | confirm_diagram_type, update, delete | delete_summary, disassociate_notebook |
| 外部服务依赖 | 无 | 无 | BilibiliClient, LLM（通过 VideoService） |
| 长时工具 | 无 | 无 | summarize_video（30s-2min） |

VideoSkillProvider 的主要差异在于 summarize_video 是长时工具，且依赖外部 B 站 API。
