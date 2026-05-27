"""OCR 解析接口。

接收图片或 PDF 材料，抽取文本和字段后返回给材料审核流程继续使用。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, ToolLog
from app.schemas import OCRResponse
from app.services.ocr_service import parse_ocr

router = APIRouter(prefix="/ocr", tags=["ocr"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/parse", response_model=OCRResponse)
def ocr_parse(file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"}:
        raise HTTPException(status_code=400, detail="Only image and pdf files are supported for OCR.")

    saved_name = f"{uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / saved_name
    with open(file_path, "wb") as handle:
        handle.write(file.file.read())

    parsed = parse_ocr(str(file_path))
    db.add(
        Document(
            filename=file.filename or saved_name,
            content=parsed["text"],
            source="upload",
            source_type="ocr_material",
            scenario="competition_registration",
            file_path=str(file_path),
        )
    )
    db.add(
        ToolLog(
            task_name="OCR识别",
            tool_name="ocr_parse_file",
            status="fallback" if parsed["fallback_used"] else "completed",
            input_payload={"filename": file.filename},
            output_payload={"lines": len(parsed["lines"]), "fields": parsed["extracted_fields"]},
        )
    )
    db.commit()
    return OCRResponse(
        filename=file.filename or saved_name,
        engine=parsed["engine"],
        text=parsed["text"],
        extracted_fields=parsed["extracted_fields"],
        open_fields=parsed.get("open_fields", {}),
        document_structure=parsed.get("document_structure", {}),
        raw_fields=parsed.get("raw_fields", []),
        field_matches=parsed.get("field_matches", []),
        unmapped_fields=parsed.get("unmapped_fields", []),
        lines=parsed["lines"],
        fallback_used=parsed["fallback_used"],
    )
