"""数据看板接口。

聚合文档、问答、审核、表单和流程任务数量，生成首页使用的摘要指标。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import AuditTask, ChatLog, Document, FormFillResult, WorkflowRun
from app.schemas import DashboardMetric, DashboardSummary

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
        highlight="把制度问答、OCR 识别、规则审核、表单预填和流程待办整合成一个会办事的高校智能办理平台。",
        metrics=[
            DashboardMetric(label="平均办理耗时下降", value="60%", trend="基于样例流程估算"),
            DashboardMetric(label="材料遗漏识别率", value="85%", trend="规则校验 + OCR/文档抽取"),
            DashboardMetric(label="重复咨询下降", value="70%", trend="RAG 知识库复用"),
            DashboardMetric(label="表单填写效率提升", value="75%", trend="结构化字段自动预填"),
        ],
        business_value=[
            "服务学生、老师与学校管理部门，减少重复咨询和材料返工。",
            "将分散在通知、表格、截图中的信息统一成可执行办理流程。",
            "同一主链路可扩展到请假审批、奖助学金、报销和社团活动审批。",
        ],
        scenarios=["比赛报名", "请假审批", "奖助学金申请", "报销办理", "社团活动审批"],
        demo_mode=settings.DEMO_MODE,
    )
