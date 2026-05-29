"""流程规划接口。

根据用户问题、材料审核上下文和场景类型生成下一步办理计划。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, ToolLog, WorkflowRun
from app.schemas import NoticeTaskRequest, NoticeTaskResponse, WorkflowRequest, WorkflowResponse
from app.services.notice_task_service import generate_notice_tasks
from app.services.session_service import add_session_event
from app.services.workflow_service import plan_workflow

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.post("/plan", response_model=WorkflowResponse)
def workflow_plan(req: WorkflowRequest, db: Session = Depends(get_db)):
    selected_docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all() if req.document_ids else []
    if req.document_ids and not selected_docs:
        raise HTTPException(status_code=404, detail="未找到选中的制度/通知文件。")
    documents = [{"filename": doc.filename, "content": doc.content or "", "source_type": doc.source_type} for doc in selected_docs]
    result = plan_workflow(req.request_text, req.scenario, documents=documents)
    db.add(WorkflowRun(intent=result["intent"], request_text=req.request_text, result=result))
    db.add(
        ToolLog(
            task_name="流程待办",
            tool_name="generate_todo_plan",
            status="fallback" if result.get("fallback_used") else "completed",
            input_payload={"request_text": req.request_text, "scenario": req.scenario, "document_ids": req.document_ids},
            output_payload={"todos": result["todos"]},
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "workflow",
            "流程计划",
            {"request_text": req.request_text, "result": result, "document_ids": req.document_ids},
        )
    db.commit()
    return WorkflowResponse(**result)


@router.post("/notice-tasks", response_model=NoticeTaskResponse)
def notice_tasks(req: NoticeTaskRequest, db: Session = Depends(get_db)):
    if not req.document_ids:
        raise HTTPException(status_code=400, detail="请先选择至少一份通知、制度或说明文件。")
    docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all()
    if not docs:
        raise HTTPException(status_code=404, detail="未找到选中的文件。")
    result = generate_notice_tasks(docs, req.user_goal, req.scenario)
    db.add(WorkflowRun(intent="notice_task_cards", request_text=req.user_goal, result=result))
    db.add(
        ToolLog(
            task_name="通知任务卡",
            tool_name="extract_notice_tasks",
            status="fallback" if result.get("fallback_used") else "completed",
            input_payload={"document_ids": req.document_ids, "scenario": req.scenario, "user_goal": req.user_goal},
            output_payload={"tasks": len(result.get("tasks", [])), "risks": len(result.get("cross_document_risks", []))},
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "tasks",
            "通知任务卡",
            {"user_goal": req.user_goal, "result": result, "document_ids": req.document_ids},
        )
    db.commit()
    return NoticeTaskResponse(**result)
