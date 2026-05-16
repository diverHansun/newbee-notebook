# non-functional.md — classify-library

本批次属于**列表查询路径上的小幅扩展**，不是系统关键路径上的高并发模块，因此非功能性约束聚焦在"不引入退化"和"i18n 完整性"两点，而不是性能数字。

---

## 一、Quality Priorities（质量优先级）

按从高到低：

1. **优先保证既有列表查询行为不退化**——本批次不携带 `content_type` 参数时，所有路径必须与本批次前的行为完全一致（响应时间、SQL 形状、返回结构、错误语义）。这是"零回归"承诺。
2. **优先保证 i18n 完备**——所有面向用户的新增字符串必须在 `uiStrings.libraryPage` 中提供中英双值，禁止组件内硬编码（包括 chip 标签、按钮、表格列名、徽章 aria-label、tooltip）。
3. **优先保证类型筛选语义可预测**——多选语义是 OR，类型与状态是 AND，行为在 UI 与 API 文档中必须一致；用户不应猜测语义。
4. **其次才是性能**——当前 Library 文档量级小（百级），`WHERE content_type IN (...)` 在小表上代价可忽略；本阶段不优化、不加索引。

---

## 二、Operational Constraints（运行约束）

### 后端

- **SQL 形状稳定**：未传 `content_type` 时，`list_by_library` / `count_by_library` 生成的 SQL 必须与本批次前的字节级等价（或语义等价但不包含多余的 `WHERE TRUE` 类冗余项），避免影响既有的查询计划缓存。
- **参数列表上限**：`content_type` 重复参数数量不应超过 8（`DocumentType` 全集），Router 层不强制截断（因为最多就 8 个），但若收到超过 32 个的重复值应视为异常并返回 `400`——这是抗滥用边界。
- **Repo 不引入 `OR` 链**：用 `column.in_([...])`，不要手工拼 `OR` 子句。

### 前端

- **请求触发频次**：用户连续点选 chip 不去抖（不引入 debounce）。React Query 的去重与缓存机制已经足够；引入 debounce 反而让交互显得迟钝。
- **fetchAll 兼容**：现有 `fetchAll=true` 路径必须把 `contentTypes` 透传给每一页递归调用，避免出现"第一页过滤、后续页不过滤"的隐患。

### i18n

- **新增字符串必须双语**：CI 或评审需确认每个新 key 在 `zh` / `en` 都存在；缺一即不通过。
- **避免拼接**：分组名应作为完整字符串放进 i18n，不能在代码里做 `t("type") + ": " + group`——不同语言的语序不同。

---

## 三、Reliability & Observability（可靠性与可观测性）

### 失败处理

- **400 非法值**：见 `use-case.md` F-1，必须明确报错，不静默过滤。
- **5xx 失败**：用户的 chip 选中态保留，不自动清空（避免用户重试时还得重新选）。
- **i18n 缺失**：如果某 group 的 i18n key 缺失，组件应回落到 group 的英文键名（如 `slides`）而不是显示空白；这只作为保护，CI 仍应阻止 key 缺失合入。

### 可观测性

- **后端日志不增**：本批次不新增日志（既有 Library 查询本就静默，与本批次定位"小幅扩展"匹配）。如果未来类型筛选成为热点路径再补 metric。
- **不引入 trace span**：HTTP→Service→Repo 链路已经在既有的 FastAPI / SQLAlchemy 日志中可追溯，不为本批次新增 instrumentation。

---

## 四、Trade-offs & Deferred Requirements（权衡与暂缓项）

以下事项**刻意延后**，不在本批次处理：

1. **不持久化 `selectedGroups` 到 URL / localStorage**
   - 用户每次进入页面都从"全部"开始。代价：用户切换页面后回来需重新筛选。
   - 延后理由：当前 Library 文档量级小，重新点选成本可忽略；URL 持久化涉及 query 序列化、刷新行为、可分享链接语义等一系列设计决策，与本批次正交。

2. **不为 `content_type` 列添加数据库索引**
   - 见 `architecture.md` 约束 #2。

3. **不引入额外筛选维度（时间、大小、上传者）**
   - 见 `goals-duty.md` Non-Duties #6。

4. **不批量回填存量 `.ppt` 文档的 `content_type`**
   - 见 `architecture.md` 约束 #4。

5. **不为类型徽章建立完整的色彩语义系统**
   - 类型徽章统一使用中性色（视觉上明显区别于状态徽章的语义色即可），不为每个文件类型单独配色。延后理由：颜色过多反而稀释状态徽章的视觉权重；如果未来需要按类型快速扫视，再单独评估颜色系统。

6. **不引入服务端的"筛选预设"概念**
   - 分组定义留在前端单文件。延后理由：多端复用诉求尚未出现。
