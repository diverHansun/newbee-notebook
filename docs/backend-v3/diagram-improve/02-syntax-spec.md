# 02 输出格式语法规范

本文档是后续 prompt 与 validator 的单一真相源。每一条规则会被以下两处同时使用:

- `registry.agent_system_prompt`(以及 provider 汇总后的 system_prompt)— 让 LLM 在生成前就看到规则
- `registry.validate_*` — 让后端在 LLM 生成后把关

## 1. mindmap(项目自定义 JSON schema)

### 1.1 概念澄清

此 schema **不是** React Flow 官方 Node schema。前端拿到内容后,由 `frontend/src/lib/diagram/reactflow-layout.ts::parseReactFlowDiagram` 解析为简化结构,再由 dagre 布局、React Flow 渲染。LLM 只需输出以下最小结构,**不要**输出 `position` / `data` / `type` / `sourcePosition` 等 React Flow 字段。

### 1.2 JSON 形式规范

- 顶层必须是一个对象(不能是数组,不能是字符串)
- 顶层对象**有且只有两个键**:`nodes`、`edges`,类型均为数组
- `nodes` 非空,`edges` 可为空(但单节点思维导图几乎无意义,推荐至少 3 个节点)
- 每个 node 对象:
  - `id`:非空字符串,全集唯一,推荐使用英文/数字/下划线,不能包含空格和特殊字符
  - `label`:非空字符串,可以是任意 Unicode 文本(包含中文、标点),无需转义
  - **不得出现其它字段**(包括 `position`、`data`、`type`、`style`、`children` 等)
- 每个 edge 对象:
  - `source`:必须是某个已声明 node 的 id
  - `target`:必须是某个已声明 node 的 id
  - `source` 与 `target` 不得相同
  - **不得出现其它字段**(包括 `id`、`label`、`type`、`animated` 等)
- 整个 JSON **不得被 markdown 代码块包裹**,**不得出现注释 `//`**,**不得有尾随逗号**

### 1.3 结构性建议(非强约束,但 prompt 会告知 LLM)

- 有且仅有一个根节点(入度为 0 的节点恰好一个)
- 边形成一棵有向树(无环、无交叉父节点)
- 推荐深度不超过 4 层,单层子节点数不超过 7

### 1.4 合法样例

```json
{
  "nodes": [
    {"id": "root", "label": "机器学习"},
    {"id": "sup", "label": "监督学习"},
    {"id": "unsup", "label": "无监督学习"},
    {"id": "sup_cls", "label": "分类"},
    {"id": "sup_reg", "label": "回归"}
  ],
  "edges": [
    {"source": "root", "target": "sup"},
    {"source": "root", "target": "unsup"},
    {"source": "sup",  "target": "sup_cls"},
    {"source": "sup",  "target": "sup_reg"}
  ]
}
```

### 1.5 非法样例与原因

```json
{"nodes":[{"id":"a","label":"A","position":{"x":0,"y":0}}]}
```
原因:`position` 是 React Flow 字段,本 schema 禁止。

```json
[{"id":"a","label":"A"}]
```
原因:顶层必须是对象,不能是数组。

```text
```json
{"nodes":[...],"edges":[...]}
```
```
原因:不得用 markdown 代码块包裹。

```json
{"nodes":[{"id":"a","label":"A"}],"edges":[{"source":"a","target":"b"}]}
```
原因:`target="b"` 不在 nodes 列表中。

## 2. Mermaid flowchart

### 2.1 头部

首行(忽略前导空白与空行)必须是以下之一:

- `flowchart <DIR>`
- `graph <DIR>`

其中 `<DIR>` 为方向关键字,**白名单**仅:`TD`、`TB`、`BT`、`LR`、`RL`。其它写法(`TOP`、`DOWN`、`UP` 等)均非法。

推荐默认使用 `flowchart TD`(top-down),除非用户意图明显是水平方向。

### 2.2 节点与形状

节点通过 `<id><shape>` 声明或在边中首次出现时隐式声明。常用 shape:

| Shape         | 语法                  |
|---------------|-----------------------|
| 矩形          | `A[文本]`             |
| 圆角矩形      | `A(文本)`             |
| 菱形(判断)  | `A{文本}`             |
| 圆形          | `A((文本))`           |
| 跑道形(起止)| `A([文本])`           |
| 子程序        | `A[[文本]]`           |
| 圆柱(数据库)| `A[(文本)]`           |

节点 id 规范:

- 使用英文/数字/下划线,**不得以 `o` 或 `x` 开头**(会被解析成边终点修饰符),若语义必须,请改为大写首字母
- 不得使用保留字 `end`(任意大小写组合),若必须用结束节点,请用 `END` 或 `Finish`
- id 在整个 diagram 内唯一

### 2.3 节点 label 的特殊字符

**必须用双引号包裹 label** 的情况:

