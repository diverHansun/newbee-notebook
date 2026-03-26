# Video 模块：架构设计

## 1. 架构总览

```
Studio Video 面板                    Main Chat 面板
  |                                    |
  | POST /api/v1/videos/summarize      | 用户输入: "/video 总结这个视频 BV..."
  | (独立 SSE 端点)                     |
  v                                    v
VideoRouter                        ChatService
  |                                    |  match_command("/video ...")
  |                                    |  -> VideoSkillProvider
  |                                    |  -> build_manifest(SkillContext)
  |                                    v
  |                                AgentLoop
  |                                    |  调用 summarize_video / search_video 等工具
  |                                    |  工具内部委托 VideoService
  |                                    v
  +------ 共享 -------> VideoService <------+
                            |
              +-------------+-------------+
              |             |             |
        BilibiliClient  LLM Client    StorageBackend
              |             |             |
        bilibili-api   OpenAI/Zhipu    MinIO/Local
              |
        +-----+-----+
        |           |
    字幕提取    ASR Pipeline
                    |
              +-----+-----+
              |           |
          音频下载    GLM-ASR 转录
          (PyAV)
```

两条触发路径（面板直接操作 和 agent 工具调用）汇聚到同一个 VideoService，保证业务逻辑的一致性。

## 2. 核心组件

### 2.1 基础设施层（infrastructure/bilibili/）

独立的 Bilibili 平台适配层，封装所有与 B 站 API 的交互细节。

| 组件 | 职责 |
|------|------|
| BilibiliClient | 封装 bilibili-api-python SDK，提供规范化的异步方法 |
| payloads | 数据规范化函数，将原始 API 响应转为稳定的内部结构 |
| exceptions | B 站相关异常层级（BiliError 及其子类） |
| auth | B 站 QR 码登录和凭证管理 |
| asr | ASR 转录 pipeline（音频下载、分段、并发转录） |

这一层的设计保证了平台隔离：未来接入 YouTube 时，新增 `infrastructure/youtube/` 即可，不影响上层逻辑。

### 2.2 领域层（domain/entities/）

VideoSummary 实体是本模块的核心领域对象，承载视频元信息和总结内容。详见 03-data-model.md。

### 2.3 应用服务层（application/services/）

VideoService 负责编排总结 pipeline 和管理 VideoSummary 实体的生命周期。

关键设计：`summarize()` 方法接受一个可选的 `progress_callback` 参数。面板 UI 调用时传入 SSE 事件发送函数；agent 工具调用时可不传（agent 自然会等待工具返回结果）。这使得同一个 pipeline 逻辑可以服务两条触发路径。

### 2.4 Skill 层（skills/video/）

VideoSkillProvider 遵循现有的 SkillProvider 协议，构建包含视频相关工具的 SkillManifest。当 `/video` 命令激活时，工具集被注入到 agent loop 中。

### 2.5 API 层（api/routers/）

两个 router：

- `videos.py` -- VideoSummary 的 CRUD、总结触发（SSE）、视频信息查询
- `bilibili_auth.py` -- B 站 QR 登录、登出、状态查询

## 3. 设计模式与决策

### 3.1 沿用现有 Skill 体系

VideoSkillProvider 与 NoteSkillProvider、DiagramSkillProvider 遵循完全相同的模式：

- 实现 SkillProvider 协议
- 在 `api/dependencies.py` 的 `get_runtime_skill_registry_dep()` 中注册
- slash 命令激活时强制切换到 AGENT 模式
- 破坏性操作通过 `confirmation_required` 声明

选择这个模式的原因：复用已验证的 skill 基础设施，降低学习和维护成本。

### 3.2 总结 Pipeline 独立于 Agent Loop

VideoService.summarize() 是一个自包含的异步方法，不依赖 AgentLoop 运行。原因：

