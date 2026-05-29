"""知识库索引接口。

用于对已有文档重新切片并写入向量库，通常在文档内容更新后调用。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, ToolLog
from app.routes.documents import _index_document
from app.schemas import UploadResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/index", response_model=UploadResponse)
def index_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks_indexed = _index_document(
        doc.id,
        doc.filename,
        doc.content,
        scenario=doc.scenario,
        source_type=doc.source_type,
        db=db,
    )
    db.add(
        ToolLog(
            task_name="知识库重新索引",
            tool_name="search_knowledge",
            input_payload={"document_id": document_id},
            output_payload={"chunks_indexed": chunks_indexed},
        )
    )
    db.commit()
    return UploadResponse(document_id=doc.id, filename=doc.filename, chunks_indexed=chunks_indexed, status="indexed")
