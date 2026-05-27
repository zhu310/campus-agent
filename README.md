# 智审通 Campus Copilot

面向高校行政与学生事务的一站式智能审批与材料办理 Agent 平台。比赛版主链路固定为：

上传制度/通知 → 提问咨询 → RAG 检索回答 → 上传材料 → OCR 抽取 → 规则审核 → 表单预填 → 办理待办生成 → 记录留痕。

## 技术栈

- Frontend: React + TypeScript + Vite + Ant Design
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: PostgreSQL
- Vector DB: Qdrant
- OCR: PaddleOCR，PDF 文本抽取作为降级
- LLM: DeepSeek / Qwen / 通义 / 阿里百炼等 OpenAI 兼容 API

## 主链路接口

- `POST /api/documents/upload`
- `POST /api/knowledge/index`
- `POST /api/chat/query`
- `POST /api/audit/upload`
- `POST /api/audit/extract-fields`
- `POST /api/audit/run`
- `POST /api/forms/prefill`
- `POST /api/workflow/plan`
- `GET /api/tasks/recent`
- `GET /api/tasks/{id}`
- `POST /api/records/save`

保留兼容接口：`POST /api/chat/ask`、`POST /api/audit`、`GET /api/history/recent`、`POST /api/ocr/parse`。

## 数据表

核心表包括 `documents`、`document_chunks`、`sessions`、`audit_tasks`、`audit_results`、`form_templates`、`form_fill_results`、`workflow_runs`、`rule_policies`、`tool_logs`。

## 启动

```bash
docker compose up -d
```

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`
后端默认地址：`http://localhost:8000`

## 演示路径

1. 点击“导入比赛通知”，把示例通知写入知识库并入 Qdrant。
2. 提问“单人能否参赛？”或“报名截止时间是什么？”查看 RAG 回答和引用。
3. 上传报名截图/PDF，或使用内置样例材料。
4. 系统进行 OCR / 字段抽取
5. 运行规则审核
6. 自动生成表单草稿
7. 自动生成办理待办
8. 查看办理记录留痕

## 拓展选择

本地国产模型、微调数据制作、导出 Word/PDF、多 Agent 编排、请假/报销/奖助学金/社团活动审批都作为可插拔增强，不阻塞比赛主链路。
