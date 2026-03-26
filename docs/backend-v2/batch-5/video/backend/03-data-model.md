# Video 模块：数据模型

## 数据库表：video_summaries

对齐说明：

- 数据库层沿用现有表风格，主键使用 `id`
- 外键指向 `notebooks(id)`，允许 NULL（总结可独立于 notebook 存在）
- 领域实体和 API 响应暴露 `summary_id`，通过 repository / schema 映射数据库列 `id`

```sql
CREATE TABLE video_summaries (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id     UUID        REFERENCES notebooks(id) ON DELETE SET NULL,
    -- 可选关联，NULL 表示独立总结，删除 notebook 时置空而非级联删除
    platform        TEXT        NOT NULL DEFAULT 'bilibili',
    -- 视频来源平台，当前仅 'bilibili'，预留 'youtube' 等
    video_id        TEXT        NOT NULL,
    -- 平台侧的视频标识符，B站为 BV 号（如 'BV1xx411c7mD'）
    url             TEXT        NOT NULL,
    -- 完整视频链接
    title           TEXT        NOT NULL,
    cover_url       TEXT        NOT NULL DEFAULT '',
    -- 视频封面图 URL
    duration        INTEGER     NOT NULL DEFAULT 0,
    -- 视频时长（秒）
    author_name     TEXT        NOT NULL DEFAULT '',
    author_id       TEXT        NOT NULL DEFAULT '',
    -- UP 主 UID（字符串存储，兼容不同平台的 ID 格式）
    summary_content TEXT        NOT NULL DEFAULT '',
    -- AI 生成的总结文本（Markdown 格式），存数据库内联
    subtitle_path   TEXT        NOT NULL DEFAULT '',
    -- 字幕原文在对象存储中的路径，格式见下方存储路径说明
    summary_type    TEXT        NOT NULL DEFAULT 'subtitle',
    -- 总结来源标记：'subtitle'（字幕） | 'asr'（语音识别） | 'bilibili_ai'（B站AI）
    status          TEXT        NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message   TEXT        NOT NULL DEFAULT '',
    -- 失败时的错误信息
    document_ids    UUID[]      NOT NULL DEFAULT '{}',
    -- 用户手动关联的文档 ID 列表
    tags            TEXT[]      NOT NULL DEFAULT '{}',
    -- 视频标签（来自平台元数据）
    stats           JSONB       NOT NULL DEFAULT '{}',
    -- 视频统计数据，结构见下方说明
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_video_summaries_notebook_id  ON video_summaries(notebook_id);
CREATE INDEX idx_video_summaries_platform_vid ON video_summaries(platform, video_id);
CREATE INDEX idx_video_summaries_document_ids ON video_summaries USING GIN(document_ids);
CREATE INDEX idx_video_summaries_status       ON video_summaries(status);
```

### 设计说明

- `notebook_id` 允许 NULL 并使用 `ON DELETE SET NULL`，而非 CASCADE。原因：总结是用户花费时间和 API 资源生成的内容，删除 notebook 时不应连带丢失
- `platform` + `video_id` 组合的联合索引用于去重检查（同一视频不需要重复总结）
- `status` 使用 CHECK 约束，因为状态值是固定枚举，不会扩展
- `summary_type` 不加 CHECK 约束，因为未来可能新增类型（如 multimodal 图像识别）
- `stats` 使用 JSONB 存储，不单独建列，因为统计数据结构可能随平台不同而不同
- `document_ids` 使用 GIN 索引，支持按文档 ID 反查关联的视频总结

### 级联规则

| 触发操作 | 行为 |
|---------|------|
| 删除 Notebook | video_summaries.notebook_id 置为 NULL，总结本身保留 |
| 删除 Document | 从关联总结的 document_ids 数组中移除该 document_id |
| 删除 VideoSummary | 同时删除对象存储中的字幕文件 |

## 对象存储路径

```
video-subtitles/{platform}/{video_id}.txt     # 纯文本字幕
video-subtitles/{platform}/{video_id}.json    # 带时间戳的字幕数据
```

字幕文件内容不频繁读取，主要用于：重新生成总结时复用已提取的字幕、用户查看原始字幕。

### 字幕 JSON 结构

```json
[
    {"from": 0.0, "to": 3.5, "content": "大家好"},
    {"from": 3.5, "to": 7.2, "content": "今天我们来聊一下..."}
]
```

每个条目包含起止时间（秒）和文本内容，与 bilibili-api-python 返回的字幕 body 结构对齐。

## stats 字段结构

```json
{
    "view": 125000,
    "danmaku": 3200,
    "like": 8500,
    "coin": 2100,
    "favorite": 4300,
    "share": 890
}
```

字段含义与 B 站 API 返回的 stat 对象一致。不同平台的 stats 结构可能不同，因此使用 JSONB 而非固定列。

## 领域实体

```python
@dataclass
class VideoSummary(Entity):
    summary_id:      str
    notebook_id:     str | None        # None 表示独立总结
    platform:        str               # "bilibili"
    video_id:        str               # BV 号
    url:             str
    title:           str
    cover_url:       str
    duration:        int               # 秒
    author_name:     str
    author_id:       str
    summary_content: str               # Markdown 格式的 AI 总结
    subtitle_path:   str               # 对象存储路径
    summary_type:    str               # "subtitle" | "asr" | "bilibili_ai"
    status:          str               # "pending" | "processing" | "completed" | "failed"
    error_message:   str
    document_ids:    list[str]
    tags:            list[str]
    stats:           dict
    created_at:      datetime
    updated_at:      datetime
```

继承自 Entity 基类，复用 `touch()` 方法更新 `updated_at`。

## 查询路径

| 查询场景 | 方式 |
|---------|------|
| 获取 notebook 下所有总结 | `WHERE notebook_id = ?` |
| 获取所有独立总结 | `WHERE notebook_id IS NULL` |
| 检查视频是否已总结 | `WHERE platform = ? AND video_id = ?` |
| 获取关联某文档的所有总结 | `WHERE ? = ANY(document_ids)` + GIN 索引 |
| 获取单个总结详情 | `WHERE id = ?` |
| 获取进行中的总结任务 | `WHERE status = 'processing'` |
| 获取总结的字幕原文 | 从对象存储读取 `subtitle_path` 对应文件 |
