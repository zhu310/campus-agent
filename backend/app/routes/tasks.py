"""任务历史兼容接口。

这些路径复用 history 模块的实现，给前端保留更直观的 /tasks 命名。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routes.history import recent_tasks_alias, save_record, task_detail
from app.schemas import HistoryItem, SaveRecordRequest, TaskDetail

router = APIRouter(tags=["tasks"])


@router.get("/tasks/recent", response_model=list[HistoryItem])
def tasks_recent(db: Session = Depends(get_db)):
    return recent_tasks_alias(db)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def tasks_detail(task_id: int, db: Session = Depends(get_db)):
    return task_detail(task_id, db)


@router.post("/records/save", response_model=HistoryItem)
def records_save(req: SaveRecordRequest, db: Session = Depends(get_db)):
    return save_record(req, db)
