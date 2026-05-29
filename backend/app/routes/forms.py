"""表单预填接口。

根据已抽取字段生成可写入表单模板的结构化结果，并保存最近一次预填记录。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, FormFillResult, FormTemplate, ToolLog
from app.schemas import FillAssistantRequest, FillAssistantResponse, FormFillRequest, FormFillResponse
from app.services.session_service import add_session_event
from app.services.notice_task_service import generate_fill_assistant
from app.services.form_service import prefill_form

router = APIRouter(prefix="/forms", tags=["forms"])


def _template_name_for(scenario: str) -> str:
    names = {
        "competition_registration": "比赛报名表",
        "leave_approval": "请假审批表",
        "reimbursement": "报销申请表",
        "club_activity": "社团活动审批表",
        "scholarship_application": "奖助学金申请表",
    }
    return names.get(scenario, "通用办理表单")


def _ensure_template(db: Session, scenario: str):
    template_name = _template_name_for(scenario)
    template = db.query(FormTemplate).filter(FormTemplate.name == template_name).first()
    if template:
        return template
    template = FormTemplate(name=template_name, scenario=scenario, schema={})
    db.add(template)
    db.commit()
    return template


@router.post("/prefill", response_model=FormFillResponse)
def form_prefill(req: FormFillRequest, db: Session = Depends(get_db)):
    template = _ensure_template(db, req.scenario)
    template_docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all() if req.document_ids else []
    template_text = "\n\n".join(doc.content or "" for doc in template_docs)
    result = prefill_form(req.text, req.extracted_fields, scenario=req.scenario, template_text=template_text)
    db.add(FormFillResult(template_name=template.name, source_text=req.text, result=result))
    db.add(
        ToolLog(
            task_name="表单预填",
            tool_name="prefill_form",
            input_payload={"template": template.name},
            output_payload={"missing_fields": result["missing_fields"]},
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "form",
            "表单预填",
            {"result": result, "document_ids": req.document_ids},
        )
    db.commit()
    return FormFillResponse(**result)


@router.post("/assist", response_model=FillAssistantResponse)
def form_assist(req: FillAssistantRequest, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all() if req.document_ids else []
    result = generate_fill_assistant(docs, req.user_profile, req.form_text, req.draft_content, req.scenario)
    db.add(
        ToolLog(
            task_name="填写助手",
            tool_name="fill_assistant",
            status="fallback" if result.get("fallback_used") else "completed",
            input_payload={"document_ids": req.document_ids, "scenario": req.scenario},
            output_payload={
                "required_information": len(result.get("required_information", [])),
                "draft_sections": len(result.get("draft_sections", [])),
            },
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "fill_assist",
            "填写助手",
            {"result": result, "document_ids": req.document_ids, "draft_content": req.draft_content},
        )
    db.commit()
    return FillAssistantResponse(**result)
