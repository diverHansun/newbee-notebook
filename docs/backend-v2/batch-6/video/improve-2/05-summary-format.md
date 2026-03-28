# 总结内容 Markdown 格式规范

## 问题描述

### 存储格式未明确

当前 `summary_content` 字段 (DB TEXT) 存储的是 LLM 输出的文本。LLM 实际返回
markdown 格式 (标题、列表、分段等)，但代码中没有任何地方明确约定这一点。

### 提示词问题

当前 `_build_summary_messages` (video_service.py:282-302) 的 system prompt:

```python
{
    "role": "system",
    "content": "You summarize Bilibili videos into concise markdown notes.",
}
```

问题:
1. 虽然提到了 "markdown notes"，但没有明确格式要求 (标题层级、结构等)
2. 全英文提示词，中文视频容易产生英文总结
3. 没有规范输出结构，不同视频的总结格式可能差异较大

### transcript 存储无问题

字幕/ASR 转录文本存储为 `text/plain` 格式 (`videos/transcripts/{bvid}.txt`)，
这是正确的 -- 原始转录就是纯文本，无需 markdown。

---

## 修改方案

### 1. 更新 system prompt

将 `_build_summary_messages` 的 system prompt 替换为带明确格式要求的中文提示词:

```python
@staticmethod
def _build_summary_messages(
    *,
    info: dict[str, Any],
    transcript_text: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是一个视频内容总结助手。根据提供的视频信息和字幕文本，"
                "生成结构化的 Markdown 格式总结笔记。\n\n"
                "输出格式要求:\n"
                "- 使用中文撰写\n"
                "- 以二级标题 (##) 作为主要分节标题\n"
                "- 包含以下部分: 概述、核心内容 (按主题分段)、要点总结\n"
                "- 重要术语或关键概念使用加粗标记\n"
                "- 列举要点时使用无序列表\n"
                "- 保持简洁，避免冗余重复"
            ),
        },
        {
            "role": "user",
            "content": (
                f"标题: {info.get('title', '')}\n"
                f"UP主: {info.get('uploader_name', '')}\n"
                f"时长: {info.get('duration_seconds', 0)} 秒\n\n"
                f"字幕文本:\n{transcript_text}"
            ),
        },
    ]
```

变更说明:
- system prompt 改为中文，明确要求中文输出
- 规范 markdown 结构: 二级标题分节、无序列表、加粗关键词
- 定义输出分段: 概述 / 核心内容 / 要点总结
- user message 的字段标签也改为中文，保持一致

### 2. 关于 i18n

当前方案将提示词固定为中文输出。后续 i18n 系统提示词国际化时，可以:
- 根据用户语言设置动态选择提示词模板
- 或在 prompt 中加入语言参数 (如 `language: zh-CN`)

此次不实现 i18n，仅将提示词从英文改为中文，解决当前中文视频输出英文总结的问题。

---

## 格式约定

| 内容类型 | 存储位置 | 格式 | content-type |
|----------|----------|------|-------------|
| transcript (字幕/ASR原文) | 对象存储 `videos/transcripts/{bvid}.txt` | 纯文本 | `text/plain; charset=utf-8` |
| summary_content (LLM总结) | 数据库 `video_summaries.summary_content` | Markdown | N/A (DB TEXT 字段) |

两者格式不同，这是合理的:
- transcript 是原始素材，纯文本即可
- summary 是 LLM 生成的结构化内容，markdown 更适合前端渲染和 agent 读取

---

## 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `newbee_notebook/application/services/video_service.py` | 更新 `_build_summary_messages` 的 system prompt 和 user message |
