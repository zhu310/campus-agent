"""表单预填接口。

根据已抽取字段生成可写入表单模板的结构化结果，并保存最近一次预填记录。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import FormFillResult, FormTemplate, ToolLog
from app.schemas import FormFillRequest, FormFillResponse
from app.services.form_service import FORM_TEMPLATE, FORM_TEMPLATES, prefill_form

router = APIRouter(prefix="/forms", tags=["forms"])


def _template_name_for(scenario: str) -> str:
    names = {
        "competition_registration": "比赛报名表",
        "leave_approval": "请假审批表",
        "reimbursement": "报销申请表",
        "club_activity": "社团活动审批表",
    }
    return names.get(scenario, "通用办理表单")


def _ensure_template(db: Session, scenario: str):
    template_name = _template_name_for(scenario)
    template = db.query(FormTemplate).filter(FormTemplate.name == template_name).first()
    if template:
        return template
    template = FormTemplate(name=template_name, scenario=scenario, schema=FORM_TEMPLATES.get(scenario, FORM_TEMPLATE))
    db.add(template)
    db.commit()
    return template


@router.post("/prefill", response_model=FormFillResponse)
def form_prefill(req: FormFillRequest, db: Session = Depends(get_db)):
    template = _ensure_template(db, req.scenario)
    result = prefill_form(req.text, req.extracted_fields, scenario=req.scenario)
    db.add(FormFillResult(template_name=template.name, source_text=req.text, result=result))
    db.add(
        ToolLog(
            task_name="表单预填",
            tool_name="prefill_form",
            input_payload={"template": template.name},
            output_payload={"missing_fields": result["missing_fields"]},
        )
    )
    db.commit()
    return FormFillResponse(**result)
