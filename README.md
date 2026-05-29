# 智审通 Campus Copilot

面向高校行政与学生事务的一站式智能审批与材料办理 Agent 平台。比赛版主链路固定为：

上传规则/表单模板 → 提问咨询 → RAG 检索回答 → 上传个人材料/填写草稿 → 字段抽取 → 审核并补全 → 表单草稿 → 办理清单生成 → 会话留痕。

## 技术栈

- Frontend: React + TypeScript + Vite + Ant Design
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: PostgreSQL
- Vector DB: Qdrant
- OCR: PaddleOCR，PDF 文本抽取作为降级
- LLM: DeepSeek / Qwen / 通义 / 阿里百炼等 OpenAI-compatible API
- Embedding: 支持独立 OpenAI-compatible `/v1/embeddings` 服务，推荐本地 Ollama `bge-m3`

## 主链路接口

- `POST /api/documents/upload`
- `POST /api/knowledge/index`
- `POST /api/chat/query`
- `POST /api/audit/upload`
- `POST /api/audit/extract-fields`
- `POST /api/audit/run`
- `POST /api/forms/assist`
- `POST /api/forms/prefill`
- `POST /api/workflow/notice-tasks`
- `POST /api/workflow/plan`
- `GET /api/sessions/recent`
- `POST /api/sessions`

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

1. 在文件中心选择“规则/模板”，上传制度、通知、填表说明或表格模板。
2. 勾选规则/模板文件，提问“单人能否参赛？”或“报名截止时间是什么？”查看 RAG 回答和引用。
3. 在文件中心选择“个人材料”，上传个人材料、证明材料或填写草稿。
4. 点击“提取材料信息”，查看结构化字段。
5. 点击“审核并补全”，一次完成材料审核和补全建议生成。
6. 点击“生成表单草稿”，根据上传模板字段生成结构化草稿。
7. 点击“生成办理清单”或“完整闭环”，生成下一步办理计划。
8. 查看会话留痕和工具调用记录。

## 拓展选择

本地国产模型、微调数据制作、多 Agent 编排、请假/报销/奖助学金/社团活动审批都作为可插拔增强，不阻塞比赛主链路。当前版本不把 Word 原表格写回作为主功能，表单能力定位为“结构化草稿 + 缺失项 + 复核提示”。
