"""流程规划接口。

根据用户问题、材料审核上下文和场景类型生成下一步办理计划。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, ToolLog, WorkflowRun
from app.schemas import WorkflowRequest, WorkflowResponse
from app.services.workflow_service import plan_workflow

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("/plan", response_model=WorkflowResponse)
def workflow_plan(req: WorkflowRequest, db: Session = Depends(get_db)):
    selected_docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all() if req.document_ids else []
    if req.document_ids and not selected_docs:
        raise HTTPException(status_code=404, detail="未找到选中的制度/通知文件。")
    doc_context = "；".join(doc.filename for doc in selected_docs)
    request_text = req.request_text
    if doc_context:
        request_text = f"{request_text}\n选中文件：{doc_context}"
    result = plan_workflow(request_text, req.scenario)
    db.add(WorkflowRun(intent=result["intent"], request_text=req.request_text, result=result))
    db.add(
        ToolLog(
            task_name="流程待办",
            tool_name="generate_todo_plan",
            input_payload={"request_text": req.request_text, "scenario": req.scenario, "document_ids": req.document_ids},
            output_payload={"todos": result["todos"]},
        )
    )
    db.commit()
    return WorkflowResponse(**result)
