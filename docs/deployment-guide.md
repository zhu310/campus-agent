# 部署与运行指南

本文档用于比赛提交、评委复现和现场演示前自检。当前版本采用本地前后端运行，数据库与向量库通过 Docker 启动。

## 1. 环境要求

- Windows 10/11
- Git
- Docker Desktop
- Python 3.11+，当前开发环境使用 Python 3.12 也可运行
- Node.js 18+
- npm

## 2. 获取代码

```powershell
git clone https://github.com/zhu310/campus-agent.git
cd campus-agent
```

如果已经在本机开发目录中，直接进入项目根目录：

```powershell
cd E:\思途杯\campus-agent
```

## 3. 启动数据库与向量库

项目根目录执行：

```powershell
docker compose up -d
```

检查容器：

```powershell
docker ps
```

应看到：

- `campus-agent-postgres`
- `campus-agent-qdrant`

默认端口：

- PostgreSQL: `5432`
- Qdrant: `6333`

## 4. 配置后端环境变量

进入后端目录：

```powershell
cd backend
copy .env.example .env
```

然后打开 `backend/.env`，按实际情况配置：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/campus_agent
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=campus_agent_documents
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
DEMO_MODE=true
UPLOAD_DIR=uploads
```

说明：

- `backend/.env` 只保存在本地，不提交到 GitHub。
- `backend/.env.example` 是公开模板，可以提交。
- 没有稳定模型 API 时，可以先使用 `DEMO_MODE=true` 完成主链路演示。

## 5. 启动后端

首次运行：

```powershell
cd E:\思途杯\campus-agent\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

后续运行：

```powershell
cd E:\思途杯\campus-agent\backend
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

检查地址：

- `http://localhost:8000`
- `http://localhost:8000/health`
- `http://localhost:8000/docs`

## 6. 启动前端

另开一个 PowerShell：

```powershell
cd E:\思途杯\campus-agent\frontend
npm install
npm run dev
```

打开：

```text
http://localhost:5173
```

## 7. 演示数据

项目内置演示材料位于：

```text
demo-assets/
```

当前包含：

- `contest-notice.txt`
- `material-complete.txt`
- `material-incomplete.txt`
- `registration-template.txt`

建议现场再准备 PDF、DOCX、图片版本，避免只依赖文本样例。

## 8. 常见问题

### 后端连接数据库失败

先检查 Docker：

```powershell
docker ps
```

如果容器未启动：

```powershell
docker compose up -d
```

### 前端访问后端失败

确认后端正在运行：

```text
http://localhost:8000/health
```

确认前端 API 地址配置与 `frontend/src/api.ts` 一致。

### 模型 API 超时或失败

现场演示时优先保证主链路稳定。可切换到 `DEMO_MODE=true`，或使用已经准备好的演示材料与备用文本继续演示。

### OCR 效果不稳定

优先使用清晰图片、PDF 或 DOCX。现场准备备用 TXT 文本，必要时用文档解析链路继续完成字段抽取、审核、表单预填和待办生成。

