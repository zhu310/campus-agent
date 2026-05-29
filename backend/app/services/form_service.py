"""Template-driven form draft generation.

This module intentionally avoids scenario-specific form field lists. When a
template/form document is supplied, the output fields are recovered from that
document itself; user-provided material is only used as a source of values for
those recovered fields.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict

from app.services.audit_service import merge_field_details
from app.services.document_structure_service import build_document_structure, clean_cell


GENERIC_SCENARIOS = {"", "generic", "general", "other", "custom", "其他", "其他场景", "自定义场景"}

LABEL_CONCEPTS = {
    "contact": ["联系", "电话", "手机", "号码"],
    "person": ["姓名", "申请人", "负责人", "联系人"],
    "student_id": ["学号", "学生编号"],
    "id_number": ["身份证", "证件"],
    "email": ["邮箱", "email", "e-mail"],
    "date": ["时间", "日期", "年月", "起止"],
    "rank": ["排名", "名次"],
    "address": ["地址", "住址", "地点"],
    "income": ["收入", "金额", "费用"],
    "count": ["人数", "人口", "总数", "门数"],
    "school_class": ["学院", "专业", "班级", "年级", "学校", "大学"],
}

VALUE_TYPE_PATTERNS = {
    "email": re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"),
    "phone": re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$|^\d{3,4}[- ]?\d{6,8}$"),
    "id_number": re.compile(r"^\d{15}$|^\d{17}[\dXx]$"),
    "date": re.compile(r"\d{4}[./年-]\d{1,2}(?:[./月-]\d{1,2}日?)?(?:\s*[-至到]\s*\d{4}?[./年-]?\d{1,2}(?:[./月-]?\d{1,2}日?)?)?"),
    "rank": re.compile(r"^\d+\s*/\s*\d+"),
    "number": re.compile(r"^\d+(?:\.\d+)?$"),
}


def _is_generic_scenario(scenario: str | None) -> bool:
    if scenario is None:
        return True
    return str(scenario).strip().lower() in GENERIC_SCENARIOS


def _label_signature(value: str) -> str:
    return "".join(ch for ch in clean_cell(value) if ch.isalnum() or "\u4e00" <= ch <= "\u9fff").lower()


def _is_probable_value(value: str) -> bool:
    text = clean_cell(value)
    signature = _label_signature(text)
    if not signature:
        return True
    if signature.isdigit():
        return True
    if len(text) > 48:
        return True
    if any(mark in text for mark in "☑√✓■●") and not any(mark in text for mark in ":："):
        return True
    if "公章" in text or text in {"年 月 日", "年月日"}:
        return True
    return False


def _normalize_template_label(value: str) -> str:
    text = clean_cell(value)
    if not text:
        return ""
    if "：" in text or ":" in text:
        text = text.replace("：", ":").split(":", 1)[0]
    parts = text.split()
    if parts and all(len(part) == 1 for part in parts):
        text = "".join(parts)
    elif len(parts) > 1:
        text = "、".join(parts)
    else:
        text = " ".join(text.split())
    return text.strip(" /|")


def _should_skip_template_label(label: str) -> bool:
    signature = _label_signature(label)
    if not signature:
        return True
    if signature.endswith("情况") and len(signature) <= 8:
        return True
    if signature in {"学习成绩"}:
        return True
    if any(word in signature for word in ["申请表", "审批表", "审核", "意见", "公章", "签名"]):
        return True
    if any(ch.isdigit() for ch in signature) and not any(word in signature for word in ["排名", "年级", "身份证", "邮政编码"]):
        return True
    return False


def _is_section_heading(value: str, row: list[str], col_index: int) -> bool:
    signature = _label_signature(value)
    if not signature:
        return True
    return bool(col_index == 0 and len(row) > 2)


def _extract_template_labels(template_text: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        label = _normalize_template_label(value)
        signature = _label_signature(label)
        if not label or not signature or signature in seen:
            return
        if _is_probable_value(label) or _should_skip_template_label(label):
            return
        seen.add(signature)
        labels.append(label)

    structure = build_document_structure(template_text)
    for table in structure.get("tables", []):
        for row in table.get("rows", []):
            for col_index, cell in enumerate(row):
                text = clean_cell(cell)
                if not text:
                    continue
                if _is_section_heading(text, row, col_index):
                    continue
                add(text)

    for line in template_text.splitlines():
        text = clean_cell(line)
        if not text or "|" in text:
            continue
        add(text)
    return labels


def _match_score(template_label: str, source_label: str) -> float:
    left = _label_signature(template_label)
    right = _label_signature(source_label)
    if not left or not right:
        return 0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.88
    shared = len(set(left) & set(right))
    overlap = shared / max(1, min(len(left), len(right)))
    sequence = SequenceMatcher(None, left, right).ratio()
    return max(overlap, sequence)


def _label_concepts(label: str) -> set[str]:
    signature = _label_signature(label)
    concepts: set[str] = set()
    for concept, terms in LABEL_CONCEPTS.items():
        if any(term.lower().replace("-", "") in signature for term in terms):
            concepts.add(concept)
    return concepts


def _value_type(value: str) -> str:
    text = clean_cell(value).replace(" ", "")
    for kind, pattern in VALUE_TYPE_PATTERNS.items():
        if pattern.search(text):
            return kind
    if any(ch.isdigit() for ch in text) and any(unit in text for unit in ["元", "人", "门", "%"]):
        return "number"
    return "text"


def _value_matches_label(label: str, value: str) -> bool:
    concepts = _label_concepts(label)
    kind = _value_type(value)
    if not concepts or kind == "text":
        return True
    if "email" in concepts:
        return kind == "email"
    if "id_number" in concepts:
        return kind == "id_number"
    if "contact" in concepts:
        return kind in {"phone", "email", "text"}
    if "date" in concepts:
        return kind in {"date", "text"}
    if "rank" in concepts:
        return kind in {"rank", "number", "text"}
    if concepts & {"income", "count"}:
        return kind in {"number", "text"}
    return True


def _generic_boost(template_label: str, source_label: str, value: str) -> float:
    template_concepts = _label_concepts(template_label)
    source_concepts = _label_concepts(source_label)
    if not template_concepts or not source_concepts:
        return 0
    shared = template_concepts & source_concepts
    if not shared:
        return 0
    if not _value_matches_label(template_label, value):
        return 0
    if shared & {"email", "id_number", "student_id"}:
        return 0.24
    if shared & {"contact", "date", "rank", "income", "count", "address", "school_class"}:
        return 0.18
    return 0.12


def _specificity_penalty(template_label: str, source_label: str) -> float:
    left = _label_signature(template_label)
    right = _label_signature(source_label)
    if not left or not right or left in right or right in left:
        return 0
    extra = max(0, len(right) - len(left))
    return min(0.1, extra * 0.01)


def _candidate_score(label: str, source_label: str, value: str) -> float:
    base = _match_score(label, source_label)
    score = base + _generic_boost(label, source_label, value) - _specificity_penalty(label, source_label)
    if not _value_matches_label(label, value):
        score -= 0.2
    return max(0, min(1, score))


def _raw_value_for_label(label: str, raw_fields: list[dict[str, Any]], open_fields: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    candidates: list[tuple[float, str, dict[str, Any] | None, str]] = []
    seen_candidates: set[tuple[str, str]] = set()
    for source_label, value in open_fields.items():
        if value:
            value_text = clean_cell(str(value))
            source_label_text = clean_cell(str(source_label))
            seen_candidates.add((source_label_text, value_text))
            candidates.append((_candidate_score(label, source_label_text, value_text), value_text, None, source_label_text))
    for item in raw_fields:
        value = item.get("value")
        if value:
            value_text = clean_cell(str(value))
            source_label = clean_cell(str(item.get("label", "")))
            if (source_label, value_text) in seen_candidates:
                continue
            seen_candidates.add((source_label, value_text))
            candidates.append((_candidate_score(label, source_label, value_text), value_text, item, source_label))
    candidates = [item for item in candidates if item[0] >= 0.66]
    if not candidates:
        return "", None
    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] < 0.78 and candidates[0][0] - candidates[1][0] < 0.08:
        return "", None
    _, value, source, _ = candidates[0]
    return clean_cell(value), source


def _prefill_tables_from_structure(structure: dict[str, Any], raw_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields_by_table: dict[str, list[dict[str, Any]]] = {}
    for item in raw_fields:
        table_id = item.get("table_id")
        if not table_id:
            continue
        fields_by_table.setdefault(str(table_id), []).append(
            {
                "label": item.get("label"),
                "value": item.get("value"),
                "row": item.get("row"),
                "label_col": item.get("label_col"),
                "value_col": item.get("value_col"),
                "location": item.get("location"),
            }
        )

    tables: list[dict[str, Any]] = []
    for table in structure.get("tables", []):
        table_id = str(table.get("table_id", ""))
        tables.append(
            {
                "table_id": table_id,
                "rows": table.get("rows", []),
                "cells": table.get("cells", []),
                "fields": fields_by_table.get(table_id, []),
                "location": table.get("location"),
            }
        )
    return tables


def _quality_warnings(material_structure: dict[str, Any], template_text: str, template_labels: list[str]) -> list[str]:
    warnings: list[str] = []
    material_quality = material_structure.get("quality", {})
    if material_quality.get("needs_human_review"):
        warnings.append("当前材料解析质量偏低，建议先核对原文预览和字段抽取结果。")
    if template_text.strip() and not template_labels:
        warnings.append("已选择表格模板，但未能从模板中稳定识别可填写字段，请确认文件是否为可编辑文本或清晰表格。")
    if template_labels and len(template_labels) <= 2:
        warnings.append("模板字段数量较少，可能存在合并单元格或扫描件解析不完整。")
    return warnings


def _prefill_quality(final_fields: dict[str, Any], missing_fields: list[str], quality_warnings: list[str]) -> dict[str, Any]:
    total = len(final_fields)
    filled = sum(1 for value in final_fields.values() if clean_cell(value))
    fill_rate = round(filled / total, 3) if total else 0
    return {
        "field_count": total,
        "filled_count": filled,
        "missing_count": len(missing_fields),
        "fill_rate": fill_rate,
        "needs_human_review": bool(quality_warnings or (total and fill_rate < 0.5)),
    }


def prefill_form(
    text: str,
    extracted_fields: Dict[str, Any] | None = None,
    scenario: str = "competition_registration",
    template_text: str = "",
):
    details = merge_field_details(text, extracted_fields, scenario=scenario)
    structure = details["document_structure"]
    open_fields = details.get("open_fields") or details["recognized_fields"].get("open_fields") or {}

    template_labels = _extract_template_labels(template_text) if template_text.strip() else []
    quality_warnings = _quality_warnings(structure, template_text, template_labels)
    if template_labels:
        final_fields = {label: "" for label in template_labels}
        prefill_sources: dict[str, Any] = {}
        for label in template_labels:
            value, source = _raw_value_for_label(label, details["raw_fields"], open_fields)
            if not value:
                continue
            final_fields[label] = value
            if source:
                prefill_sources[label] = source
        missing_fields = [label for label, value in final_fields.items() if not value]
        template_name = "上传表格模板"
    else:
        final_fields = dict(open_fields)
        prefill_sources = {}
        missing_fields = []
        template_name = "通用开放字段表单" if _is_generic_scenario(scenario) else "未提供模板的字段草稿"
    quality = _prefill_quality(final_fields, missing_fields, quality_warnings)

    return {
        "fields": final_fields,
        "template_name": template_name,
        "missing_fields": missing_fields,
        "quality": quality,
        "source_structure": structure,
        "prefill_tables": _prefill_tables_from_structure(structure, details["raw_fields"]),
        "open_fields": open_fields,
        "prefill_sources": prefill_sources,
        "review_fields": [],
        "quality_warnings": quality_warnings,
        "raw_fields": details["raw_fields"],
        "field_matches": details["field_matches"],
        "unmapped_fields": details["unmapped_fields"],
    }
