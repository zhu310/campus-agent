"""FastAPI 应用启动入口。

本模块负责创建数据库表、配置前端跨域访问，并把各业务路由挂载到统一的
API 入口下。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routes.audit import router as audit_router
from app.routes.agent import router as agent_router
from app.routes.analytics import router as analytics_router
from app.routes.chat import router as chat_router
from app.routes.dashboard import router as dashboard_router
from app.routes.capabilities import router as capabilities_router
from app.routes.documents import router as documents_router
from app.routes.exports import router as exports_router
from app.routes.extensions import router as extensions_router
from app.routes.forms import router as forms_router
from app.routes.health import router as health_router
from app.routes.history import router as history_router
from app.routes.knowledge import router as knowledge_router
from app.routes.memory import router as memory_router
from app.routes.ocr import router as ocr_router
from app.routes.review import router as review_router
from app.routes.rules import router as rules_router
from app.routes.sessions import router as sessions_router
from app.routes.tasks import router as tasks_router
from app.routes.workflow import router as workflow_router
import app.models  # noqa

# 当前项目偏演示/比赛场景，启动时自动创建缺失的数据表，降低本地运行门槛。
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查保留根路径，便于部署探针访问；业务接口统一放在 /api 下。
app.include_router(health_router)
app.include_router(documents_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(forms_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(capabilities_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(extensions_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(ocr_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(rules_router, prefix="/api")


@app.get("/")
def root():
    """提供一个便于人工检查服务状态的根路径响应。"""
    return {
        "message": "Campus Copilot API is running",
        "demo_mode": settings.DEMO_MODE,
        "features": ["RAG", "OCR", "Rule Audit", "Form Prefill", "Workflow Planning"],
    }


"""

"""