- 总结 pipeline 是长时任务（字幕提取 + ASR 可能需要 30s-2min），而 agent loop 的单次工具调用有超时限制
- 面板 UI 需要独立的 SSE 进度推送，不能复用 agent 的事件流
- 解耦后，面板总结和 agent 对话可以并行，互不阻塞

当 agent 通过 `summarize_video` 工具调用时，工具内部同步调用 `VideoService.summarize()` 并等待结果。如果未来总结任务变得更重（长视频、批量处理），可以升级为 Celery 异步任务。

### 3.3 平台隔离

所有 Bilibili 特有逻辑集中在 `infrastructure/bilibili/` 中。VideoService 通过 BilibiliClient 接口与平台交互，不直接依赖 bilibili-api-python SDK。

未来扩展路径：新增 `infrastructure/youtube/` 实现 YouTubeClient，在 VideoService 中通过 platform 字段路由到对应的 client。

### 3.4 LLM 复用

总结生成复用项目现有的 LLM 配置（llm.yaml 中的 OpenAI/ZhipuAI 提供者）。总结 prompt 作为 VideoService 内部逻辑，不需要经过 agent loop 的工具调用协议。

保留 B 站 AI 摘要接口（`get_video_ai_conclusion`）作为补充信息源，但不作为主要总结方式。

## 4. 模块结构与文件布局

```
newbee_notebook/
├── infrastructure/
│   └── bilibili/                          # B站基础设施层
│       ├── __init__.py
│       ├── client.py                      # BilibiliClient
│       ├── payloads.py                    # 数据规范化函数
│       ├── exceptions.py                  # 异常层级
│       ├── auth.py                        # QR 登录与凭证管理
│       └── asr.py                         # ASR 转录 pipeline
│
├── domain/
│   ├── entities/
│   │   └── video_summary.py               # VideoSummary 实体
│   └── repositories/
│       └── video_summary_repository.py    # Repository ABC
│
├── infrastructure/
│   └── persistence/
│       └── repositories/
│           └── video_summary_repo_impl.py # SQLAlchemy 实现
│
├── application/
│   └── services/
│       └── video_service.py               # VideoService
│
├── skills/
│   └── video/
│       ├── __init__.py                    # 导出 VideoSkillProvider
│       ├── provider.py                    # VideoSkillProvider
│       └── tools.py                       # 工具工厂函数
│
└── api/
    ├── routers/
    │   ├── videos.py                      # Video REST API + SSE
    │   └── bilibili_auth.py               # B站认证 API
    └── models/
        └── video_models.py                # Pydantic 请求/响应模型
```

## 5. 架构约束与权衡

### 5.1 不使用 Celery 异步任务（当前阶段）

考虑过将总结 pipeline 放入 Celery worker 异步执行，这样可以避免长任务阻塞和支持批量处理。但当前阶段选择在请求进程内同步执行，原因：

- 单视频总结的耗时在可接受范围内（通常 30s-90s）
- 避免引入任务状态机的额外复杂度
- 面板 UI 的 SSE 进度推送在同步模式下实现更简单

如果后续需要支持批量总结或超长视频，再升级为 Celery 方案。

### 5.2 字幕原文存对象存储而非数据库

字幕文本可能很长（一个 1 小时视频的字幕约 50-100KB），且不需要被频繁查询或搜索。选择存储到 MinIO（与 Diagram 的 content_path 模式一致），数据库只保存路径引用。

总结内容（summary_content）则存数据库内联，因为它通常 2-5KB 且需要被列表页预览和全文读取。

### 5.3 不扩展 SkillRegistry 的匹配逻辑

讨论过让 SkillRegistry 扫描 prompt 中的关键词（如"b站"、"bilibili"、"视频总结"）自动激活 video skill。选择不实现，原因：

- 关键词匹配容易误触发，降低用户对 agent 行为的可控性
- 与现有 `/note`、`/diagram` 的显式触发模式不一致
- `/video` 前缀足够简洁，不会增加用户负担
