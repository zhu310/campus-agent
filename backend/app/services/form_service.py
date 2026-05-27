"""Form prefill service.

Prefill is a suggestion layer, not a replacement for the source material.
Each filled value keeps the original label and source location so users can
verify it before submission.
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.audit_service import merge_field_details


FORM_TEMPLATE = {
    "负责人": "",
    "团队人数": "",
    "联系方式": "",
    "项目类型": "Agent 智能体方向",
    "项目名称": "",
    "团队成员": "",
    "学校": "",
    "学院/班级": "",
    "专业指导老师": "",
    "英语指导老师": "",
    "指导老师": "",
    "邮箱": "",
    "摘要": "",
    "科研诚信保证": "",
}

FORM_TEMPLATES = {
    "competition_registration": FORM_TEMPLATE,
    "leave_approval": {
        "请假人": "",
        "学号": "",
        "学院/班级": "",
        "请假原因": "",
        "开始时间": "",
        "结束时间": "",
        "联系方式": "",
        "证明材料": "",
    },
    "reimbursement": {
        "经办人": "",
        "事项名称": "",
        "报销金额": "",
        "发票/票据": "",
        "票据类型": "",
        "联系方式": "",
    },
    "club_activity": {
        "申请人": "",
        "活动名称": "",
        "活动时间": "",
        "活动地点": "",
        "联系方式": "",
        "邮箱": "",
    },
}

TARGET_FIELD_MAPS = {
    "competition_registration": {
        "负责人": "name",
        "团队人数": "team_size",
        "联系方式": "phone",
        "项目名称": "project_name",
        "团队成员": "team_members",
        "学校": "school",
        "学院/班级": "college_class",
        "专业指导老师": "professional_advisor",
        "英语指导老师": "english_advisor",
        "指导老师": "advisor",
        "邮箱": "email",
        "摘要": "abstract",
        "科研诚信保证": "integrity_statement",
    },
    "leave_approval": {
        "请假人": "name",
        "学号": "student_id",
        "学院/班级": "college_class",
        "请假原因": "leave_reason",
        "开始时间": "leave_start",
        "结束时间": "leave_end",
        "联系方式": "phone",
        "证明材料": "proof",
    },
    "reimbursement": {
        "经办人": "name",
        "事项名称": "project_name",
        "报销金额": "amount",
        "发票/票据": "invoice",
        "票据类型": "invoice_type",
        "联系方式": "phone",
    },
    "club_activity": {
        "申请人": "applicant",
        "活动名称": "activity_name",
        "活动时间": "activity_time",
        "活动地点": "activity_location",
        "联系方式": "phone",
        "邮箱": "email",
    },
}

TARGET_FIELD_MAP = TARGET_FIELD_MAPS["competition_registration"]

REQUIRED_FORM_FIELDS = {
    "competition_registration": {"负责人", "团队人数", "联系方式", "项目名称", "邮箱"},
    "leave_approval": {"请假人", "学号", "学院/班级", "请假原因", "开始时间", "结束时间", "联系方式"},
    "reimbursement": {"经办人", "事项名称", "报销金额", "发票/票据"},
    "club_activity": {"申请人", "活动名称", "活动时间", "活动地点", "联系方式"},
}

GENERIC_SCENARIOS = {"", "generic", "general", "other", "custom", "其他", "其他场景", "自定义场景"}


def _is_generic_scenario(scenario: str | None) -> bool:
    if scenario is None:
        return True
    normalized = str(scenario).strip().lower()
    return normalized in GENERIC_SCENARIOS or normalized not in FORM_TEMPLATES


def _source_for(field_name: str, matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [item for item in matches if item.get("field_name") == field_name]
    if not candidates:
        return None
    return max(candidates, key=lambda item: float(item.get("confidence") or 0))


def _prefill_tables_from_structure(structure: dict[str, Any], raw_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return table-shaped prefill data without flattening the original rows."""
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


def prefill_form(text: str, extracted_fields: Dict[str, Any] | None = None, scenario: str = "competition_registration"):
    details = merge_field_details(text, extracted_fields, scenario=scenario)
    fields = details["recognized_fields"]
    matches = details["field_matches"]
    structure = details["document_structure"]

    open_fields = details.get("open_fields") or fields.get("open_fields") or {}
    final_fields = dict(open_fields if _is_generic_scenario(scenario) and open_fields else FORM_TEMPLATES.get(scenario, FORM_TEMPLATE))
    target_map = TARGET_FIELD_MAPS.get(scenario, TARGET_FIELD_MAP)
    prefill_sources: dict[str, Any] = {}

    if _is_generic_scenario(scenario):
        target_map = {}

    for target_label, field_name in target_map.items():
        value = fields.get(field_name, "")
        if not value:
            continue
        final_fields[target_label] = value
        source = _source_for(field_name, matches)
        prefill_sources[target_label] = source or {
            "field_name": field_name,
            "semantic_name": target_label,
            "original_label": target_label,
            "value": value,
            "source": "字段推导",
            "method": "derived_or_external",
            "location": "",
            "confidence": 0.6,
            "needs_review": True,
        }

    material_type = fields.get("material_type")
    if material_type == "科研英语演讲报名表":
        required = {"项目名称", "团队成员", "团队人数", "学校", "学院/班级", "联系方式", "邮箱"}
    else:
        required = set() if _is_generic_scenario(scenario) else REQUIRED_FORM_FIELDS.get(scenario, REQUIRED_FORM_FIELDS["competition_registration"])
    missing_fields = [key for key, value in final_fields.items() if key in required and not value]
    review_fields = [key for key, source in prefill_sources.items() if source.get("needs_review")]

    return {
        "fields": final_fields,
        "template_name": "通用开放字段表单" if _is_generic_scenario(scenario) else (material_type or f"{scenario} 办理表单"),
        "missing_fields": missing_fields,
        "source_structure": structure,
        "prefill_tables": _prefill_tables_from_structure(structure, details["raw_fields"]),
        "open_fields": open_fields,
        "prefill_sources": prefill_sources,
        "review_fields": review_fields,
        "raw_fields": details["raw_fields"],
        "field_matches": details["field_matches"],
        "unmapped_fields": details["unmapped_fields"],
    }
