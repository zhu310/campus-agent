"""历史记录接口。

统一汇总问答、审核、表单、流程和工具日志，让前端能按最近任务查看详情。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditTask, ChatLog, FormFillResult, ToolLog, WorkflowRun
from app.schemas import HistoryItem, SaveRecordRequest, TaskDetail

router = APIRouter(prefix="/history", tags=["history"])


def _collect_recent(db: Session):
    items = []
    for item in db.query(ChatLog).order_by(ChatLog.created_at.desc()).limit(8).all():
        items.append(HistoryItem(id=item.id, type="问答", title="智能问答", summary=item.question, created_at=item.created_at.isoformat()))
    for item in db.query(AuditTask).order_by(AuditTask.created_at.desc()).limit(8).all():
        items.append(HistoryItem(id=item.id, type="审核", title=item.material_name, summary=f"当前状态：{item.status}", created_at=item.created_at.isoformat()))
    for item in db.query(FormFillResult).order_by(FormFillResult.created_at.desc()).limit(8).all():
        items.append(HistoryItem(id=item.id, type="表单", title=item.template_name, summary="已生成结构化表单预填结果", created_at=item.created_at.isoformat()))
    for item in db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(8).all():
        items.append(HistoryItem(id=item.id, type="待办", title="流程计划", summary=item.result.get("summary", ""), created_at=item.created_at.isoformat()))
    for item in db.query(ToolLog).order_by(ToolLog.created_at.desc()).limit(8).all():
        items.append(HistoryItem(id=item.id, type="留痕", title=item.task_name, summary=f"{item.tool_name} / {item.status}", created_at=item.created_at.isoformat()))
    items.sort(key=lambda entry: entry.created_at, reverse=True)
    return items[:24]


@router.get("/recent", response_model=list[HistoryItem])
def recent_history(db: Session = Depends(get_db)):
    return _collect_recent(db)


@router.get("/tasks/recent", response_model=list[HistoryItem])
def recent_tasks_alias(db: Session = Depends(get_db)):
    return _collect_recent(db)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def task_detail(task_id: int, db: Session = Depends(get_db)):
    audit = db.get(AuditTask, task_id)
    if audit:
        payload = {"source_text": audit.source_text, "results": [result.result for result in audit.results]}
        return TaskDetail(id=audit.id, type="审核", title=audit.material_name, summary=audit.status, payload=payload, created_at=audit.created_at.isoformat())
    chat = db.get(ChatLog, task_id)
    if chat:
        payload = {"question": chat.question, "answer": chat.answer, "citations": chat.citations}
        return TaskDetail(id=chat.id, type="问答", title="智能问答", summary=chat.question, payload=payload, created_at=chat.created_at.isoformat())
    form = db.get(FormFillResult, task_id)
    if form:
        return TaskDetail(id=form.id, type="表单", title=form.template_name, summary="表单预填结果", payload=form.result, created_at=form.created_at.isoformat())
    workflow = db.get(WorkflowRun, task_id)
    if workflow:
        return TaskDetail(id=workflow.id, type="待办", title="流程计划", summary=workflow.result.get("summary", ""), payload=workflow.result, created_at=workflow.created_at.isoformat())
    tool = db.get(ToolLog, task_id)
    if tool:
        payload = {"input": tool.input_payload, "output": tool.output_payload}
        return TaskDetail(id=tool.id, type="留痕", title=tool.task_name, summary=f"{tool.tool_name} / {tool.status}", payload=payload, created_at=tool.created_at.isoformat())
    raise HTTPException(status_code=404, detail="Task not found.")


@router.post("/records/save", response_model=HistoryItem)
def save_record(req: SaveRecordRequest, db: Session = Depends(get_db)):
    log = ToolLog(
        task_name=req.task_name,
        tool_name=req.tool_name,
        status=req.status,
        input_payload=req.input_payload,
        output_payload=req.output_payload,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return HistoryItem(id=log.id, type="留痕", title=log.task_name, summary=f"{log.tool_name} / {log.status}", created_at=log.created_at.isoformat())
