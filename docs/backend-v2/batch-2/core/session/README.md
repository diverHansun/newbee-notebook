# Session 模块设计文档

## 概述

Session 模块负责会话生命周期管理：创建和恢复会话、协调消息持久化、管理并发控制。它是 context 模块和 engine 模块的上层编排者——从 context 获取历史、调用 engine 执行、将结果写回 context 并持久化。

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-goals-duty.md](./01-goals-duty.md) | 设计目标与职责边界 |
| [02-architecture.md](./02-architecture.md) | 会话编排、持久化协调、并发控制 |
| [03-dfd-interface.md](./03-dfd-interface.md) | 数据流与接口定义 |
| [04-test.md](./04-test.md) | 验证策略 |
