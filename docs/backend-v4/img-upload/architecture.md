# img_upload 模块 architecture.md

本文档描述 `img_upload` 模块的内部结构与设计选择。设计严格服从 [goals-duty.md](goals-duty.md)：只服务 main 面板 agent 聊天链路、复用现有 LLM 配置、单次兜底视觉模型、当前一轮注入图片不污染历史压缩链路、永久保留原图但不持久化送 LLM 的副本、与 `generated_images` 平行不合并。

---

## 一、Architecture Overview（总体架构）

`img_upload` 模块采用"上传与发送解耦 + 视觉兜底薄层 + 当前轮单点注入"的结构。

模块由六个子组件协作完成"用户上传 → 持久化 → 在当前一轮聊天中注入 → 视觉模型校正 → 透传 LLMClient → 历史保留语义但不重传"的职责。

1. **Upload Surface（上传入口）**：在聊天 API 下增加 session 维度的上传接口；前端通过 file picker / 拖拽 / 剪贴板 / 截屏触发上传，并以两阶段流程先取得 image_id 再发送聊天请求。
2. **Chat Image Service（聊天图资产服务）**：负责校验、存储、读取 `chat_images` 资产，并提供"原图"与"送 LLM 的副本"两条读取路径。
3. **Chat Image Repository（资产仓储）**：负责把 chat_images 元数据写入 DB、查询所属 session、执行软删。
4. **Vision Policy（视觉能力裁决）**：维护 provider→视觉模型白名单与 provider→默认视觉模型映射，提供"是否具备视觉能力"与"应回退到哪个模型"两个查询。
5. **Multimodal Context Adapter（多模态当前轮装配器）**：在 ContextBuilder 的"当前一轮 user 消息"位置注入 OpenAI 兼容 content parts，仅本轮生效。
6. **Chat Pipeline Hook（聊天流水线钩子）**：在 ChatService 内部于"取得 LLMRuntimeConfig 之后、构造 LLMClient 之前"插入视觉兜底与多模态装配，对历史压缩链路保持透明。

### 高层依赖关系

```text
frontend chat-input
  -> Upload Surface
    -> Chat Image Service
      -> StorageBackend (chat-images/{session_id}/{image_id}.{ext})
      -> Chat Image Repository (chat_images row)

frontend chat-input
  -> Chat API (/chat/stream with image_ids)
    -> ChatService / SessionManager
      -> Chat Pipeline Hook
        -> Vision Policy (current model -> effective model)
        -> Multimodal Context Adapter
          -> Chat Image Service.load_for_llm (resize + base64)
          -> ContextBuilder (current user message only)
        -> LLMClient.chat_stream
          -> AsyncOpenAI (image_url content parts)
```

### 当前轮与历史轮的分界

```text
current user message
  Multimodal Context Adapter 写入 OpenAI content parts
  附上 image_url base64 part
  Vision Policy 决定本调用使用的 model

历史 user/assistant message
  StoredMessage.content 仍为 str
  仅 metadata.image_ids 保留语义
  ContextBuilder 不重新加载图，不向 LLM 重传
```

---

## 二、Design Pattern & Rationale（设计模式与理由）

### 1. Two-Phase Submission：上传与发送解耦

聊天请求与图片上传被拆成"先 POST images 取 id"与"再 POST chat 携带 ids"两个阶段。原因是 chat 端是 SSE 流式接口，对 multipart 与重复 base64 不友好；解耦后上传可并行、可重试、可显示进度，发送按钮在所有图 ready 前禁用。

服务于 goals-duty **G1 / G6 / D1 / D2 / D3**。

### 2. Pure-Function Policy：视觉兜底是无状态裁决

`Vision Policy` 是纯函数 + 常量映射，不读 DB、不依赖 IO，只回答"当前 (provider, model) 是否能看图"与"provider 的默认视觉模型是什么"。它通过 `dataclasses.replace` 在 runtime config 上做不可变副本替换，仅对本次调用生效。

服务于 goals-duty **G3 / D5 / D6 / N5**。

### 3. Adapter at One Seam：多模态注入仅作用于当前一轮

`Multimodal Context Adapter` 不修改 `StoredMessage`、不修改 SessionMemory、不修改 Compressor，只在 ContextBuilder 构造"最后一条 user 消息"时把 image_url part 拼到 content。历史消息永远保持字符串 content。

服务于 goals-duty **G4 / N3** 与 architecture 的最低侵入约束。

### 4. Resource Adapter Split：原图与送 LLM 副本走两条读路径

`Chat Image Service` 暴露两个读取入口：`load_preview` 返回原图、`load_for_llm` 返回经过 long-edge 缩放与 base64 编码的内存副本。原图永远不被改写。

服务于 goals-duty **G5 / D9**。

### 5. Parallel Asset Tables：与 generated_images 物理隔离

不在 `generated_images` 上加 `source` 字段做合并，而是新建 `chat_images` 表与 `chat-images/` storage 路径。两类资产来源信任不同（用户上传 vs 工具生成）、生命周期不同、UI 语义不同，物理隔离是最便宜的边界。

服务于 goals-duty **G7 / N7**。

### 6. Defer Cleanup：软删 + 后台扫描

session/message 删除时立即对 chat_images 做软删（写 deleted_at），实际 storage 文件由后续 sweeper 任务清理。原因是 chat 流处理路径不应被 storage IO 阻塞，软删也便于事故回滚。

服务于 goals-duty **D8**。

### 7. 拒绝在 LLMClient 中混入视觉概念

`LLMClient` 只负责把 messages 透传给上游 SDK，对"视觉"无感知。视觉判定与 model 替换全部在 ChatService 这一侧完成。LLMClient 因此保持稳定的最小职责。

