"""Helpers for workflow sessions and resumable task history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, SessionEvent, SessionRecord


PLACEHOLDER_NAMES = {"新建对话", "新的办理会话", "创建办理会话", ""}


def _shorten(text: str, limit: int = 18) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit] if len(compact) <= limit else f"{compact[:limit]}..."


def _document_label(db: Session, document_ids: list[Any]) -> str:
    ids = [int(item) for item in document_ids if isinstance(item, int) or str(item).isdigit()]
    if not ids:
        return ""
    doc = db.query(Document).filter(Document.id.in_(ids)).order_by(Document.id.asc()).first()
    if not doc:
        return ""
    first_line = next((line.strip() for line in (doc.content or "").splitlines() if line.strip()), "")
    raw = first_line or doc.filename
    return _shorten(raw.replace(".docx", "").replace(".pdf", "").replace(".txt", ""), 12)


def _maybe_autoname_session(db: Session, session: SessionRecord, event_type: str, title: str, payload: dict[str, Any]) -> None:
    if session.name not in PLACEHOLDER_NAMES or event_type == "context":
        return
    document_label = _document_label(db, payload.get("document_ids") if isinstance(payload, dict) else [])
    if event_type == "answer":
        action_label = _shorten(str(payload.get("question") or title), 14)
    elif event_type == "tasks":
        action_label = "办理流程"
    elif event_type == "audit":
        action_label = "材料审核"
    elif event_type == "fill_review":
        action_label = "填写审核"
    else:
        action_label = _shorten(title, 14)
    session.name = f"{document_label}：{action_label}" if document_label else action_label


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
    _maybe_autoname_session(db, session, event_type, title, payload)
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
