"""Helpers for workflow sessions and resumable task history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import SessionEvent, SessionRecord


def ensure_session(db: Session, session_id: int | None, scenario: str, name: str | None = None) -> SessionRecord:
    if session_id:
        existing = db.get(SessionRecord, session_id)
        if existing:
            return existing
    record = SessionRecord(name=name or "新的办理会话", scenario=scenario)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def add_session_event(
    db: Session,
    session_id: int | None,
    scenario: str,
    event_type: str,
    title: str,
    payload: dict[str, Any],
) -> SessionRecord:
    session = ensure_session(db, session_id, scenario, name=title)
    db.add(
        SessionEvent(
            session_id=session.id,
            event_type=event_type,
            title=title,
            payload=payload,
        )
    )
    return session


def summarize_session(session: SessionRecord, events: list[SessionEvent]) -> dict[str, Any]:
    latest = next((event for event in events if event.event_type != "context"), None)
    if latest is None:
        latest = events[0] if events else None
    document_ids: list[int] = []
    for event in events:
        ids = event.payload.get("document_ids") if isinstance(event.payload, dict) else None
        if isinstance(ids, list):
            document_ids = [int(item) for item in ids if isinstance(item, int)]
            break
    return {
        "id": session.id,
        "name": session.name,
        "scenario": session.scenario,
        "summary": latest.title if latest else "暂无操作记录",
        "document_ids": document_ids,
        "created_at": session.created_at.isoformat(),
        "updated_at": (latest.created_at if latest else session.created_at).isoformat(),
    }
