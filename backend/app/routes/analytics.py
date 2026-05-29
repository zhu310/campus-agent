"""Data-analysis agent endpoints."""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, SessionEvent, SessionRecord, ToolLog
from app.routes.documents import _index_document
from app.schemas import SessionDetail, SessionEventItem, SessionItem
from app.services.data_analysis_service import analyze_files, answer_analysis_question
from app.services.session_service import ensure_session, summarize_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsChatRequest(BaseModel):
    session_id: int
    question: str


def _events_for(db: Session, session_id: int, limit: int = 80) -> list[SessionEvent]:
    return (
        db.query(SessionEvent)
        .filter(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.created_at.desc())
        .limit(limit)
        .all()
    )


def _latest_analysis(events: list[SessionEvent]) -> dict[str, Any] | None:
    for event in events:
        if event.event_type == "analytics_analysis" and isinstance(event.payload, dict):
            result = event.payload.get("result")
            if isinstance(result, dict):
                return result
    return None


def _autoname(record: SessionRecord, result: dict[str, Any], task: str) -> None:
    if record.name not in {"新建分析", "新建数据分析", "新的数据分析会话"}:
        return
    files = result.get("files", [])
    first = files[0].get("file_name") if files and isinstance(files[0], dict) else ""
    base = str(first or "数据分析").replace(".xlsx", "").replace(".xls", "").replace(".csv", "")
    record.name = f"{base[:12]}：{task[:14]}"


def _analysis_document_text(result: dict[str, Any], task: str) -> str:
    lines = [
        f"数据分析任务：{task}",
        "",
        "上传文件：",
    ]
    for item in result.get("files", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('file_name')}，识别数据块 {item.get('blocks')} 个")
    lines.extend(["", "分析结论：", str(result.get("insights") or "")])

    for block in result.get("blocks", []):
        if not isinstance(block, dict):
            continue
        lines.extend(
            [
                "",
                f"数据块：{block.get('key')}",
                f"文件：{block.get('file_name')}，工作表：{block.get('sheet')}",
                f"规模：{block.get('row_count')} 行，{block.get('column_count')} 列，缺失单元格 {block.get('missing_cells')}，缺失率 {block.get('missing_rate')}",
                "字段：",
            ]
        )
        for column in block.get("columns", [])[:30]:
            if isinstance(column, dict):
                lines.append(
                    f"- {column.get('name')}，类型 {column.get('type')}，非空 {column.get('non_null')}，缺失 {column.get('missing')}，唯一值 {column.get('unique')}"
                )
        numeric_summary = block.get("numeric_summary", [])
        if numeric_summary:
            lines.append("数值摘要：")
            for item in numeric_summary[:30]:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('column')}：最小 {item.get('min')}，最大 {item.get('max')}，均值 {item.get('mean')}，合计 {item.get('sum')}"
                    )
        preview = block.get("preview", [])
        if preview:
            lines.append("样例行：")
            for row in preview[:8]:
                lines.append(str(row))
    return "\n".join(lines)


@router.post("/sessions", response_model=SessionItem)
def create_analysis_session(db: Session = Depends(get_db)):
    record = ensure_session(db, None, "data_analysis", "新建分析")
    db.add(SessionEvent(session_id=record.id, event_type="context", title="创建数据分析会话", payload={"scenario": "data_analysis"}))
    db.commit()
    return summarize_session(record, _events_for(db, record.id))


@router.get("/sessions", response_model=list[SessionItem])
def recent_analysis_sessions(db: Session = Depends(get_db)):
    records = db.query(SessionRecord).filter(SessionRecord.scenario == "data_analysis").order_by(SessionRecord.created_at.desc()).limit(30).all()
    items = [summarize_session(record, _events_for(db, record.id, 20)) for record in records]
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return items[:20]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def analysis_session_detail(session_id: int, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None or record.scenario != "data_analysis":
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    events = _events_for(db, session_id)
    base = summarize_session(record, events)
    return {
        **base,
        "events": [
            SessionEventItem(id=item.id, event_type=item.event_type, title=item.title, payload=item.payload, created_at=item.created_at.isoformat())
            for item in reversed(events)
        ],
    }


@router.delete("/sessions/{session_id}")
def delete_analysis_session(session_id: int, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None or record.scenario != "data_analysis":
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    db.query(SessionEvent).filter(SessionEvent.session_id == session_id).delete()
    db.delete(record)
    db.commit()
    return {"deleted": True, "session_id": session_id}


@router.post("/analyze")
async def analyze_spreadsheets(
    files: List[UploadFile] = File(..., description="上传一个或多个 Excel/CSV 文件"),
    task: str = Form("请分析这批校园业务数据的整体情况、异常和后续建议"),
    session_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个文件")
    try:
        final_task = task.strip() or "请分析这批校园业务数据"
        result = await analyze_files(files, task=final_task)
        record = ensure_session(db, session_id, "data_analysis", "新建分析")
        _autoname(record, result, final_task)
        first_file = next((item.get("file_name") for item in result.get("files", []) if isinstance(item, dict)), "表格数据")
        analysis_text = _analysis_document_text(result, final_task)
        document = Document(
            filename=f"数据分析：{first_file}",
            content=analysis_text,
            source="analytics_upload",
            source_type="data_analysis",
            scenario="data_analysis",
            file_path=None,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        chunks_indexed = _index_document(
            document.id,
            document.filename,
            analysis_text,
            scenario="data_analysis",
            source_type="data_analysis",
            db=db,
        )
        result["document_id"] = document.id
        result["chunks_indexed"] = chunks_indexed
        db.add(
            SessionEvent(
                session_id=record.id,
                event_type="analytics_analysis",
                title=final_task,
                payload={"task": final_task, "document_id": document.id, "result": result},
            )
        )
        db.add(
            ToolLog(
                task_name="数据分析入库",
                tool_name="analytics_index",
                input_payload={"task": final_task, "files": result.get("files", [])},
                output_payload={"document_id": document.id, "chunks_indexed": chunks_indexed},
            )
        )
        db.commit()
        result["session_id"] = record.id
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据分析失败：{exc}") from exc


@router.post("/chat")
def chat_with_analysis(req: AnalyticsChatRequest, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, req.session_id)
    if record is None or record.scenario != "data_analysis":
        raise HTTPException(status_code=404, detail="Analysis session not found.")
    events = _events_for(db, req.session_id)
    analysis = _latest_analysis(events)
    if not analysis:
        raise HTTPException(status_code=400, detail="当前会话还没有上传表格，请先上传并分析数据。")
    history = [
        {"role": event.event_type, "title": event.title, "payload": event.payload}
        for event in reversed(events)
        if event.event_type in {"analytics_chat", "analytics_analysis"}
    ]
    answer, fallback_used = answer_analysis_question(analysis, req.question.strip(), history)
    payload = {"question": req.question, "answer": answer, "fallback_used": fallback_used}
    db.add(SessionEvent(session_id=req.session_id, event_type="analytics_chat", title=req.question[:80], payload=payload))
    db.commit()
    return payload
