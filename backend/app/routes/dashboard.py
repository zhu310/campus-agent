"""数据看板接口。

聚合文档、问答、审核、表单和流程任务数量，生成首页使用的摘要指标。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import AuditTask, ChatLog, Document, FormFillResult, WorkflowRun
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)):
    return DashboardSummary(
        project_name="智审通 Campus Copilot",
        documents_count=db.query(Document).count(),
        ask_count=db.query(ChatLog).count(),
        audit_count=db.query(AuditTask).count(),
        form_count=db.query(FormFillResult).count(),
        workflow_count=db.query(WorkflowRun).count(),
        highlight="把制度问答、材料解析、规则审核、表单预填和流程待办整合到同一个高校智能办理工作台。",
        metrics=[],
        business_value=[
            "服务学生、老师与学校管理部门的高频事务办理。",
            "将分散在通知、表格、截图中的信息统一成可执行办理流程。",
            "同一主链路可扩展到请假审批、奖助学金、报销和社团活动审批。",
        ],
        scenarios=["比赛报名", "请假审批", "奖助学金申请", "报销办理", "社团活动审批"],
        demo_mode=settings.DEMO_MODE,
    )