- label 含空格以外的以下任一字符:`(` `)` `:` `;` `"` `'` `` ` `` `|` `\` `<` `>` `&` `#`
- label 含任何中文标点(如 `,`、`。`、`:`、`(`、`)`、`"`、`"`、`「`、`」` 等)
- label 等于或包含保留字 `end`
- label 中含 `"` 时,外层仍用双引号并在内部用 `#quot;` 或 HTML 实体

示例:

```
A["执行第 1 步 (初始化)"]
B["结果: 通过"]
C["`**加粗** 与 *斜体*`"]
```

建议(非强约束):label 长度不超过 40 个字符;若概念较长,优先拆分为多个节点,而不是堆在一个 label 里。

### 2.4 边

| 语法                       | 含义             |
|----------------------------|------------------|
| `A --> B`                  | 实线箭头         |
| `A --- B`                  | 实线无箭头       |
| `A -.-> B`                 | 虚线箭头         |
| `A ==> B`                  | 粗实线箭头       |
| `A -->|标签| B`            | 带标签的边       |
| `A -- 标签 --> B`          | 带标签的边(等价)|

边标签遵循与节点 label 相同的特殊字符规则,含特殊字符时用双引号包裹:`A -->|"重试 (最多 3 次)"| B`。

### 2.5 合法样例

```
flowchart TD
    Start([开始]) --> Input["读取输入"]
    Input --> Check{"输入有效?"}
    Check -->|是| Process["执行处理"]
    Check -->|否| Error["返回错误"]
    Process --> END([结束])
    Error --> END
```

### 2.6 非法样例与原因

```
flowchart TOP
    A --> B
```
原因:`TOP` 不在方向白名单。

```
flowchart TD
    A[执行(步骤1)] --> B
```
原因:label 含括号,必须用双引号包裹。

```
flowchart TD
    end --> B
```
原因:`end` 是保留字,不能用作节点 id。

```
```mermaid
flowchart TD
    A --> B
```
```
原因:整个 Mermaid content **不得被 markdown 围栏包裹**。

## 3. Mermaid sequenceDiagram

### 3.1 头部

首行(忽略前导空白与空行)必须恰好是 `sequenceDiagram`。不支持在此行附带任何其它文字。

### 3.2 参与者

- **隐式**:在消息中首次出现即注册
- **显式**:`participant <Id>` 或 `participant <Id> as <别名>`,别名可为任意 Unicode 文本
- **actor 形式**:`actor <Id>`(渲染为人形图标)

参与者 id 规范:

- 英文/数字/下划线,唯一
- 若字面需要使用保留字 `end`,请写作 `"end"` 或 `(end)`

### 3.3 消息(箭头)

| 语法       | 含义             |
|------------|------------------|
| `A->B`     | 实线无箭头       |
| `A-->B`    | 虚线无箭头       |
| `A->>B`    | 实线实心箭头     |
| `A-->>B`   | 虚线实心箭头     |
| `A-xB`     | 实线叉号(失败)|
| `A--xB`    | 虚线叉号         |
| `A-)B`     | 实线异步箭头     |

消息格式:`<From><Arrow><To>: <message>`。冒号后是消息文本。

### 3.4 消息文本的特殊字符

- **分号 `;`** 必须写作 `#59;`(否则被解析为语句分隔符)
- **`#`** 必须写作 `#35;`
- 括号、冒号、引号在消息文本中**一般允许**,但若出现解析异常时建议用 HTML 实体
- 多行消息不支持,若需要换行,请在 participant 级用别名,或拆成多条消息

### 3.5 合法样例

```
sequenceDiagram
    participant U as 用户
    participant API as 接口
    participant DB as 数据库
    U->>API: 提交查询
    API->>DB: SELECT * FROM t
    DB-->>API: 结果集
    API-->>U: JSON 响应
```

### 3.6 非法样例与原因

```
sequenceDiagram LR
    A->>B: hello
```
原因:`sequenceDiagram` 首行不得携带附加关键字。

```
sequenceDiagram
    A->>B: 步骤1; 步骤2
```
原因:消息文本中的 `;` 需写作 `#59;`。

```
sequenceDiagram
    end->>B: hi
```
原因:参与者名 `end` 是保留字,需包裹为 `"end"` 或改名。

## 4. 通用禁忌(三种类型共用)

- 不得输出 markdown 代码块围栏 ` ``` `
- 不得在 content 前后附加自然语言说明或标题
- 不得输出 `<tool_call>...</tool_call>` 标记
- 不得使用占位符("TODO"、"待补充"、"...")

## 5. 与 validator 的对应关系

本文档的每一条规则都应在 [04-validator-hardening.md](./04-validator-hardening.md) 中有对应的后端校验实现。Prompt(见 [03-prompt-refactor.md](./03-prompt-refactor.md))与 validator 必须对齐:**凡是 prompt 里宣称的强约束,validator 必须能拦住对应违规**。
