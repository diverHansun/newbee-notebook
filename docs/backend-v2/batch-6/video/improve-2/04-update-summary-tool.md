# 新增 update_summary Agent 工具

## 问题描述

当前 video skill 的 9 个 agent 工具覆盖了视频发现、元数据查询、内容获取、总结生成、
列表查看、读取总结、删除总结、笔记本关联/解关联。

缺少的关键能力: **修改已有总结的内容**。

用户在 agent 会话中可能希望:
- 让 agent 基于补充信息更新总结
- 要求 agent 修正总结中的错误
- 让 agent 将总结翻译或改写为不同风格

目前只能删除旧总结再重新生成，无法原地编辑。

---

## 设计方案

### 1. VideoService 新增方法

在 `video_service.py` 中添加 `update_summary_content` 方法:

```python
async def update_summary_content(self, summary_id: str, content: str) -> VideoSummary:
    """Update the markdown summary content of an existing video summary."""
    summary = await self.get(summary_id)
    if summary.status != "completed":
        raise ValueError(
            f"Cannot update summary in status '{summary.status}', expected 'completed'"
        )
    summary.summary_content = content
    summary.touch()
    summary = await self._video_repo.update(summary)
    await self._video_repo.commit()
    return summary
```

约束:
- 只允许更新 `status="completed"` 的总结，不允许修改正在处理或失败的总结
- 更新内容直接写入 DB 的 `summary_content` 字段
- 调用 `touch()` 更新时间戳

### 2. tools.py 新增工具构建函数

```python
def build_update_summary_tool(service: VideoService) -> ToolDefinition:
    async def execute(args: dict[str, Any]) -> ToolCallResult:
        summary_id = str(args.get("summary_id") or "").strip()
        content = str(args.get("content") or "").strip()
        if not content:
            return _safe_error_result(
                "update_summary requires non-empty content",
                "video_update_empty_content",
            )
        try:
            summary = await service.update_summary_content(summary_id, content)
        except VideoSummaryNotFoundError as exc:
            return _safe_error_result(str(exc), "video_summary_not_found")
        except ValueError as exc:
            return _safe_error_result(str(exc), "video_update_invalid_status")
        except Exception as exc:
            return _safe_error_result(
                f"Failed to update summary: {exc}",
                "video_update_failed",
            )
        return ToolCallResult(
            content=f"Video summary updated: {summary.title}",
            metadata={"summary_id": summary.summary_id},
        )

    return ToolDefinition(
        name="update_summary",
        description="Update the markdown content of a saved video summary.",
        parameters={
            "type": "object",
            "properties": {
                "summary_id": {
                    "type": "string",
                    "description": "Summary ID of the video summary to update",
                },
                "content": {
                    "type": "string",
                    "description": "New markdown content for the summary",
                },
            },
            "required": ["summary_id", "content"],
        },
        execute=execute,
    )
```

### 3. provider.py 注册工具

在 `VideoSkillProvider.build_manifest` 中:

```python
from newbee_notebook.skills.video.tools import (
    # ... existing imports ...
    build_update_summary_tool,
)

# tools 列表中添加:
tools=[
    # ... existing 9 tools ...
    build_update_summary_tool(service=self._video_service),
],
```

### 4. ConfirmCard 配置

`update_summary` 是修改操作，需要用户确认。在 `build_manifest` 中注册:

```python
confirmation_required=frozenset({
    "delete_summary",
    "disassociate_notebook",
    "update_summary",          # 新增
}),
confirmation_meta={
    "delete_summary": ConfirmationMeta(action_type="delete", target_type="video"),
    "disassociate_notebook": ConfirmationMeta(action_type="delete", target_type="video"),
    "update_summary": ConfirmationMeta(     # 新增
        action_type="update",
        target_type="video",
    ),
},
```

`action_type="update"` 在 `ConfirmationMeta` 的约定中已被支持 (contracts.py:21 注释:
`create | update | delete | confirm`)。

### 5. System Prompt 更新

在 `system_prompt_addition` 中补充 `update_summary` 的使用指引:

```
"Use update_summary to modify the content of an existing completed summary. "
"Always read_summary first to get the current content before updating.\n"
```

---

## 工具数变化

| 阶段 | 工具数 |
|------|--------|
| improve-1 合并前 | 12 |
| improve-1 合并后 | 9 |
| improve-2 新增后 | 10 |

10 个工具仍在 note(8)/diagram(7) 的合理范围内，不会造成 agent 上下文污染。

---

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/application/services/video_service.py` | 新增 `update_summary_content` 方法 |
| `newbee_notebook/skills/video/tools.py` | 新增 `build_update_summary_tool` 函数 |
| `newbee_notebook/skills/video/provider.py` | 注册工具，配置 confirmation_required 和 confirmation_meta |
