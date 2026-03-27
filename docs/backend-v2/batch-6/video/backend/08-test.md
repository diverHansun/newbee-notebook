# Video 模块：验证策略

## 1. 测试范围

### 1.1 覆盖范围

- BilibiliClient 的数据规范化和异常映射
- VideoService 的总结 pipeline 和 CRUD 逻辑
- VideoSkillProvider 的 manifest 构建和工具执行
- Video REST API 的端点行为
- ASR pipeline 的分段和拼接逻辑

### 1.2 不覆盖

- bilibili-api-python SDK 本身的正确性（第三方库）
- 真实 B 站 API 的可用性和响应格式变更（集成测试环境不稳定）
- 真实 LLM 的生成质量（prompt 效果需要人工评估）
- 真实 GLM-ASR 服务的转录质量
- 前端 Video 面板的 UI 交互

## 2. 关键场景

### 2.1 总结 Pipeline -- 字幕路径

验证正常流程：BV 号提取 -> 视频信息获取 -> 字幕提取成功 -> LLM 生成总结 -> 持久化 -> 返回 completed 状态的 VideoSummary。

mock 对象：BilibiliClient（返回预设的视频信息和字幕文本）、llm_client（返回预设的总结文本）、StorageBackend（验证字幕写入调用）。

### 2.2 总结 Pipeline -- ASR 降级路径

验证字幕不可用时的降级流程：字幕提取返回空 -> 触发 ASR pipeline -> 音频下载 -> 分段 -> 转录 -> LLM 生成总结。

mock 对象：BilibiliClient.get_video_subtitle 返回空、ASR 服务返回预设文本。

### 2.3 总结 Pipeline -- 去重

验证同一视频不会重复总结：首次总结成功 -> 第二次提交同一 BV 号 -> 直接返回已有总结而非重新执行 pipeline。

### 2.4 总结 Pipeline -- 失败恢复

验证失败后的重试行为：首次总结失败（status=failed）-> 再次提交同一 BV 号 -> 重置状态为 processing 并重新执行 pipeline。

### 2.5 Notebook 关联生命周期

验证关联操作的正确性：创建独立总结（notebook_id=None）-> 关联到 notebook -> 按 notebook 列表查询可见 -> 取消关联 -> 列表查询不可见但总结仍存在。

### 2.6 Document 关联校验

验证 document 关联的前置校验：总结未关联 notebook 时添加 document 关联 -> 应拒绝。总结已关联 notebook -> 添加不属于该 notebook 的 document -> 应拒绝。

### 2.7 Skill 工具执行

验证 VideoSkillProvider 的各工具在正常和异常情况下的行为：

- summarize_video 工具成功时返回 ToolCallResult 包含总结内容和 summary_id
- summarize_video 工具失败时返回 ToolCallResult 包含 error 字段而非抛出异常
- delete_summary 工具在 confirmation_required 集合中
- list_summaries 工具按 notebook_id 过滤

### 2.8 BV 号提取

验证 extract_bvid 对各种输入格式的处理：

- 标准 URL：`https://www.bilibili.com/video/BV1xx411c7mD`
- 短链：`https://b23.tv/xxxxx`（需验证是否支持或明确不支持）
- 纯 BV 号：`BV1xx411c7mD`
- 包含额外参数的 URL：`https://www.bilibili.com/video/BV1xx411c7mD?p=2&t=120`
- 无效输入：应抛出 InvalidBvidError

### 2.9 数据规范化

验证 payloads 模块的 normalize 函数对边界输入的处理：

- 缺失字段（部分 API 返回可能不包含某些字段）
- 类型不一致（duration 可能是 int、float 或 string）
- HTML 标签清除（搜索结果的 title 包含 `<em>` 标签）

## 3. 集成点

### 3.1 SkillRegistry 集成

验证 VideoSkillProvider 在 SkillRegistry 中的注册和匹配：

- `/video 搜索机器学习` -> 匹配到 VideoSkillProvider，cleaned_message = `"搜索机器学习"`
- `/note 创建笔记` -> 不匹配 VideoSkillProvider
- `/videoabc` -> 不匹配（需要空格或结尾分隔）

### 3.2 ChatService 集成

验证 `/video` 命令通过 ChatService -> SkillRegistry -> VideoSkillProvider -> AgentLoop 的完整链路。mock LLM 返回预设的工具调用决策，验证工具执行结果正确传递。

### 3.3 依赖注入链

验证 `get_video_service` 和 `get_runtime_skill_registry_dep` 的依赖注入链路正确组装，VideoSkillProvider 能获取到有效的 VideoService 实例。

## 4. 验证策略

### 4.1 Mock 策略

| 外部依赖 | Mock 方式 | 说明 |
|---------|----------|------|
| bilibili-api-python | Mock BilibiliClient 方法 | 返回预设的规范化数据 |
| LLM 服务 | Mock llm_client.chat/chat_stream | 返回预设的总结文本 |
| GLM-ASR 服务 | Mock aiohttp.ClientSession | 返回预设的转录文本 |
| MinIO/StorageBackend | Mock save_file/read_file | 验证调用参数，不实际写入 |
| PostgreSQL | 使用测试数据库或 mock repository | 视情况选择 |

### 4.2 测试分层

| 层 | 范围 | 工具 |
|----|------|------|
| 单元测试 | payloads 规范化、BV 号提取、异常映射 | pytest |
| 服务测试 | VideoService 方法（mock 外部依赖） | pytest + pytest-asyncio |
| Skill 测试 | VideoSkillProvider 的 manifest 和工具执行 | pytest + pytest-asyncio |
| API 测试 | REST 端点的请求/响应行为 | pytest + httpx.AsyncClient |

### 4.3 不做自动化的部分

- **真实 B 站 API 集成测试** -- B 站 API 有频率限制且返回格式可能变更，不适合 CI 自动化。手动验证即可。
- **LLM 总结质量评估** -- prompt 效果需要人工判断，不适合断言驱动的自动化测试。
- **ASR 转录准确率** -- 依赖外部 ASR 服务，不稳定。以 mock 测试覆盖流程正确性。
- **SSE 端点的前端消费** -- SSE 事件格式的正确性在 API 测试中验证，前端渲染属于前端测试范围。
