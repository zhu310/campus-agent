"""Document structure extraction service.

This layer is intentionally business-agnostic: it recovers paragraphs, tables,
key-value pairs and section blocks from parsed text, but does not decide whether
"姓名" means a team leader, applicant, reimburser, or something else.
"""

from __future__ import annotations

import re
from typing import Any


LABEL_MAX_LENGTH = 40
SECTION_TITLE_RE = re.compile(r"^[一二三四五六七八九十\d]+[、.．]\s*(.{2,40})$")


def clean_cell(value: Any) -> str:
    value = str(value or "").replace("\r", "\n").strip()
    value = re.sub(r"\n{2,}", "\n", value)
    value = re.sub(r"\s+\|", " |", value)
    value = re.sub(r"\|\s+", "| ", value)
    return value.strip(":：,，;； ")


def _looks_like_label(value: str) -> bool:
    value = clean_cell(value)
    if not value or len(value) > LABEL_MAX_LENGTH:
        return False
    if re.search(r"[。！？!?，,；;]", value):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", value))


def _label_signature(value: str) -> str:
    return re.sub(r"\s+", "", clean_cell(value)).lower()


COMMON_FORM_LABELS = {
    "姓名", "性别", "出生年月", "民族", "政治面貌", "入学时间", "学号", "所在年级",
    "身份证号码", "联系电话", "学院", "学院系", "专业", "班", "曾获何种奖励",
    "家庭人口总数", "家庭月总收入", "人均月收入", "收入来源", "家庭住址", "邮政编码",
    "困难情况认定档次", "成绩排名", "申请理由", "申请人签名", "院系审核意见", "学校审核意见",
}


def _is_common_form_label(value: str) -> bool:
    signature = _label_signature(value)
    return signature in COMMON_FORM_LABELS or any(label in signature and len(signature) <= len(label) + 4 for label in COMMON_FORM_LABELS)


def _location(line_no: int, page: int | None = None) -> str:
    if page:
        return f"第 {page} 页，第 {line_no} 行"
    return f"第 {line_no} 行"


def _table_cells(line: str) -> list[str]:
    if "|" not in line:
        return []
    return [clean_cell(cell) for cell in line.split("|") if clean_cell(cell)]


