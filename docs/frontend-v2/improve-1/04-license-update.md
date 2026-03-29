# License 协议更新

## 变更内容

将 Newbee Notebook 项目的开源协议从 **Apache License 2.0** 更换为 **GNU Affero General Public License v3 (AGPLv3)**。

## 实施方式

### 文件替换

直接替换项目根目录下的 `LICENSE` 文件内容为 AGPLv3 全文。

### AGPLv3 关键条款摘要

| 条款 | 说明 |
|------|------|
| 自由使用 | 任何人可自由使用、修改、分发本软件 |
| 修改要求 | 如果修改本软件，必须开源修改版本 |
| 网络使用条款 | 通过网络使用本软件的用户有权获得源代码 |
| 专利授权 | 授予必要的专利授权 |
| 无担保 | 按"原样"提供，无任何明示或暗示担保 |

## 协议差异对比

| 方面 | Apache 2.0 | AGPLv3 |
|------|------------|--------|
| 开源要求 | 是 | 是 |
| 商业使用 | 允许 | 允许 |
| 专利授权 | 包含 | 包含 |
| 商标保护 | 明确不授予 | 明确不授予 |
| 网络交互 | 不要求开源 | **要求开源** |
| 专利诉讼 | 提供防御机制 | 提供防御机制 |

**关键差异**：AGPLv3 要求如果通过网页或网络服务向用户提供本软件，也必须向用户公开源代码。这与 Newbee Notebook 作为 Web 应用的项目定位相符。

## 文件位置

```
LICENSE  (项目根目录)
```

## 操作步骤

1. 获取 AGPLv3 官方文本（https://www.gnu.org/licenses/agpl-3.0.html）
2. 替换 `LICENSE` 文件内容
3. 更新版权年份（如需）
4. 检查项目中其他 LICENSE 相关引用是否需要更新

## 版权声明格式

AGPLv3 要求在每个副本中包含版权声明和许可声明。标准格式：

```
Copyright (C) 2024-2026 Newbee Notebook Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

## 第三方依赖兼容性

在更换协议前，需确认项目使用的所有第三方依赖的许可证与 AGPLv3 兼容：

| 依赖类型 | 示例 | 兼容性 |
|----------|------|--------|
| MIT/BSD | React, Next.js | 兼容 |
| Apache 2.0 | 一部分 Node.js 生态 | 兼容 |
| AGPLv3 | 部分开源组件 | 需确认具体条款 |
| 闭源软件 | 不允许 | 不可使用 |

Newbee Notebook 当前使用的依赖（React、Next.js、Tailwind CSS 等）均为 MIT/BSD/Apache 兼容协议，与 AGPLv3 无冲突。

## 注意事项

- License 变更只影响未来版本，不影响已发布版本的法律状态
- 如果项目有贡献者协议，需同步更新 CLA 或 DCO
- 第三方代码的 LICENSE 文件应保留在各自目录
