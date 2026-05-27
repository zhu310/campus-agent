"""人工复核接口。

真实落地时，机器抽取不能直接等同于最终结论；这里提供复核记录的创建、修改和
查询，让字段修正、风险确认和审计轨迹形成闭环。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import HumanReviewRecord, ToolLog
from app.schemas import ReviewCreateRequest, ReviewResponse, ReviewUpdateRequest
from app.services.security_service import redact_payload

router = APIRouter(prefix="/review", tags=["review"])


def _to_response(record: HumanReviewRecord) -> ReviewResponse:
    return ReviewResponse(
        id=record.id,
        task_id=record.task_id,
        material_name=record.material_name,
        scenario=record.scenario,
        status=record.status,
        original_payload=record.original_payload,
        corrected_fields=record.corrected_fields,
        notes=record.notes,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.post("/records", response_model=ReviewResponse)
def create_review_record(req: ReviewCreateRequest, db: Session = Depends(get_db)):
    record = HumanReviewRecord(
        task_id=req.task_id,
        material_name=req.material_name,
        scenario=req.scenario,
        original_payload=req.original_payload,
        corrected_fields=req.corrected_fields,
        notes=req.notes,
    )
    db.add(record)
    db.add(
        ToolLog(
            task_name="人工复核",
            tool_name="human_review_create",
            status="pending",
            input_payload=redact_payload({"task_id": req.task_id, "material_name": req.material_name, "scenario": req.scenario}),
            output_payload={"created": True},
        )
    )
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.patch("/records/{record_id}", response_model=ReviewResponse)
def update_review_record(record_id: int, req: ReviewUpdateRequest, db: Session = Depends(get_db)):
    record = db.get(HumanReviewRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review record not found.")
    record.corrected_fields = req.corrected_fields
    record.status = req.status
    record.notes = req.notes
    db.add(
        ToolLog(
            task_name="人工复核",
            tool_name="human_review_update",
            status=req.status,
            input_payload={"record_id": record_id},
            output_payload=redact_payload({"corrected_fields": req.corrected_fields}),
        )
    )
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.get("/records", response_model=list[ReviewResponse])
def list_review_records(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(HumanReviewRecord)
    if status:
        query = query.filter(HumanReviewRecord.status == status)
    records = query.order_by(HumanReviewRecord.created_at.desc()).limit(50).all()
    return [_to_response(record) for record in records]
