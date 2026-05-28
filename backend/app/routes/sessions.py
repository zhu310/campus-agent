"""Workflow session routes used to restore recent Copilot tasks."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SessionEvent, SessionRecord
from app.schemas import (
    SessionCreateRequest,
    SessionDetail,
    SessionEventCreateRequest,
    SessionEventItem,
    SessionItem,
    SessionUpdateRequest,
)
from app.services.session_service import ensure_session, summarize_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _events_for(db: Session, session_id: int, limit: int = 50) -> list[SessionEvent]:
    return (
        db.query(SessionEvent)
        .filter(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("", response_model=SessionItem)
def create_session(req: SessionCreateRequest, db: Session = Depends(get_db)):
    record = ensure_session(db, None, req.scenario, req.name)
    db.add(
        SessionEvent(
            session_id=record.id,
            event_type="context",
            title="创建办理会话",
            payload={"document_ids": req.document_ids, "scenario": req.scenario},
        )
    )
    db.commit()
    return summarize_session(record, _events_for(db, record.id))


@router.get("/recent", response_model=list[SessionItem])
def recent_sessions(db: Session = Depends(get_db)):
    records = db.query(SessionRecord).order_by(SessionRecord.created_at.desc()).limit(30).all()
    items = [summarize_session(record, _events_for(db, record.id, limit=10)) for record in records]
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return items[:20]


@router.get("/{session_id}", response_model=SessionDetail)
def session_detail(session_id: int, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    events = _events_for(db, session_id, limit=80)
    base = summarize_session(record, events)
    return {
        **base,
        "events": [
            SessionEventItem(
                id=item.id,
                event_type=item.event_type,
                title=item.title,
                payload=item.payload,
                created_at=item.created_at.isoformat(),
            )
            for item in reversed(events)
        ],
    }


@router.patch("/{session_id}", response_model=SessionItem)
def rename_session(session_id: int, req: SessionUpdateRequest, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    record.name = req.name.strip()
    db.add(
        SessionEvent(
            session_id=record.id,
            event_type="context",
            title="重命名办理会话",
            payload={"name": record.name},
        )
    )
    db.commit()
    return summarize_session(record, _events_for(db, record.id))


@router.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    db.query(SessionEvent).filter(SessionEvent.session_id == session_id).delete()
    db.delete(record)
    db.commit()
    return {"deleted": True, "session_id": session_id}


@router.post("/{session_id}/events", response_model=SessionEventItem)
def add_event(session_id: int, req: SessionEventCreateRequest, db: Session = Depends(get_db)):
    record = db.get(SessionRecord, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    event = SessionEvent(session_id=session_id, event_type=req.event_type, title=req.title, payload=req.payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return SessionEventItem(
        id=event.id,
        event_type=event.event_type,
        title=event.title,
        payload=event.payload,
        created_at=event.created_at.isoformat(),
    )
