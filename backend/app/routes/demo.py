"""演示数据接口。

用于比赛/演示环境快速导入样例通知和材料，保证评委打开系统就能跑通流程。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document
from app.routes.documents import _index_document
from app.schemas import DemoAsset, UploadResponse
from app.services.demo_seed import CONTEST_NOTICE_TEXT, MATERIAL_SAMPLE_COMPLETE, MATERIAL_SAMPLE_INCOMPLETE, REGISTRATION_TEMPLATE

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/load-contest-notice", response_model=UploadResponse)
def load_contest_notice(db: Session = Depends(get_db)):
    existing = db.query(Document).filter(Document.filename == "比赛通知示例.txt").first()
    if existing:
        chunks = _index_document(existing.id, existing.filename, existing.content, scenario=existing.scenario, db=db)
        return UploadResponse(document_id=existing.id, filename=existing.filename, chunks_indexed=chunks, status="indexed")

    doc = Document(
        filename="比赛通知示例.txt",
        content=CONTEST_NOTICE_TEXT,
        source="seed",
        source_type="knowledge_base",
        scenario="competition_registration",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunks = _index_document(doc.id, doc.filename, doc.content, scenario=doc.scenario, db=db)
    db.commit()
    return UploadResponse(document_id=doc.id, filename=doc.filename, chunks_indexed=chunks, status="indexed")


@router.get("/assets", response_model=list[DemoAsset])
def list_demo_assets():
    return [
        DemoAsset(name="比赛通知文本", type="knowledge", content=CONTEST_NOTICE_TEXT),
        DemoAsset(name="报名表模板", type="template", content=REGISTRATION_TEMPLATE),
        DemoAsset(name="缺失项样例材料", type="material", content=MATERIAL_SAMPLE_INCOMPLETE),
        DemoAsset(name="完整样例材料", type="material", content=MATERIAL_SAMPLE_COMPLETE),
    ]
