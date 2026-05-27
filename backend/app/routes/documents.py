"""文档管理接口。

负责上传、解析、入库、切片、向量索引、预览和删除制度/通知/材料文件。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import Document, DocumentChunk, ToolLog
from app.schemas import DocumentDetail, DocumentItem, UploadResponse
from app.services.file_parser import extract_text_from_file
from app.services.llm_service import embed_texts
from app.services.text_utils import chunk_text
from app.services.vector_service import ensure_collection, upsert_chunks

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _index_document(
    doc_id: int,
    filename: str,
    text: str,
    scenario: str = "competition_registration",
    db: Session | None = None,
):
    """把完整文档切片后写入向量库，并同步保存 SQL 片段用于兜底检索。"""
    chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    if not chunks:
        return 0
    # 先批量生成向量，再按相同顺序构造 Qdrant point，保证片段和向量一一对应。
    vectors = embed_texts(chunks)
    ensure_collection(len(vectors[0]))
    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = f"{doc_id}_{idx}"
        point_id = abs(hash(chunk_id)) % 2147483647
        points.append(
            qmodels.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "document_id": doc_id,
                    "chunk_id": chunk_id,
                    "title": filename,
                    "filename": filename,
                    "scenario": scenario,
                    "source_type": "knowledge_base",
                    "updated_at": None,
                    "text": chunk,
                    "location": f"片段 {idx + 1}",
                },
            )
        )
    upsert_chunks(points)

    if db is not None:
        # 重新索引时清理旧片段，避免同一文档被重复召回。
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{idx}"
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    text=chunk,
                    scenario=scenario,
                    source_type="knowledge_base",
                    qdrant_point_id=abs(hash(chunk_id)) % 2147483647,
                )
            )
        db.commit()
    return len(chunks)


@router.get("", response_model=list[DocumentItem])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [
        DocumentItem(
            id=item.id,
            filename=item.filename,
            source=item.source,
            source_type=item.source_type,
            scenario=item.scenario,
            created_at=item.created_at.isoformat(),
        )
        for item in docs
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        source=doc.source,
        source_type=doc.source_type,
        scenario=doc.scenario,
        created_at=doc.created_at.isoformat(),
        content=doc.content,
        file_path=doc.file_path,
    )


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    deleted_file = False
    if doc.file_path:
        # 删除磁盘文件前确认目标仍在 uploads 目录内，避免误删项目外文件。
        upload_root = UPLOAD_DIR.resolve()
        target = Path(doc.file_path).resolve()
        if upload_root in target.parents and target.exists() and target.is_file():
            target.unlink()
            deleted_file = True
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.delete(doc)
    db.add(
        ToolLog(
            task_name="删除文件",
            tool_name="delete_document",
            input_payload={"document_id": document_id},
            output_payload={"deleted": True, "deleted_file": deleted_file},
        )
    )
    db.commit()
    return {"deleted": True, "deleted_file": deleted_file, "document_id": document_id}


@router.post("/upload", response_model=UploadResponse)
def upload_document(
    file: UploadFile = File(...),
    scenario: str = Form("competition_registration"),
    source_type: str = Form("knowledge_base"),
    db: Session = Depends(get_db),
):
    """接收上传文件，解析文本后按用途决定是否进入知识库索引。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Only pdf/docx/txt/md are supported.")

    saved_name = f"{uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / saved_name
    with open(file_path, "wb") as handle:
        handle.write(file.file.read())

    try:
        text = extract_text_from_file(str(file_path))
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}") from exc
    if not text.strip():
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail="文件中未解析到可用文本。请确认不是空白模板、扫描图片版 Word，或改用图片/PDF 上传到办理材料。")

    doc = Document(
        filename=file.filename or saved_name,
        content=text,
        source="upload",
        source_type=source_type,
        scenario=scenario,
        file_path=str(file_path),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # source_type 支持 both 或逗号组合，允许一个文件同时作为知识库和办理材料。
    source_types = {item.strip() for item in source_type.split(",") if item.strip()}
    should_index = "knowledge_base" in source_types or source_type == "both"
    stored_source_type = "both" if should_index and ("material" in source_types or source_type == "both") else source_type

    doc.source_type = stored_source_type
    chunks_indexed = 0
    if should_index:
        chunks_indexed = _index_document(doc.id, doc.filename, text, scenario=scenario, db=db)
    db.add(
        ToolLog(
            task_name="文件上传",
            tool_name="document_upload",
            input_payload={"filename": file.filename, "scenario": scenario, "source_type": stored_source_type},
            output_payload={"chunks_indexed": chunks_indexed},
        )
    )
    db.commit()
    return UploadResponse(document_id=doc.id, filename=doc.filename, chunks_indexed=chunks_indexed, status="indexed")


@router.post("/index-text", response_model=UploadResponse)
def index_text(filename: str, text: str, scenario: str = "competition_registration", db: Session = Depends(get_db)):
    doc = Document(filename=filename, content=text, source="seed", source_type="knowledge_base", scenario=scenario)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunks_indexed = _index_document(doc.id, doc.filename, text, scenario=scenario, db=db)
    return UploadResponse(document_id=doc.id, filename=doc.filename, chunks_indexed=chunks_indexed, status="indexed")
