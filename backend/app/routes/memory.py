"""Long-term memory routes.

Only user-confirmed values are stored here. The model may suggest what is
missing, but it does not write memory without an explicit frontend action.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import UserMemory
from app.schemas import MemoryCreateRequest, MemoryItem

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_item(memory: UserMemory) -> MemoryItem:
    return MemoryItem(
        id=memory.id,
        key=memory.key,
        value=memory.value,
        category=memory.category,
        source=memory.source,
        confirmed=memory.confirmed,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
    )


@router.get("", response_model=list[MemoryItem])
def list_memory(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(UserMemory).filter(UserMemory.confirmed.is_(True))
    if category:
        query = query.filter(UserMemory.category == category)
    items = query.order_by(UserMemory.updated_at.desc()).limit(100).all()
    return [_to_item(item) for item in items]


@router.post("", response_model=MemoryItem)
def save_memory(req: MemoryCreateRequest, db: Session = Depends(get_db)):
    key = req.key.strip()
    value = req.value.strip()
    if not key or not value:
        raise HTTPException(status_code=400, detail="记忆名称和值不能为空。")
    existing = (
        db.query(UserMemory)
        .filter(UserMemory.key == key, UserMemory.category == req.category)
        .first()
    )
    if existing:
        existing.value = value
        existing.source = req.source
        existing.confirmed = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _to_item(existing)

    memory = UserMemory(
        key=key,
        value=value,
        category=req.category,
        source=req.source,
        confirmed=True,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return _to_item(memory)


@router.delete("/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    memory = db.get(UserMemory, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    db.delete(memory)
    db.commit()
    return {"deleted": True, "memory_id": memory_id}
