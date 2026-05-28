"""Document management routes.

Uploads are parsed into full document text and SQL chunks. Qdrant indexing is
best-effort so the app can still answer questions when the vector service is not
running.
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
    """Index parsed text into SQL chunks and, when available, Qdrant."""
    chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    if not chunks:
        return 0

    try:
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
    except Exception:
        pass

    if db is not None:
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
    display_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".doc":
        raise HTTPException(status_code=400, detail="暂不支持 .doc 老 Word 格式，请另存为 .docx、PDF 或 txt 后上传。")
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="仅支持 pdf/docx/txt/md。")

    saved_name = f"{uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / saved_name
    with open(file_path, "wb") as handle:
        while chunk := file.file.read(1024 * 1024):
            handle.write(chunk)

    try:
        text = extract_text_from_file(str(file_path))
    except Exception as exc:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}") from exc
    if not text.strip():
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail="文件中未解析到可用文本，请确认文件不是空白模板或扫描图片。")

    visible_name = (display_name or "").strip() or file.filename or saved_name
    source_types = {item.strip() for item in source_type.split(",") if item.strip()}
    should_index = "knowledge_base" in source_types or source_type == "both"
    stored_source_type = "both" if should_index and ("material" in source_types or source_type == "both") else source_type

    doc = Document(
        filename=visible_name,
        content=text,
        source="upload",
        source_type=stored_source_type,
        scenario=scenario,
        file_path=str(file_path),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks_indexed = 0
    if should_index:
        chunks_indexed = _index_document(doc.id, doc.filename, text, scenario=scenario, db=db)

    db.add(
        ToolLog(
            task_name="文件上传",
            tool_name="document_upload",
            input_payload={
                "filename": visible_name,
                "original_filename": file.filename,
                "scenario": scenario,
                "source_type": stored_source_type,
            },
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
