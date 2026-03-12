# Context 模块：数据流与接口定义

## 1. 上下文与范围

Context 模块位于 engine 和 session 之间：

- session 模块在会话开始时调用 Context 恢复历史，在请求结束后调用 Context 追加新消息。
- engine 模块（AgentLoop）在执行前调用 Context 获取构建好的消息链。
- Context 模块自身依赖 LLM 的 tokenizer 做 token 统计，依赖 LLM 实例做异步摘要生成。

## 2. 数据流

### 2.1 消息链构建流程

以 Agent 模式为例，完整的消息链构建流程：

1. engine 调用 `ContextBuilder.build(track="main", system_prompt=...)`。
2. ContextBuilder 从 SessionMemory 读取 Main 轨道的全部消息。
3. TokenCounter 统计总 token 数。
4. 与 ContextBudget 的 history 预算对比。
5. 若未超预算：直接返回 `[system_prompt] + [全部历史]`。
6. 若超预算：按分层策略压缩。
   - 最近 N 轮 -> 完整保留
   - 倒数 N+1 到 N+M 轮 -> Compressor 首段提取
   - 更早的消息 -> 使用缓存的摘要（若无缓存，使用截断版本，异步触发摘要生成）
7. 重新统计压缩后的 token 数，确认在预算内。
8. 组装最终消息链：`[system_prompt, 摘要消息(可选), 压缩层消息, 完整层消息]`。

### 2.2 Explain/Conclude 的消息链构建

1. engine 调用 `ContextBuilder.build(track="side", system_prompt=..., inject_main=True)`。
2. ContextBuilder 从 SessionMemory 读取 Main 轨道近期历史。
3. 对 Main 历史按 main_injection 预算截断。
4. 从 SessionMemory 读取 Side 轨道历史。
5. 对 Side 历史按 history 预算压缩（策略同 Main）。
6. 组装：`[system_prompt, Main 历史(只读前缀), Side 历史]`。

### 2.3 新消息写入

请求结束后，session 模块调用 SessionMemory 追加新消息：

1. session 确定当前模式对应的轨道（Agent/Ask -> Main，Explain/Conclude -> Side）。
2. 调用 `SessionMemory.append(track, [user_message, assistant_message])`。
3. SessionMemory 将消息追加到对应轨道。
4. 若 Side 轨道超出容量上限，裁剪最早的交互对。
5. 若追加后历史消息进入新的摘要范围，标记摘要为"过期"。

### 2.4 异步摘要生成

1. 消息链构建时发现摘要已过期或不存在。
2. 本次构建使用截断版本（零延迟）。
3. 请求结束后，触发异步任务调用 LLM 生成摘要。
4. 摘要生成完成后，写入 SessionMemory 的摘要缓存。
5. 下次请求的消息链构建使用新摘要。

### 2.5 Session 恢复

用户重新打开已有会话时：

1. session 模块从数据库加载 Message 实体列表。
2. 按 mode 分类为 CA 消息（Chat/Ask）和 EC 消息（Explain/Conclude）。
3. 调用 `SessionMemory.load_from_messages(ca_messages, ec_messages)`。
4. SessionMemory 将 Message 实体转换为 ChatMessage，写入对应轨道。
5. 如果数据库中存储了摘要（Session.context_summary），加载到摘要缓存。

## 3. 接口定义

### 3.1 SessionMemory

```python
class SessionMemory:
    def get_history(self, track: str) -> List[ChatMessage]:
        """获取指定轨道的全部消息。track 取值 "main" 或 "side"。"""

    def append(self, track: str, messages: List[ChatMessage]) -> None:
        """向指定轨道追加消息。Side 轨道超出容量时自动裁剪。"""

    def load_from_messages(
        self,
        main_messages: List[MessageEntity],
        side_messages: List[MessageEntity],
    ) -> None:
        """从持久化消息恢复双轨状态。"""

    def get_summary(self) -> Optional[str]:
        """获取摘要层缓存。返回 None 表示无缓存或已过期。"""

    def set_summary(self, summary: str) -> None:
        """设置摘要层缓存。"""

    def mark_summary_stale(self) -> None:
        """标记摘要为过期。"""

    def reset(self) -> None:
        """清空双轨历史和摘要缓存。"""
```

### 3.2 ContextBuilder

```python
class ContextBuilder:
    def __init__(
        self,
        memory: SessionMemory,
        token_counter: TokenCounter,
        budget: ContextBudget,
        compressor: Compressor,
    ) -> None: ...

    def build(
        self,
        track: str,
        system_prompt: str,
        inject_main: bool = False,
    ) -> List[ChatMessage]:
        """构建消息链。inject_main=True 时在 Side 轨道消息前注入 Main 历史。"""

    def compress_tool_results(
        self,
        messages: List[ChatMessage],
        current_round_index: int,
    ) -> List[ChatMessage]:
        """压缩当前请求内的工具结果。current_round_index 之前的 tool_result 被截断。"""
```

### 3.3 TokenCounter

```python
class TokenCounter:
    def __init__(self, llm: LLM) -> None: ...

    def count(self, text: str) -> int:
        """统计文本的 token 数。"""

    def count_messages(self, messages: List[ChatMessage]) -> int:
        """统计消息列表的 token 总数。"""

    def fits_budget(self, messages: List[ChatMessage], budget: int) -> bool:
        """判断消息列表是否在预算内。"""
```

### 3.4 Compressor

```python
class Compressor:
    def __init__(self, llm: LLM, token_counter: TokenCounter) -> None: ...

    def truncate(self, text: str, max_tokens: int) -> str:
        """截断文本到指定 token 数。"""

    def extract_first_paragraph(self, text: str) -> str:
        """提取首段内容。"""

    async def summarize(self, messages: List[ChatMessage], prompt: str) -> str:
        """调用 LLM 生成摘要。异步执行。"""
```

## 4. 数据所有权

| 数据 | 所有者 | Context 模块的角色 |
|------|--------|-------------------|
| ChatMessage 列表（内存） | SessionMemory | 管理者：读写双轨历史 |
| 摘要缓存 | SessionMemory | 管理者：存储和标记过期 |
| Message 实体（数据库） | session 模块 / Repository | 消费者：从中恢复状态 |
| token 预算配置 | ContextBudget（来自配置文件） | 消费者：按预算裁剪 |
| LLM tokenizer | LLM Provider 层 | 消费者：做 token 统计 |
| 构建后的消息链 | 调用方（engine） | 生产者：构建后交出 |
