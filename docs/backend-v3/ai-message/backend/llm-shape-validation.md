# LLM 返回形态验证

## 概述

本文件说明如何在真实环境中验证 OpenAI-compatible LLM 在以下场景下的实际返回形态：

1. 非流式普通回答
2. 非流式 structured tool_call
3. 流式 structured tool_call

这项验证的目标不是测试业务功能，而是确认中间态方案依赖的几个关键假设是否成立：

1. 模型在 tool_call 场景下是否会返回自然语言 `content`
2. 流式响应里 `content delta` 和 `tool_calls delta` 的先后顺序是什么
3. `tool_calls delta` 的字段结构是否符合当前 `AgentLoop` 预期

---

## 一、验证脚本

脚本路径：`scripts/llm_response_shape_probe.py`

脚本特点：

1. 复用项目现有 `newbee_notebook.core.llm.client.LLMClient`
2. 自动加载仓库根目录 `.env`
3. 默认读取 `newbee_notebook/configs/llm.yaml` 中的 provider/model 配置
4. 同时输出原始响应 JSON 和便于人工查看的摘要信息
5. 支持把结果写入 JSON 文件，便于后续对照分析

---

## 二、验证案例

### Case 1：普通非流式回答

作用：确认普通回答的基线结构。

关注点：

- `choices[0].message.content`
- 是否没有 `tool_calls`

### Case 2：非流式 structured tool_call

作用：确认当模型被要求调用工具时，是否会返回：

- 只有 `tool_calls`
- 或 `content + tool_calls`

这是中间态功能的第一层前提。

### Case 3：流式 structured tool_call

作用：确认 tool_call 场景下的 chunk 形态。

重点观察：

1. 是否出现 `delta.content`
2. 是否出现 `delta.tool_calls`
3. 第一段 `delta.content` 是否早于第一段 `delta.tool_calls`
4. `delta.tool_calls` 是否带 `index`、`id`、`function.name`、`function.arguments`

这是后端 `_stream_reasoning()` 方案成立的关键验证。

---

## 三、建议运行命令

### 使用默认 provider/model

```bash
python scripts/llm_response_shape_probe.py
```

### 指定 Qwen

```bash
python scripts/llm_response_shape_probe.py --provider qwen --model qwen3.5-plus
```

### 指定 Zhipu

```bash
python scripts/llm_response_shape_probe.py --provider zhipu --model glm-5
```

### 输出到文件

```bash
python scripts/llm_response_shape_probe.py --output tmp/host-debug-validation/llm-shape-qwen.json
```

---

## 四、结果如何解读

### 最理想的情况

如果流式 tool_call 验证结果表现为：

1. 先出现一小段 `delta.content`
2. 随后出现 `delta.tool_calls`
3. `arguments` 被分多段流出

那么这说明：

- 延迟 flush 策略是合理的
- `_ToolCallAccumulator` 的设计有必要
- 前端确实有机会看到“让我先查一下...”这类中间态文本

### 次优情况

如果模型只返回 `tool_calls`，没有伴随 `content`，也不代表方案失败，只是说明：

- 中间态功能不是每次都能出现
- 前端仍需保留 ThinkingIndicator / ToolStepsIndicator 回退逻辑

### 不符合预期的情况

如果流式返回完全没有 structured tool_call delta，或者字段结构与 OpenAI-compatible Chat Completions 差异很大，那么后端就需要先补 provider 兼容层，而不能直接实现 `_stream_reasoning()`。

---

## 五、与当前方案的关系

验证完成后，主要用来确认以下几个设计点：

1. `intermediate_content` 事件是否值得做
2. `_stream_reasoning()` 是否可以直接落在现有 `LLMClient.chat_stream()` 上
3. `content` 和 `tool_calls` 是否需要 provider-specific 兼容处理
4. 后端是否可以默认采用“structured tool_call 优先、文本 fallback 次之”的策略

---

## 六、实施建议

1. 先用默认 provider 跑一次。
2. 再分别用 Qwen 和 Zhipu 跑一遍。
3. 把三份 JSON 结果保留在 `tmp/host-debug-validation/` 下。
4. 以真实结果回头校正 `AgentLoop` 的实现细节，而不是只根据文档假设推进。

---

## 七、2026-04-07 实测结果

本次已经用真实 key 跑过两组 provider：

1. `qwen / qwen3.5-plus`
2. `zhipu / glm-5`

结果文件：

1. `tmp/host-debug-validation/llm-shape-qwen3.5-plus.json`
2. `tmp/host-debug-validation/llm-shape-glm-5.json`

### 7.1 Qwen 结果

关键观察：

1. 非流式 tool_call 返回 `content=""`，只有 `tool_calls`。
2. 流式 tool_call 从第一个 chunk 开始就是 `delta.tool_calls`。
3. 没有观察到任何 `delta.content`。
4. `arguments` 以多段字符串增量返回，符合 `_ToolCallAccumulator` 的预期。

结论：

- Qwen 默认路径下，中间态 UI 很可能大多数时候不会出现。
- 但流式 structured tool_call 聚合器仍然是必须的。

### 7.2 GLM-5 结果

关键观察：

1. 非流式 tool_call 返回了自然语言 `content + tool_calls`。
2. 流式 tool_call 先返回多段 `delta.content`，之后再返回 `delta.tool_calls`。
3. 这与后端文档中的延迟 flush 假设完全一致。

结论：

- GLM-5 明确支持本次中间态方案的目标体验。
- 当前产品默认按 Zhipu/GLM-5 路径设计时，中间态 UI 会显著可见。

### 7.3 对方案的直接影响

1. 后端必须保留 provider 无中间态时的回退路径，不能假设所有 provider 都会产出中间态文本。
2. 前端必须保留 ThinkingIndicator / ToolStepsIndicator 的无中间态回退展示。
3. 延迟 flush 策略仍然成立，因为至少 GLM-5 已实测验证 `content` 先于 `tool_calls` 到达。