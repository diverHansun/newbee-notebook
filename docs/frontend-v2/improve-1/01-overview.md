# Frontend-v2 改进计划 1 - 设计文档

## 概述

本文档集描述了 Newbee Notebook 前端 v2 版本的首轮改进，涉及以下四个方面：

1. **i18n 同步** - 界面语言设置与 Agent system_prompt 语言同步
2. **品牌标识** - 小蜜蜂图标替代原有文字标识
3. **协议更新** - License 由 Apache 2.0 更换为 AGPLv3
4. **设置面板精简** - 移除 RAG 配置项，保留 Skills "即将推出" 状态

注：Studio 卡片优化（配色与特效）作为预留项，本次不实施。

## 文档结构

| 文档 | 内容 |
|------|------|
| 01-overview.md | 本文档，描述整体架构和模块关系 |
| 02-i18n-sync-system-prompt.md | i18n 与后端 system_prompt 同步机制设计 |
| 03-brand-identity.md | 品牌标识（小蜜蜂）使用规范 |
| 04-license-update.md | AGPLv3 协议替换说明 |
| 05-settings-panel.md | 设置面板精简设计方案 |

## 模块依赖关系

```
i18n-sync-system-prompt
       |
       v
  +----------+      brand-identity
  | 前端     | <------------------ control-panel-icon.tsx
  | (lang)  |          |
  +----------+          v
       |         +------------+
       |         | 小蜜蜂图片  |
       |         +------------+
       v
  +----------+
  | 后端     |
  | (prompt) |
  +----------+

settings-panel  ----> control-panel.tsx (移除 RAG tab)
```

## 设计原则

- **运行时动态切换**：所有配置变更均支持运行时生效，无需重启后端服务
- **无破坏性变更**：不修改现有 API 契约，仅扩展行为
- **CSS 变量化**：颜色、特效使用 CSS 变量，便于主题扩展
- **静态资源规范**：图片资源放置于 `frontend/public/assets/images/`，通过相对路径引用

## 实施顺序

1. 品牌标识（静态资源替换，最独立）
2. License 更新（文件替换）
3. 设置面板精简（UI 调整）
4. i18n 同步（涉及前后端联动，最后实施）
