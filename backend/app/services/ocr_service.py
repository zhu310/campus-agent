"""OCR 解析服务。

优先使用 PaddleOCR 识别图片/PDF，依赖不可用时返回解析降级标记，便于前端提示
用户改用文本材料或可复制 PDF。
"""

from pathlib import Path
from typing import Any, Dict, List
from app.services.audit_service import merge_field_details

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional runtime dependency
    pdfplumber = None

try:
    from paddleocr import PaddleOCR  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PaddleOCR = None


_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None and PaddleOCR is not None:
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch")
    return _ocr_instance


def _ocr_image(file_path: str) -> tuple[str, List[str], bool]:
    engine = _get_ocr()
    if engine is None:
        return "", [], True
    result = engine.ocr(file_path, cls=True)
    lines: List[str] = []
    for page in result or []:
        for row in page or []:
            if row and len(row) > 1 and row[1]:
                lines.append(str(row[1][0]).strip())
    text = "\n".join(lines)
    return text, lines, False


def _ocr_pdf(file_path: str) -> tuple[str, List[str], bool]:
    if pdfplumber is None:
        return "", [], True
    texts: List[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                texts.extend(line.strip() for line in page_text.splitlines() if line.strip())
            for table in page.extract_tables() or []:
                for row in table or []:
                    cells = [str(cell or "").strip() for cell in row if str(cell or "").strip()]
                    if cells:
                        texts.append(" | ".join(cells))
    text = "\n".join(texts)
    return text, texts, True


def parse_ocr(file_path: str, scenario: str = "competition_registration") -> Dict[str, Any]:
    suffix = Path(file_path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        text, lines, fallback_used = _ocr_image(file_path)
        engine = "PaddleOCR" if not fallback_used else "PaddleOCR unavailable"
    elif suffix == ".pdf":
        text, lines, fallback_used = _ocr_pdf(file_path)
        engine = "PDF text extraction"
    else:
        raise ValueError(f"Unsupported OCR file type: {suffix}")
    details = merge_field_details(text, scenario=scenario)
    return {
        "engine": engine,
        "text": text,
        "lines": lines,
        "extracted_fields": details["recognized_fields"],
        "open_fields": details["open_fields"],
        "document_structure": details["document_structure"],
        "raw_fields": details["raw_fields"],
        "field_matches": details["field_matches"],
        "unmapped_fields": details["unmapped_fields"],
        "fallback_used": fallback_used,
    }
