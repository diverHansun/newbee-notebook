# Newbee Notebook

Newbee Notebook 是一个面向医疗学习与知识问答的多模式智能助手项目，支持文档上传、知识检索问答和内容总结讲解。

## 功能概览

- `Chat`：通用对话与工具辅助查询
- `Ask`：基于知识库文档的问答
- `Conclude`：对文档内容进行总结
- `Explain`：对概念进行解释和拆解
- 文档处理：统一转为 Markdown 后进入检索链路

## 文档处理规则

- PDF：`MinerU (cloud/local) -> PyPdf fallback`
- CSV / Word / TXT / Markdown / HTML 等：`MarkItDown -> Markdown`

## 快速入口

- API 文档：`http://localhost:8000/docs`
- CLI：`python main.py`
- 文档上传脚本：`python scripts/upload_documents.py "<file-path>"`
- 脚本分层说明：`scripts/README.md`
- Postman 集合：`postman_collection.json`

## 使用前准备

- 详细启动步骤：`quickstart.md`
- 先复制环境模板：`cp .env.example .env`
- 至少配置：`ZHIPU_API_KEY`、数据库连接、`MINERU_MODE`
- 文档转换 Cloud 模式必填：`MINERU_API_KEY`

## 项目文档

- 后端文档：`docs/backend-v1/`
- 前端规划：`docs/frontend-v1/`
- MinerU V4 改造：`docs/backend-v1/improve-3/`
- Postman 指南：`POSTMAN_GUIDE.md`
