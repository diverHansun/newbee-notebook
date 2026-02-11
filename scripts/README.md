# Scripts 目录说明

本项目采用分层脚本组织，避免后端、前端、全局脚本混放。

## 1. 目录职责

1. `scripts/`
   - 全局入口脚本
   - 面向用户直接执行
   - 可调用后端或前端子模块脚本
2. `newbee_notebook/scripts/`
   - 后端内部脚本
   - 建议通过模块方式执行：`python -m newbee_notebook.scripts.<name>`
3. `frontend/scripts/`
   - 前端工程脚本（当前阶段预留）

## 2. 当前脚本

1. `scripts/upload_documents.py`
   - 用途：上传一个或多个本地文档（Windows 中文文件名友好）
   - 示例：`python scripts/upload_documents.py "D:\\docs\\中文病例.pdf"`
2. `scripts/up-mineru.ps1`
   - 用途：按 CPU/GPU 自动选择 compose 配置启动 MinerU 服务
3. `scripts/mineru_v4_smoke_test.py`
   - 用途：对 MinerU v4 云端流程进行端到端冒烟测试

## 3. 后端脚本示例

1. `python -m newbee_notebook.scripts.rebuild_pgvector`
2. `python -m newbee_notebook.scripts.rebuild_es`

