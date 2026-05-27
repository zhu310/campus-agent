"""智能体编排接口。

把问答、字段抽取、审核、表单预填和流程规划串成一条完整办理链路，供前端
“一键运行完整闭环”调用。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ToolLog
from app.schemas import AgentRunRequest, AgentRunResponse, TraceStep
from app.services.audit_service import audit_material, list_rules, merge_fields
from app.services.form_service import prefill_form
from app.services.workflow_service import plan_workflow

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResponse)
def run_agent(req: AgentRunRequest, db: Session = Depends(get_db)):
    trace = [
        TraceStep(title="Intent Agent", status="completed", detail="识别为综合办理链路"),
        TraceStep(title="Audit Agent", status="completed", detail="抽取字段并执行规则审核"),
        TraceStep(title="Form Agent", status="completed", detail="生成表单预填草稿"),
        TraceStep(title="Workflow Agent", status="completed", detail="生成下一步办理计划"),
        TraceStep(title="Record Agent", status="completed", detail="写入工具调用留痕"),
    ]

    fields = merge_fields(req.material_text, scenario=req.scenario)
    rules = list_rules(db, req.scenario)
    audit_result = audit_material(req.material_name, req.material_text, req.scenario, rules, extra_fields=fields)
    form_result = prefill_form(req.material_text, audit_result["recognized_fields"], scenario=req.scenario)
    workflow_result = plan_workflow(
        f"{req.request_text}\n审核结论：{audit_result['level']}\n材料内容：{req.material_text[:4000]}",
        req.scenario,
    )

    db.add(
        ToolLog(
            task_name="综合办理 Agent",
            tool_name="agent_run",
            status="completed",
            input_payload={"scenario": req.scenario, "document_ids": req.document_ids},
            output_payload={
                "fields": fields,
                "audit_level": audit_result["level"],
                "workflow_steps": len(workflow_result["steps"]),
            },
        )
    )
    db.commit()

    return AgentRunResponse(
        intent="integrated_process",
        fields=fields,
        audit=audit_result,
        form=form_result,
        workflow=workflow_result,
        trace=trace,
    )
