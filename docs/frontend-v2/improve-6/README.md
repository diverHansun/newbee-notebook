# improve-6: API Key 状态指示器统一补全

## 背景

控制面板（Control Panel）模型配置区域中，ASR 配置卡片已有 API Key 状态指示器，
而 LLM、Embedding、MinerU 三个配置卡片缺少同等功能，造成界面行为不一致。
本次改动目标是为三者补全状态指示器，并统一指示器的呈现方式。

## 文档列表

- [01-problem-analysis.md](01-problem-analysis.md) — 现状分析：各配置项的 API key 检查机制与缺失情况
- [02-design-spec.md](02-design-spec.md) — 设计规范：API key 映射规则、字段设计、UI 呈现规范
- [03-implementation-plan.md](03-implementation-plan.md) — 实施方案：后端与前端的具体改动清单

## 涉及文件

**后端**
- `newbee_notebook/api/routers/config.py`
- `newbee_notebook/core/common/config_db.py`

**前端**
- `frontend/src/lib/api/config.ts`
- `frontend/src/components/layout/model-config-panel.tsx`
- `frontend/src/lib/i18n/strings.ts`