def _extract_table_blocks(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_rows: list[list[str]] = []
    start_line = 0

    def flush() -> None:
        nonlocal current_rows, start_line
        if not current_rows:
            return
        table_id = f"table_{len(blocks) + 1}"
        blocks.append(
            {
                "type": "table",
                "table_id": table_id,
                "rows": current_rows,
                "cells": [
                    {
                        "row": row_index,
                        "col": col_index,
                        "text": cell,
                        "location": _location(start_line + row_index),
                    }
                    for row_index, row in enumerate(current_rows)
                    for col_index, cell in enumerate(row)
                ],
                "line": start_line,
                "location": _location(start_line),
                "text": "\n".join(" | ".join(row) for row in current_rows),
            }
        )
        current_rows = []
        start_line = 0

    for line_no, line in lines:
        cells = _table_cells(line)
        if cells:
            if not current_rows:
                start_line = line_no
            current_rows.append(cells)
        else:
            flush()
    flush()
    return blocks


def _extract_kv_blocks(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    colon_pattern = re.compile(r"^\s*([^:：|]{2,40})\s*[:：]\s*(.+?)\s*$")

    for line_no, line in lines:
        match = colon_pattern.match(line)
        if not match:
            continue
        label = clean_cell(match.group(1))
        value = clean_cell(match.group(2))
        if _looks_like_label(label) and value:
            blocks.append(
                {
                    "type": "kv",
                    "label": label,
                    "value": value,
                    "line": line_no,
                    "location": _location(line_no),
                    "text": f"{label}: {value}",
                    "method": "label_colon_value",
                }
            )

    # Some OCR and Word templates put labels and values on adjacent lines.
    index = 0
    while index < len(lines) - 1:
        line_no, label = lines[index]
        _, value = lines[index + 1]
        if any(mark in label for mark in ":：|") or any(mark in value for mark in ":：|"):
            index += 1
            continue
        if _looks_like_label(label) and value and not _looks_like_label(value):
            blocks.append(
                {
                    "type": "kv",
                    "label": clean_cell(label),
                    "value": clean_cell(value),
                    "line": line_no,
                    "location": _location(line_no),
                    "text": f"{clean_cell(label)}: {clean_cell(value)}",
                    "method": "adjacent_line_pair",
                }
            )
            index += 2
        else:
            index += 1
    return blocks


def _extract_table_kv_blocks(table_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for table in table_blocks:
        for row_index, row in enumerate(table.get("rows", []), start=0):
            index = 0
            while index < len(row) - 1:
                label = clean_cell(row[index])
                value = clean_cell(row[index + 1])
                pairwise_row = len(row) % 2 == 0
                if _looks_like_label(label) and value and not _is_common_form_label(value) and (pairwise_row or not _looks_like_label(value)):
                    line_no = int(table.get("line") or 1) + row_index
                    blocks.append(
                        {
                            "type": "kv",
                            "table_id": table.get("table_id"),
                            "row": row_index,
                            "label_col": index,
                            "value_col": index + 1,
                            "label": label,
                            "value": value,
                            "line": line_no,
                            "location": _location(line_no),
                            "text": f"{label}: {value}",
                            "method": "table_pair",
                        }
                    )
                    index += 2
                else:
                    index += 1
    return blocks


def _extract_section_blocks(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_title = ""
    current_line = 0
    current_content: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_line, current_content
        if current_title and current_content:
            blocks.append(
                {
                    "type": "section",
                    "title": current_title,
                    "content": "\n".join(current_content).strip(),
                    "line": current_line,
                    "location": _location(current_line),
                    "text": f"{current_title}\n" + "\n".join(current_content).strip(),
                }
            )
        current_title = ""
        current_line = 0
        current_content = []

    for line_no, line in lines:
        title_match = SECTION_TITLE_RE.match(line)
        is_short_heading = _looks_like_label(line) and len(line) <= 18 and not _table_cells(line)
        if title_match or is_short_heading:
            flush()
            current_title = clean_cell(title_match.group(1) if title_match else line)
            current_line = line_no
            continue
        if current_title:
            current_content.append(line)
    flush()
    return blocks


def build_document_structure(text: str, source: str = "parsed_text") -> dict[str, Any]:
    """Return a stable intermediate representation for downstream agents."""
    normalized = (text or "").replace("\r", "\n")
    lines = [(line_no, clean_cell(line)) for line_no, line in enumerate(normalized.splitlines(), start=1) if clean_cell(line)]
    table_blocks = _extract_table_blocks(lines)
    kv_blocks = _extract_kv_blocks(lines) + _extract_table_kv_blocks(table_blocks)
    section_blocks = _extract_section_blocks(lines)
    paragraph_blocks = [
        {"type": "paragraph", "text": line, "line": line_no, "location": _location(line_no)}
        for line_no, line in lines
        if "|" not in line
    ]
    structured_line_numbers = {
        int(item.get("line") or 0)
        for item in table_blocks + kv_blocks + section_blocks
        if item.get("line")
    }
    coverage = len(structured_line_numbers) / max(1, len(lines))
    confidence = min(
        0.98,
        0.35
        + min(0.35, len(kv_blocks) * 0.04)
        + min(0.2, len(table_blocks) * 0.1)
        + min(0.1, coverage * 0.1),
    )
    return {
        "source": source,
        "plain_text": normalized,
        "lines": [{"line": line_no, "text": line, "location": _location(line_no)} for line_no, line in lines],
        "blocks": table_blocks + kv_blocks + section_blocks + paragraph_blocks,
        "tables": table_blocks,
        "key_values": kv_blocks,
        "sections": section_blocks,
        "quality": {
            "line_count": len(lines),
            "table_count": len(table_blocks),
            "key_value_count": len(kv_blocks),
            "section_count": len(section_blocks),
            "structured_line_coverage": round(coverage, 3),
            "confidence": round(confidence, 3),
            "needs_human_review": confidence < 0.55 or (not table_blocks and not kv_blocks and len(lines) > 3),
        },
    }
