"""材料审核相关接口。

提供字段抽取、规则审核和图片/PDF OCR 上传入口，是材料从非结构化文本进入
结构化办理流程的第一站。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditResult, AuditTask, Document, ToolLog
from app.schemas import AuditRequest, AuditResponse, ExtractFieldsRequest, ExtractFieldsResponse, OCRResponse
from app.services.audit_service import audit_material, list_rules, merge_field_details, missing_field_labels
from app.services.file_parser import extract_text_from_file
from app.services.ocr_service import parse_ocr
from app.services.security_service import redact_payload
from app.services.session_service import add_session_event

router = APIRouter(prefix="/audit", tags=["audit"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _run_audit(req: AuditRequest, db: Session) -> AuditResponse:
    task = AuditTask(
        material_name=req.material_name,
        scenario=req.scenario,
        source_text=req.text,
        status="running",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    rules = list_rules(db, req.scenario)
    result = audit_material(req.material_name, req.text, req.scenario, rules, extra_fields=req.ocr_fields)
    task.status = result["level"]
    db.add(AuditResult(task_id=task.id, level=result["level"], result=result))
    db.add(
        ToolLog(
            task_name="规则审核",
            tool_name="validate_rules",
            status=result["level"],
            input_payload=redact_payload({"material_name": req.material_name, "scenario": req.scenario}),
            output_payload=redact_payload({
                "missing_items": result["missing_items"],
                "level": result["level"],
                "needs_human_review": result.get("needs_human_review"),
            }),
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "audit",
            "材料审核",
            {
                "material_name": req.material_name,
                "result": redact_payload(result),
                "document_ids": req.document_ids,
            },
        )
    db.commit()
    return AuditResponse(**result)


@router.post("", response_model=AuditResponse)
def audit(req: AuditRequest, db: Session = Depends(get_db)):
    return _run_audit(req, db)


@router.post("/run", response_model=AuditResponse)
def audit_run(req: AuditRequest, db: Session = Depends(get_db)):
    return _run_audit(req, db)


@router.post("/extract-fields", response_model=ExtractFieldsResponse)
def extract_material_fields(req: ExtractFieldsRequest, db: Session = Depends(get_db)):
    details = merge_field_details(req.text, req.ocr_fields, scenario=req.scenario)
    fields = details["recognized_fields"]
    missing = missing_field_labels(fields, req.scenario)
    db.add(
        ToolLog(
            task_name="字段抽取",
            tool_name="extract_fields",
            input_payload={"scenario": req.scenario},
            output_payload=redact_payload({"fields": fields, "missing_fields": missing}),
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "fields",
            "信息抽取",
            {
                "fields": redact_payload(fields),
                "missing_fields": missing,
                "document_ids": req.document_ids,
            },
        )
    db.commit()
    return ExtractFieldsResponse(
        fields=fields,
        open_fields=details["open_fields"],
        synonym_fields=details["synonym_fields"],
        document_structure=details["document_structure"],
        raw_fields=details["raw_fields"],
        field_matches=details["field_matches"],
        unmapped_fields=details["unmapped_fields"],
        missing_fields=missing,
        scenario=req.scenario,
    )


@router.post("/upload", response_model=OCRResponse)
def audit_upload(
    file: UploadFile = File(...),
    scenario: str = Form("competition_registration"),
    display_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".doc":
        raise HTTPException(status_code=400, detail="暂不支持 .doc 老 Word 格式，请另存为 .docx、PDF 或 txt 后上传。")
    if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="办理材料支持 png/jpg/jpeg/bmp/webp/pdf/docx/txt/md。")
    saved_name = f"{uuid4().hex}{suffix}"
    file_path = UPLOAD_DIR / saved_name
    with open(file_path, "wb") as handle:
        while chunk := file.file.read(1024 * 1024):
            handle.write(chunk)

    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"}:
        parsed = parse_ocr(str(file_path), scenario=scenario)
        if not parsed.get("text", "").strip():
            if file_path.exists():
                file_path.unlink()
            if suffix == ".pdf":
                raise HTTPException(status_code=400, detail="PDF 中未解析到可复制文本；如果是扫描版 PDF，请先转为图片或使用 OCR 工具识别后再上传。")
            raise HTTPException(status_code=400, detail="图片 OCR 未解析到文本，请确认图片清晰或 OCR 依赖已安装。")
    else:
        try:
            text = extract_text_from_file(str(file_path))
        except Exception as exc:
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=400, detail=f"材料文件解析失败：{exc}") from exc
        if not text.strip():
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=400, detail="材料文件中未解析到可用文本，请确认不是空白模板或图片版 Word。")
        details = merge_field_details(text, {}, scenario=scenario)
        fields = details["recognized_fields"]
        parsed = {
            "engine": "document-parser",
            "text": text,
            "extracted_fields": fields,
            "open_fields": details["open_fields"],
            "document_structure": details["document_structure"],
            "raw_fields": details["raw_fields"],
            "field_matches": details["field_matches"],
            "unmapped_fields": details["unmapped_fields"],
            "lines": [line for line in text.splitlines() if line.strip()],
            "fallback_used": False,
        }
    visible_name = (display_name or "").strip() or file.filename or saved_name
    db.add(
        Document(
            filename=visible_name,
            content=parsed["text"],
            source="upload",
            source_type="material",
            scenario=scenario,
            file_path=str(file_path),
        )
    )
    db.add(
        ToolLog(
            task_name="材料上传与OCR",
            tool_name="ocr_parse_file",
            status="fallback" if parsed["fallback_used"] else "completed",
            input_payload={"filename": visible_name, "original_filename": file.filename},
            output_payload=redact_payload({"lines": len(parsed["lines"]), "fields": parsed["extracted_fields"]}),
        )
    )
    db.commit()
    return OCRResponse(
        filename=visible_name,
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
