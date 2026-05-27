"""文件文本解析服务。

支持 txt/md/docx/pdf 的文本提取，其中 docx 会额外兜底读取 XML，提升模板类
文档的解析成功率。
"""

from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional runtime dependency
    pdfplumber = None

try:
    from docx import Document as DocxDocument
except Exception:  # pragma: no cover - optional runtime dependency
    DocxDocument = None


def _extract_docx_xml_text(file_path: str) -> str:
    texts: list[str] = []
    namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    }
    try:
        with ZipFile(file_path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.startswith("word/")
                and name.endswith(".xml")
                and (
                    name == "word/document.xml"
                    or name.startswith("word/header")
                    or name.startswith("word/footer")
                    or name.startswith("word/footnotes")
                    or name.startswith("word/endnotes")
                )
            ]
            for name in names:
                root = ET.fromstring(archive.read(name))
                for node in root.findall(".//w:t", namespaces):
                    if node.text and node.text.strip():
                        texts.append(node.text.strip())
                for node in root.findall(".//w:tab", namespaces):
                    texts.append("\t")
                for node in root.findall(".//w:br", namespaces):
                    texts.append("\n")
    except (BadZipFile, ET.ParseError, KeyError):
        return ""
    return "\n".join(texts)


def extract_text_from_file(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {'.txt', '.md'}:
        return path.read_text(encoding='utf-8', errors='ignore')

    if suffix == '.pdf':
        if pdfplumber is None:
            raise ValueError('PDF parsing requires pdfplumber. Please install backend requirements.')
        texts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                if page_text.strip():
                    texts.append(page_text)
                for table in page.extract_tables() or []:
                    for row in table or []:
                        cells = [str(cell or '').strip() for cell in row if str(cell or '').strip()]
                        if cells:
                            texts.append(' | '.join(cells))
        return '\n'.join(texts)

    if suffix == '.docx':
        texts = []
        if DocxDocument is not None:
            doc = DocxDocument(file_path)
            paragraphs = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            table_lines = []
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        table_lines.append(' | '.join(cells))
            texts.append('\n'.join(paragraphs + table_lines))
        texts.append(_extract_docx_xml_text(file_path))
        merged_lines: list[str] = []
        seen_lines: set[str] = set()
        for block in texts:
            for line in block.splitlines():
                line = line.strip()
                if line and line not in seen_lines:
                    seen_lines.add(line)
                    merged_lines.append(line)
        return "\n".join(merged_lines)

    raise ValueError(f'Unsupported file type: {suffix}')
