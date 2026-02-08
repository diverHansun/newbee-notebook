# MediMind Agent

MediMind Agent 是一个面向医疗学习与知识问答的多模式智能助手项目，提供文档上传、检索问答、总结与讲解能力。

## 功能

- `Chat`：通用对话与工具辅助查询
- `Ask`：基于知识库文档的问答
- `Conclude`：对文档内容进行总结
- `Explain`：对概念进行解释和拆解
- 文档处理：统一转为 Markdown 后进入检索链路

## 文档处理规则

- PDF：`MinerU (cloud/local) -> PyPdf fallback`
- CSV / Word / TXT / Markdown / HTML 等：`MarkItDown -> Markdown`

## 使用入口

- API：启动后访问 `http://localhost:8000/docs`
- CLI：`python main.py`
- 上传脚本：`python scripts/upload_documents.py "<file-path>"`
- 接口调试：`postman_collection.json`

## 开始使用

- 详细启动步骤请看 `quickstart.md`
- 先复制环境变量模板：`cp .env.example .env`
- 至少配置：`ZHIPU_API_KEY`、数据库连接、`MINERU_MODE`
- Cloud 模式下需填写：`MINERU_PIPELINE_ID`

## 项目文档

- 后端文档：`docs/backend-v1/`
- 前端文档：`docs/frontend-v1/`
- 改进方案（MinerU）：`docs/backend-v1/improve-2/`
- Postman 说明：`POSTMAN_GUIDE.md`