这是"被放弃的方案"之一（在 LLMClient 内部判断 + 自动改写 model），放弃理由是它会让 LLMClient 变成业务感知层，破坏 batch-2 client 的分层契约。

---

## 三、Module Structure & File Layout（模块结构与文件组织）

模块的文件分布在 Newbee 已有的目录结构中，遵循"按角色而非按模块名"的现有约定。

### 后端

```text
newbee_notebook/
├ api/
│  └ routers/
│     └ chat_images.py            上传与读取的 HTTP 入口（Upload Surface + 资产读端点）
│  └ schemas/
│     └ chat_images.py            ChatImage / Upload 响应 / Error 响应 pydantic schema
│
├ application/
│  └ services/
│     ├ chat_image_service.py     Chat Image Service：校验、存储、加载（含 load_for_llm）
│     └ chat_service.py           （已存在）Chat Pipeline Hook 接入位置
│
├ infrastructure/
│  └ persistence/
│     └ chat_image_repository.py  Chat Image Repository：DB 读写、按 session 校验、软删
│  └ storage/
│     └ chat_image_storage.py     StorageBackend 的 chat-images 命名空间封装
│
├ core/
│  ├ llm/
│  │  └ vision_policy.py          Vision Policy：白名单常量 + is_vision_capable + fallback
│  └ context/
│     └ context_builder.py        （已存在）扩展可选参数 current_image_data_urls
│
└ db/
   └ migrations/
      └ versions/
         └ <yyyy_mm_dd>_chat_images.py  alembic 迁移：建 chat_images 表 + 给 chat_messages 加 image_ids JSONB
```

### 前端

```text
frontend/src/
├ components/
│  └ chat/
│     ├ chat-input.tsx                 （已存在）增加附件栏触发与发送按钮禁送条件
│     ├ chat-image-attachments/        附件栏组件目录
│     │  ├ attachment-bar.tsx          多图缩略 / 上传中 / 失败重试
│     │  ├ paperclip-button.tsx        file picker
│     │  ├ paste-handler.ts            剪贴板图片捕获 hook
│     │  ├ drop-zone.tsx               拖拽落区
│     │  └ screenshot-button.tsx       getDisplayMedia 截屏（不可用时隐藏）
│     └ chat-panel.tsx                 历史消息缩略图回看
├ lib/
│  ├ api/
│  │  ├ chat-images.ts                 上传与读取 API client
│  │  └ types.ts                        ChatRequest 增加 image_ids；ChatMessage.images 来源类型扩展
│  └ hooks/
│     └ useChatImageUpload.ts          管理多图并发上传 + 状态机
```

### 配置与文档

```text
newbee_notebook/configs/llm.yaml       Zhipu 默认模型已是 glm-5v-turbo（不在本模块内改）
docs/backend-v4/img-upload/            本模块设计文档目录
```

---

## 四、Architectural Constraints & Trade-offs（约束与权衡）

### 1. 不在 LLMClient 中加视觉判定

**取舍**：放弃了"在 LLMClient 内自动判断 model 与替换"的便捷写法，接受 ChatService 多一处显式调用 Vision Policy 的代价。
**理由**：保持 `LLMClient` 作为薄 SDK wrapper 的不变性；视觉策略可单独单测、可在不动 LLMClient 的情况下演进白名单。

### 2. 不修改 StoredMessage 的 content 类型

**取舍**：放弃了"让历史消息天然支持多模态 content 数组"的统一抽象，接受当前一轮在 ContextBuilder 内分支处理的代价。
**理由**：dual-track memory、Compressor、token_counter、compaction 的全部既有实现都依赖 `content: str`。若改为 `str | list[dict]`，三个子系统都要做兼容修改与回归测试，超出本模块范围。

### 3. 历史轮次不重传图

**取舍**：放弃了"用户提到旧图时仍能看到原图"的多轮视觉记忆能力，接受单轮视觉的短窗口语义。
**理由**：避免 token 成本不可控；agent 自身记忆模块仍可基于 `metadata.image_ids` 做语义引用；若未来需要长期视觉记忆，可在 agent 记忆层独立讨论，不污染本模块。

### 4. 单次 model 兜底而不是引导用户改配置

**取舍**：放弃了"前端拦截 + 引导用户切换模型"的强显式方案，接受后端单次切换的隐式语义。
**理由**：用户预期是"附图就能问"；前端拦截会让多模态成为高摩擦功能。日志与可观测性补足隐式带来的认知缺口。

### 5. Inline base64 优于 presigned URL

**取舍**：放弃了"通过 MinIO presigned URL 减小 chat 请求体"的方案，接受单次请求体可能达到几 MB 的代价。
**理由**：内网 / docker-compose / 本地部署中 LLM 提供商无法反向访问 Newbee storage；base64 是唯一在所有部署形态都成立的方案。`Chat Image Service.load_for_llm` 的 long-edge 缩放是为此约束的代偿。

### 6. 平行 chat_images 表

**取舍**：放弃了"复用 generated_images 表 + source 字段"的合并方案，接受多一张表的代价。
**理由**：来源信任、生命周期、安全审计三方面差异明显；合并将让 generated_images 现有逻辑必须围绕 source 分支处理，造成更高维护成本。

### 7. 上传未全 ready 不允许发送

**取舍**：放弃了"发送时把上传未完成的图丢进异步队列继续传"的弹性方案，接受用户必须等待的体验代价。
**理由**：契约简单 → 后端不需要做"部分图未到也先生成回复，再补传"的状态机；前端只需要禁用发送按钮即可保证一致性。
