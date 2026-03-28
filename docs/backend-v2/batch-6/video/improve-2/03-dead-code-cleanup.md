# tools.py 死代码清理

## 问题描述

improve-1 将 12 个视频 agent 工具合并为 9 个后，`tools.py` 中残留了 5 个旧的独立
工具构建函数。这些函数不再被 `provider.py` 引用，也不被项目中其他任何位置引用。

---

## 死代码清单

| 函数名 | tools.py 行号 | 已被取代 |
|--------|--------------|----------|
| `build_search_video_tool` | L103-132 | `build_discover_videos_tool` (source="search") |
| `build_get_video_subtitle_tool` | L206-227 | `build_get_video_content_tool` (type="subtitle") |
| `build_get_hot_videos_tool` | L333-352 | `build_discover_videos_tool` (source="hot") |
| `build_get_rank_videos_tool` | L355-374 | `build_discover_videos_tool` (source="rank") |
| `build_get_related_videos_tool` | L377-396 | `build_discover_videos_tool` (source="related") |

---

## 引用验证

### provider.py 当前 import (provider.py:8-18)

```python
from newbee_notebook.skills.video.tools import (
    build_associate_notebook_tool,
    build_delete_summary_tool,
    build_discover_videos_tool,
    build_disassociate_notebook_tool,
    build_get_video_content_tool,
    build_get_video_info_tool,
    build_list_summaries_tool,
    build_read_summary_tool,
    build_summarize_video_tool,
)
```

以上 9 个函数即为全部活跃工具。5 个死代码函数不在 import 列表中。

### 项目全局搜索确认

以下函数名在 `provider.py` 之外无任何引用:
- `build_search_video_tool` -- 无引用
- `build_get_video_subtitle_tool` -- 无引用
- `build_get_hot_videos_tool` -- 无引用
- `build_get_rank_videos_tool` -- 无引用
- `build_get_related_videos_tool` -- 无引用

---

## 修改方案

直接删除以下 5 个函数定义及其内部的 `execute` 闭包:

1. `build_search_video_tool` (tools.py:103-132)
2. `build_get_video_subtitle_tool` (tools.py:206-227)
3. `build_get_hot_videos_tool` (tools.py:333-352)
4. `build_get_rank_videos_tool` (tools.py:355-374)
5. `build_get_related_videos_tool` (tools.py:377-396)

删除后 tools.py 将只保留 9 个活跃工具构建函数 + 3 个辅助函数 (`_safe_error_result`,
`_format_summary_item`, `_format_video_result_lines`)。

---

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/skills/video/tools.py` | 删除 5 个未引用的工具构建函数 |
