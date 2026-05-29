"""Material field extraction and rule audit service.

The important product rule here is: never throw away what the user uploaded.
We keep raw labels and values exactly as extracted, then add a semantic match
layer only to help auditing and form prefill.
"""

from __future__ import annotations

import re
import json
from typing import Any, Dict, Iterable, List

from app.models import RulePolicy
from app.services.document_structure_service import build_document_structure
from app.services.field_schema_service import FIELD_SCHEMAS, GENERIC_SCENARIOS, is_generic_scenario, scenario_schema
from app.services.llm_service import chat_completion


FIELD_LABELS = {
    "material_type": "材料类型",
    "name": "负责人",
    "student_id": "学号",
    "gender": "性别",
    "birth_date": "出生年月",
    "ethnicity": "民族",
    "political_status": "政治面貌",
    "enrollment_date": "入学时间",
    "grade": "所在年级",
    "id_number": "身份证号码",
    "college_class": "学院/班级",
    "school": "学校",
    "student_level": "学生层次",
    "phone": "联系方式",
    "project_name": "项目/作品名称",
    "team_size": "团队人数",
    "advisor": "指导老师",
    "professional_advisor": "专业指导老师",
    "english_advisor": "英语指导老师",
    "email": "邮箱",
    "team_members": "团队成员",
    "abstract": "摘要",
    "integrity_statement": "科研诚信保证",
    "leave_reason": "请假原因",
    "leave_start": "请假开始时间",
    "leave_end": "请假结束时间",
    "proof": "证明材料",
    "amount": "金额",
    "invoice": "发票/票据",
    "invoice_type": "票据类型",
    "activity_name": "活动名称",
    "activity_time": "活动时间",
    "activity_location": "活动地点",
    "applicant": "申请人",
    "awards": "曾获何种奖励",
    "family_population": "家庭人口总数",
    "family_income": "家庭月总收入",
    "per_capita_income": "人均月收入",
    "income_source": "收入来源",
    "family_address": "家庭住址",
    "postal_code": "邮政编码",
    "poverty_level": "困难情况认定档次",
    "grade_rank": "成绩排名",
    "comprehensive_rank": "综合考评排名",
    "application_reason": "申请理由",
}

DEFAULT_REQUIRED_FIELDS = ["name", "phone", "email", "project_name", "team_size"]

SCENARIO_REQUIRED_FIELDS = {key: value["required_fields"] for key, value in FIELD_SCHEMAS.items()}
SCENARIO_FIELD_PRIORITIES = {key: value["field_priorities"] for key, value in FIELD_SCHEMAS.items()}


def _field_group(name: str, aliases: list[str]) -> dict[str, Any]:
    return {"name": name, "aliases": aliases}

SEMANTIC_FIELD_GROUPS: dict[str, dict[str, Any]] = {
    "project_name": {
        "name": "项目/作品名称",
        "aliases": ["作品名称", "作品标题", "项目名称", "项目标题", "参赛作品名称", "实践题目", "活动名称", "Title"],
    },
    "name": {
        "name": "负责人",
        "aliases": ["负责人", "团队负责人", "队长", "队长姓名", "组长", "组长姓名", "申报人", "申请人", "姓名"],
    },
    "phone": {
        "name": "联系方式",
        "aliases": ["联系方式", "联系电话", "手机", "手机号", "手机号码", "电话", "联系人电话"],
    },
    "email": {
        "name": "邮箱",
        "aliases": ["邮箱", "电子邮箱", "邮箱地址", "Email", "E-mail", "Email地址", "E-mail地址"],
    },
    "team_members": {
        "name": "团队成员",
        "aliases": ["团队成员", "成员", "团队姓名", "参赛成员", "队员", "团队名单"],
    },
    "team_size": {
        "name": "团队人数",
        "aliases": ["团队人数", "队伍人数", "人数", "成员人数", "参赛人数"],
    },
    "student_id": {
        "name": "学号",
        "aliases": ["学号", "学生编号"],
    },
    "gender": _field_group("性别", ["性别"]),
    "birth_date": _field_group("出生年月", ["出生年月", "出生日期", "生日"]),
    "ethnicity": _field_group("民族", ["民族"]),
    "political_status": _field_group("政治面貌", ["政治面貌"]),
    "enrollment_date": _field_group("入学时间", ["入学时间", "入学日期"]),
    "grade": _field_group("所在年级", ["所在年级", "年级"]),
    "id_number": _field_group("身份证号码", ["身份证号码", "身份证号", "证件号码"]),
    "school": {
        "name": "学校",
        "aliases": ["学校", "所在学校", "高校"],
    },
    "college_class": {
        "name": "学院/班级",
        "aliases": ["学院", "学院/班级", "学院班级", "专业班级", "班级", "所在学院"],
    },
    "student_level": {
        "name": "学生层次",
        "aliases": ["本科生研究生", "学生层次", "培养层次", "学历层次"],
    },
    "advisor": {
        "name": "指导老师",
        "aliases": ["指导老师", "指导教师", "导师"],
    },
    "professional_advisor": {
        "name": "专业指导老师",
        "aliases": ["专业指导老师", "专业指导教师"],
    },
    "english_advisor": {
        "name": "英语指导老师",
        "aliases": ["英语指导老师", "英语指导教师"],
    },
    "abstract": {
        "name": "摘要",
        "aliases": ["摘要", "作品摘要", "项目摘要", "英语摘要", "Abstract"],
    },
    "integrity_statement": {
        "name": "科研诚信保证",
        "aliases": ["科研诚信保证", "诚信承诺", "诚信声明"],
    },
    "leave_reason": _field_group("请假原因", ["请假原因", "请假事由", "事由", "原因", "请假说明"]),
    "leave_start": _field_group("请假开始时间", ["开始时间", "请假开始时间", "起始时间", "请假起始日期", "请假时间起"]),
    "leave_end": _field_group("请假结束时间", ["结束时间", "请假结束时间", "截止时间", "请假结束日期", "请假时间止"]),
    "proof": _field_group("证明材料", ["证明材料", "证明附件", "附件", "病历", "诊断证明", "佐证材料"]),
    "amount": _field_group("金额", ["金额", "报销金额", "费用金额", "申请金额", "合计金额", "总金额"]),
    "invoice": _field_group("发票/票据", ["发票", "票据", "发票号", "发票号码", "票据编号", "凭证"]),
    "invoice_type": _field_group("票据类型", ["票据类型", "发票类型", "凭证类型"]),
    "activity_name": _field_group("活动名称", ["活动名称", "社团活动名称", "事项名称", "活动主题"]),
    "activity_time": _field_group("活动时间", ["活动时间", "举办时间", "开始日期", "结束日期"]),
    "activity_location": _field_group("活动地点", ["活动地点", "举办地点", "场地", "地点"]),
    "applicant": _field_group("申请人", ["申请人", "经办人", "提交人", "联系人", "负责人"]),
    "awards": _field_group("曾获何种奖励", ["曾获何种奖励", "获奖情况", "奖励", "曾获奖励"]),
    "family_population": _field_group("家庭人口总数", ["家庭人口总数", "家庭人口", "人口总数"]),
    "family_income": _field_group("家庭月总收入", ["家庭月总收入", "家庭总收入", "月总收入"]),
    "per_capita_income": _field_group("人均月收入", ["人均月收入", "人均收入"]),
    "income_source": _field_group("收入来源", ["收入来源", "家庭收入来源"]),
    "family_address": _field_group("家庭住址", ["家庭住址", "家庭地址", "住址"]),
    "postal_code": _field_group("邮政编码", ["邮政编码", "邮编"]),
    "poverty_level": _field_group("困难情况认定档次", ["困难情况认定档次", "困难认定档次", "困难档次"]),
    "grade_rank": _field_group("成绩排名", ["成绩排名", "学习成绩排名", "排名"]),
    "comprehensive_rank": _field_group("综合考评排名", ["综合考评排名", "综合排名", "实行综合考评排名"]),
    "application_reason": _field_group("申请理由", ["申请理由", "申请原因", "申请说明"]),
}

FIELD_PATTERNS = {
    "name": [r"(?:负责人|团队负责人|队长姓名|队长|组长姓名|组长|申报人|申请人|姓名)\s*[:：]\s*([^\n|]{2,30})"],
    "student_id": [r"(?:学号|学生编号)\s*[:：]\s*([A-Za-z0-9-]{6,30})"],
    "college_class": [r"(?:学院/班级|学院班级|专业班级|所在学院|学院|班级)\s*[:：]\s*([^\n|]{2,100})"],
    "phone": [r"(1[3-9]\d{9})", r"(?:联系方式|联系电话|手机号码|手机号|电话)\s*[:：]\s*([0-9\-]{6,30})"],
    "project_name": [r"(?:作品名称|作品标题|项目名称|项目标题|参赛作品名称|实践题目|活动名称)(?:\s*\(?Title\)?)?\s*[:：]?\s*([^\n|]{2,200})"],
    "team_size": [r"(?:团队人数|队伍人数|成员人数|参赛人数|人数)\s*[:：]\s*(\d{1,2})"],
    "advisor": [r"(?:指导老师|指导教师|导师)\s*[:：]\s*([^\n|]{2,40})"],
    "email": [r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"],
    "team_members": [r"(?:团队成员|团队姓名|参赛成员|团队名单|队员)(?:（.*?）|\(.*?\))?\s*[:：]\s*([^\n]{2,500})"],
    "leave_reason": [r"(?:请假原因|请假事由|事由|原因)\s*[:：]\s*([^\n|]{2,300})"],
    "leave_start": [r"(?:请假开始时间|开始时间|起始时间)\s*[:：]\s*([^\n|]{2,80})"],
    "leave_end": [r"(?:请假结束时间|结束时间|截止时间)\s*[:：]\s*([^\n|]{2,80})"],
    "amount": [r"(?:报销金额|费用金额|申请金额|合计金额|总金额|金额)\s*[:：]?\s*([0-9]+(?:\.[0-9]{1,2})?)"],
    "invoice": [r"(?:发票号|发票号码|票据编号|凭证号)\s*[:：]\s*([A-Za-z0-9-]{4,60})"],
    "activity_name": [r"(?:活动名称|活动主题|事项名称)\s*[:：]\s*([^\n|]{2,120})"],
    "activity_time": [r"(?:活动时间|举办时间)\s*[:：]\s*([^\n|]{2,120})"],
    "activity_location": [r"(?:活动地点|举办地点|场地|地点)\s*[:：]\s*([^\n|]{2,120})"],
}

SECTION_STOPS = ["科研诚信保证", "诚信承诺", "诚信声明", "组长签名", "队长签名", "负责人签名"]
TEAM_MEMBER_SPLIT_RE = re.compile(r"[、,，;；\s|/]+")


def _clean_label(value: str) -> str:
    value = re.sub(r"\s+", "", value or "")
    value = re.sub(r"[（(].*?[）)]", "", value)
    return value.strip(":：| ")


def _clean_value(value: Any) -> str:
    value = str(value or "").replace("\r", "\n").strip()
    value = re.sub(r"\n{2,}", "\n", value)
    value = re.sub(r"\s+\|", " |", value)
    value = re.sub(r"\|\s+", "| ", value)
    return value.strip(":：,，;； ")


def _line_location(index: int) -> str:
    return f"第 {index} 行"


def _make_raw_field(label: str, value: Any, source: str, method: str, line: int, confidence: float = 0.82) -> dict[str, Any] | None:
    cleaned_label = _clean_value(label)
    cleaned_value = _clean_value(value)
    if not cleaned_label or not cleaned_value:
        return None
    return {
        "label": cleaned_label,
        "value": cleaned_value,
        "source": source,
        "method": method,
        "line": line,
        "location": _line_location(line),
        "confidence": confidence,
    }


def _dedupe_raw_fields(raw_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in raw_fields:
        key = (_clean_label(item.get("label", "")), _clean_value(item.get("value", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_pipe_table_raw_fields(text: str) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "|" not in line:
            continue
        cells = [_clean_value(cell) for cell in line.split("|") if _clean_value(cell)]
        index = 0
        while index < len(cells) - 1:
            label = cells[index]
            value = cells[index + 1]
            if _match_semantic_field(label) and value and not _match_semantic_field(value):
                item = _make_raw_field(label, value, "原始表格", "table_pair", line_no, 0.9)
                if item:
                    raw_fields.append(item)
                index += 2
            else:
                index += 1
    return raw_fields


def _extract_colon_raw_fields(text: str) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*([^:：|]{2,40})\s*[:：]\s*(.+?)\s*$")
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = pattern.match(line)
        if not match:
            continue
        item = _make_raw_field(match.group(1), match.group(2), "原始文本", "label_colon_value", line_no, 0.88)
        if item:
            raw_fields.append(item)
    return raw_fields


def _extract_line_pair_raw_fields(text: str) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    lines = [(line_no, _clean_value(line)) for line_no, line in enumerate(text.splitlines(), start=1) if _clean_value(line)]
    index = 0
    while index < len(lines) - 1:
        line_no, label = lines[index]
        _, value = lines[index + 1]
        if _match_semantic_field(label) and value and not _match_semantic_field(value):
            item = _make_raw_field(label, value, "原始文本", "line_pair", line_no, 0.76)
            if item:
                raw_fields.append(item)
            index += 2
        else:
            index += 1
    return raw_fields


def _first_match(text: str, patterns: Iterable[str]) -> tuple[str, int] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
        if match:
            line = text[: match.start()].count("\n") + 1
            return _clean_value(match.group(1)), line
    return None


def _extract_regex_raw_fields(text: str) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    for field_name, patterns in FIELD_PATTERNS.items():
        matched = _first_match(text, patterns)
        if not matched:
            continue
        value, line = matched
        item = _make_raw_field(FIELD_LABELS[field_name], value.splitlines()[0].strip(), "全文识别", "regex", line, 0.68)
        if item:
            raw_fields.append(item)
    return raw_fields


def _extract_section(text: str, start_labels: list[str], stop_labels: list[str]) -> tuple[str, int] | None:
    start_pattern = "|".join(re.escape(label) for label in start_labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    match = re.search(rf"(?:{start_pattern}).*?\n(.*?)(?=\n(?:{stop_pattern})|\Z)", text, flags=re.S)
    if not match:
        return None
    value = _clean_value(match.group(1))
    if not value:
        return None
    line = text[: match.start()].count("\n") + 1
    return value[:1400], line


def _extract_section_raw_fields(text: str) -> list[dict[str, Any]]:
    raw_fields: list[dict[str, Any]] = []
    abstract = _extract_section(text, ["英语摘要", "摘要", "Abstract"], SECTION_STOPS)
    if abstract:
        item = _make_raw_field("摘要", abstract[0], "原始段落", "section", abstract[1], 0.72)
        if item:
            raw_fields.append(item)
    integrity = _extract_section(text, ["科研诚信保证", "诚信承诺", "诚信声明"], ["组长签名", "队长签名", "负责人签名"])
    if integrity:
        item = _make_raw_field("科研诚信保证", integrity[0], "原始段落", "section", integrity[1], 0.72)
        if item:
            raw_fields.append(item)
    return raw_fields


def _extract_structure_raw_fields(structure: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert format-level key-value blocks into raw fields.

    This is the handoff between Document Structure Agent and Field Extraction
    Agent: the former preserves layout and source location; the latter will map
    labels to scenario fields later.
    """
    raw_fields: list[dict[str, Any]] = []
    for item in structure.get("key_values", []):
        raw = _make_raw_field(
            item.get("label", ""),
            item.get("value", ""),
            "结构化文档",
            item.get("method", "structure_kv"),
            int(item.get("line") or 1),
            0.88 if item.get("method") == "table_pair" else 0.84,
        )
        if raw:
            raw["location"] = item.get("location") or raw["location"]
            if item.get("table_id"):
                raw["table_id"] = item.get("table_id")
                raw["row"] = item.get("row")
                raw["label_col"] = item.get("label_col")
                raw["value_col"] = item.get("value_col")
            raw_fields.append(raw)

    # Section titles such as "摘要" or "申请理由" often carry the field label
    # while the content lives in a multi-line paragraph.
    for item in structure.get("sections", []):
        raw = _make_raw_field(
            item.get("title", ""),
            item.get("content", ""),
            "结构化段落",
            "section_block",
            int(item.get("line") or 1),
            0.74,
        )
        if raw:
            raw["location"] = item.get("location") or raw["location"]
            raw_fields.append(raw)
    return raw_fields


def _extract_raw_fields(text: str, structure: dict[str, Any] | None = None, scenario: str = "competition_registration") -> list[dict[str, Any]]:
    cleaned = text.replace("\r", "\n")
    structure = structure or build_document_structure(cleaned)
    raw_fields: list[dict[str, Any]] = []
    raw_fields.extend(_extract_structure_raw_fields(structure))

    if _is_generic_scenario(scenario):
        raw_fields.extend(_extract_colon_raw_fields(cleaned))
        return _dedupe_raw_fields(raw_fields)

    # The legacy extractors stay as deterministic fallbacks. They are deliberately
    # placed after structure extraction so broad regexes do not overwrite better
    # table or section evidence.
    raw_fields.extend(_extract_pipe_table_raw_fields(cleaned))
    raw_fields.extend(_extract_colon_raw_fields(cleaned))
    raw_fields.extend(_extract_line_pair_raw_fields(cleaned))
    raw_fields.extend(_extract_regex_raw_fields(cleaned))
    raw_fields.extend(_extract_section_raw_fields(cleaned))
    return _dedupe_raw_fields(raw_fields)


def _candidate_field_names(scenario: str | None = None) -> list[str]:
    preferred = SCENARIO_FIELD_PRIORITIES.get(scenario or "", [])
    return preferred + [field for field in SEMANTIC_FIELD_GROUPS if field not in preferred]


def _is_generic_scenario(scenario: str | None) -> bool:
    return is_generic_scenario(scenario)


def _match_semantic_field(label: str, scenario: str | None = None) -> str | None:
    cleaned = _clean_label(label).lower()
    if not cleaned:
        return None
    for field_name in _candidate_field_names(scenario):
        group = SEMANTIC_FIELD_GROUPS[field_name]
        for alias in group["aliases"]:
            alias_cleaned = _clean_label(alias).lower()
            if cleaned == alias_cleaned or alias_cleaned in cleaned:
                return field_name
    return None


def _match_raw_fields(raw_fields: list[dict[str, Any]], scenario: str = "competition_registration") -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if _is_generic_scenario(scenario):
        return {}, [], raw_fields

    recognized: dict[str, Any] = {}
    field_matches: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []

    for item in raw_fields:
        label_text = str(item.get("label", ""))
        value_text = str(item.get("value", ""))
        field_name = _match_semantic_field(label_text, scenario)
        if not field_name:
            unmapped.append(item)
            continue
        if field_name in {"name", "applicant"} and "签名" in label_text:
            unmapped.append(item)
            continue
        if field_name == "application_reason" and re.search(r"签名|公章|年\s*月\s*日", value_text):
            unmapped.append(item)
            continue
        if field_name in {"school", "college_class"} and re.search(r"审核|意见|公章", label_text + value_text):
            unmapped.append(item)
            continue
        match = {
            "field_name": field_name,
            "semantic_name": SEMANTIC_FIELD_GROUPS[field_name]["name"],
            "original_label": item["label"],
            "value": item["value"],
            "source": item["source"],
            "method": item["method"],
            "location": item["location"],
            "confidence": item["confidence"],
            "needs_review": item["confidence"] < 0.75,
        }
        field_matches.append(match)
        current = recognized.get(field_name)
        if not current or float(item["confidence"]) > float(current.get("confidence", 0)):
            recognized[field_name] = match

    flat_fields = {field_name: match["value"] for field_name, match in recognized.items() if match.get("value")}
    return flat_fields, field_matches, unmapped


def _normalize_extra_fields(extra_fields: Dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not extra_fields:
        return {}, [], [], []

    flat: dict[str, Any] = {}
    raw_fields: list[dict[str, Any]] = []
    field_matches: list[dict[str, Any]] = []
    unmapped_fields: list[dict[str, Any]] = []

    for key, value in extra_fields.items():
        if key == "recognized_fields" and isinstance(value, dict):
            flat.update({k: v for k, v in value.items() if v})
        elif key == "raw_fields" and isinstance(value, list):
            raw_fields.extend([item for item in value if isinstance(item, dict)])
        elif key == "field_matches" and isinstance(value, list):
            field_matches.extend([item for item in value if isinstance(item, dict)])
        elif key == "unmapped_fields" and isinstance(value, list):
            unmapped_fields.extend([item for item in value if isinstance(item, dict)])
        elif value and key in SEMANTIC_FIELD_GROUPS:
            flat[key] = value

    return flat, raw_fields, field_matches, unmapped_fields


def _open_fields_from_raw(raw_fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep every extracted label/value pair for unknown or newly added scenes."""
    open_fields: dict[str, Any] = {}
    for item in raw_fields:
        label = _clean_value(item.get("label", ""))
        value = _clean_value(item.get("value", ""))
        if not label or not value:
            continue
        if label in open_fields and open_fields[label] != value:
            suffix = 2
            while f"{label}_{suffix}" in open_fields:
                suffix += 1
            open_fields[f"{label}_{suffix}"] = value
        else:
            open_fields[label] = value
    return open_fields


def _field_synonyms_from_raw(raw_fields: list[dict[str, Any]], scenario: str) -> dict[str, list[dict[str, Any]]]:
    """Build a non-destructive synonym index from original labels to canonical fields."""
    synonym_fields: dict[str, list[dict[str, Any]]] = {}
    if _is_generic_scenario(scenario):
        return synonym_fields
    for item in raw_fields:
        field_name = _match_semantic_field(str(item.get("label", "")), scenario)
        if not field_name:
            continue
        synonym_fields.setdefault(field_name, []).append(
            {
                "semantic_name": SEMANTIC_FIELD_GROUPS[field_name]["name"],
                "original_label": item.get("label", ""),
                "value": item.get("value", ""),
                "source": item.get("source", ""),
                "method": item.get("method", ""),
                "location": item.get("location", ""),
                "table_id": item.get("table_id"),
                "row": item.get("row"),
                "confidence": item.get("confidence", 0),
            }
        )
    return synonym_fields


def _merge_open_fields(recognized_fields: dict[str, Any], open_fields: dict[str, Any], scenario: str) -> None:
    # Always expose open_fields so new document types remain inspectable. For
    # generic/custom scenes, also promote original labels to top-level fields
    # because there is no fixed schema to map into yet.
    if open_fields:
        recognized_fields["open_fields"] = open_fields
    if _is_generic_scenario(scenario):
        recognized_fields["generic_fields"] = open_fields


def _parse_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _llm_extract_fields(text: str, structure: dict[str, Any], scenario: str) -> dict[str, Any]:
    """Optional JSON-only LLM fallback for low-confidence or unknown layouts."""
    schema_fields = scenario_schema(scenario)["field_priorities"]
    system_prompt = (
        "你是高校材料结构化抽取助手。只返回 JSON 对象，不要解释。"
        "必须包含 recognized_fields、open_fields、risk_notes 三个字段。"
        "所有字段必须来自原文，不确定就不要编造。"
    )
    user_prompt = json.dumps(
        {
            "scenario": scenario,
            "expected_fields": schema_fields,
            "document_quality": structure.get("quality", {}),
            "tables": structure.get("tables", [])[:5],
            "key_values": structure.get("key_values", [])[:80],
            "text_preview": text[:5000],
        },
        ensure_ascii=False,
    )
    parsed = _parse_json_object(chat_completion(system_prompt, user_prompt))
    if not parsed:
        return {"recognized_fields": {}, "open_fields": {}, "risk_notes": [], "used": False}
    return {
        "recognized_fields": parsed.get("recognized_fields") if isinstance(parsed.get("recognized_fields"), dict) else {},
        "open_fields": parsed.get("open_fields") if isinstance(parsed.get("open_fields"), dict) else {},
        "risk_notes": parsed.get("risk_notes") if isinstance(parsed.get("risk_notes"), list) else [],
        "used": True,
    }


def _should_use_llm_fallback(structure: dict[str, Any], open_fields: dict[str, Any], scenario: str) -> bool:
    quality = structure.get("quality", {})
    return bool(quality.get("needs_human_review")) or (_is_generic_scenario(scenario) and not open_fields)


def _parse_team_members(value: str) -> list[str]:
    cleaned = _clean_value(value)
    if not cleaned:
        return []
    members: list[str] = []
    for item in TEAM_MEMBER_SPLIT_RE.split(cleaned):
        item = item.strip()
        match = re.search(r"[\u4e00-\u9fff]{2,4}(?:\([A-Za-z,]+\))?", item)
        if match:
            members.append(match.group(0))
    return members


def _derive_team_fields(fields: Dict[str, Any]) -> None:
    members = _parse_team_members(str(fields.get("team_members") or ""))
    if members:
        fields["team_members"] = "、".join(members)
        fields.setdefault("team_size", str(len(members)))
        leader = re.match(r"[\u4e00-\u9fff]{2,4}", members[0])
        fields.setdefault("name", leader.group(0) if leader else members[0])
    if not fields.get("name") or fields.get("name") == "-":
        text = str(fields.get("team_members") or "")
        leader_match = re.search(r"(?:组长|队长|负责人|团队负责人)(?:签名)?\s*[:：]?\s*([\u4e00-\u9fff]{2,4})", text)
        if leader_match:
            fields["name"] = leader_match.group(1)


def _required_fields_for(fields: Dict[str, Any], scenario: str = "competition_registration") -> list[str]:
    if _is_generic_scenario(scenario):
        return []
    return scenario_schema(scenario)["required_fields"]


def missing_field_labels(fields: Dict[str, Any], scenario: str = "competition_registration") -> list[str]:
    normalized = fields.get("recognized_fields", fields) if isinstance(fields, dict) else {}
    return [FIELD_LABELS.get(field, field) for field in _required_fields_for(normalized, scenario) if not normalized.get(field)]


def merge_field_details(text: str, extra_fields: Dict[str, Any] | None = None, scenario: str = "competition_registration") -> Dict[str, Any]:
    cleaned = text.replace("\r", "\n")
    structure = build_document_structure(cleaned)
    raw_fields = _extract_raw_fields(cleaned, structure, scenario)
    recognized_fields, field_matches, unmapped_fields = _match_raw_fields(raw_fields, scenario)

    extra_flat, extra_raw, extra_matches, extra_unmapped = _normalize_extra_fields(extra_fields)
    for key, value in extra_flat.items():
        recognized_fields.setdefault(key, value)
    raw_fields = _dedupe_raw_fields(raw_fields + extra_raw)
    field_matches.extend(extra_matches)
    unmapped_fields.extend(extra_unmapped)
    open_fields = _open_fields_from_raw(raw_fields)
    synonym_fields = _field_synonyms_from_raw(raw_fields, scenario)

    if recognized_fields.get("professional_advisor") or recognized_fields.get("english_advisor"):
        advisors = [recognized_fields.get("professional_advisor"), recognized_fields.get("english_advisor")]
        recognized_fields.setdefault("advisor", "；".join(item for item in advisors if item))

    _derive_team_fields(recognized_fields)
    _merge_open_fields(recognized_fields, open_fields, scenario)
    llm_fallback = {"recognized_fields": {}, "open_fields": {}, "risk_notes": [], "used": False}
    if _should_use_llm_fallback(structure, open_fields, scenario):
        llm_fallback = _llm_extract_fields(cleaned, structure, scenario)
        for key, value in llm_fallback["recognized_fields"].items():
            recognized_fields.setdefault(key, value)
        for key, value in llm_fallback["open_fields"].items():
            open_fields.setdefault(key, value)
    if synonym_fields:
        recognized_fields["synonym_fields"] = synonym_fields
    recognized_fields["scenario"] = scenario

    mapped_labels = {_clean_label(item.get("original_label", "")) for item in field_matches}
    unmapped_fields = [
        item for item in raw_fields
        if _clean_label(item.get("label", "")) not in mapped_labels and not _match_semantic_field(str(item.get("label", "")), scenario)
    ] + extra_unmapped

    return {
        "recognized_fields": {key: value for key, value in recognized_fields.items() if value},
        "raw_fields": raw_fields,
        "open_fields": open_fields,
        "synonym_fields": synonym_fields,
        "llm_fallback": llm_fallback,
        "field_matches": field_matches,
        "unmapped_fields": _dedupe_raw_fields(unmapped_fields),
        "document_structure": structure,
    }


def extract_fields(text: str, scenario: str = "competition_registration") -> Dict[str, Any]:
    return merge_field_details(text, scenario=scenario)["recognized_fields"]


def merge_fields(text: str, extra_fields: Dict[str, Any] | None = None, scenario: str = "competition_registration") -> Dict[str, Any]:
    return merge_field_details(text, extra_fields, scenario=scenario)["recognized_fields"]


def seed_default_rules(db) -> None:
    default_rules = [
        {"rule_name": "必填-负责人姓名", "scenario": "competition_registration", "field_name": "name", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充负责人或队长姓名。"},
        {"rule_name": "必填-联系方式", "scenario": "competition_registration", "field_name": "phone", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充联系电话。"},
        {"rule_name": "必填-邮箱", "scenario": "competition_registration", "field_name": "email", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充接收通知的邮箱。"},
        {"rule_name": "必填-项目名称", "scenario": "competition_registration", "field_name": "project_name", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充作品或项目名称。"},
        {"rule_name": "建议-指导老师", "scenario": "competition_registration", "field_name": "advisor", "operator": "recommended", "expected_value": None, "severity": "medium", "suggestion": "建议补充指导老师。"},
        {"rule_name": "必填-请假人姓名", "scenario": "leave_approval", "field_name": "name", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充请假人姓名。"},
        {"rule_name": "必填-请假原因", "scenario": "leave_approval", "field_name": "leave_reason", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充请假原因。"},
        {"rule_name": "必填-请假开始时间", "scenario": "leave_approval", "field_name": "leave_start", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充请假开始时间。"},
        {"rule_name": "必填-请假结束时间", "scenario": "leave_approval", "field_name": "leave_end", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充请假结束时间。"},
        {"rule_name": "建议-证明材料", "scenario": "leave_approval", "field_name": "proof", "operator": "recommended", "expected_value": None, "severity": "medium", "suggestion": "建议上传或说明证明材料。"},
        {"rule_name": "必填-报销金额", "scenario": "reimbursement", "field_name": "amount", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充报销金额。"},
        {"rule_name": "必填-票据信息", "scenario": "reimbursement", "field_name": "invoice", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充发票或票据信息。"},
        {"rule_name": "必填-活动名称", "scenario": "club_activity", "field_name": "activity_name", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充活动名称。"},
        {"rule_name": "必填-活动时间", "scenario": "club_activity", "field_name": "activity_time", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充活动时间。"},
        {"rule_name": "必填-活动地点", "scenario": "club_activity", "field_name": "activity_location", "operator": "required", "expected_value": None, "severity": "high", "suggestion": "补充活动地点。"},
    ]
    for rule_data in default_rules:
        rule = (
            db.query(RulePolicy)
            .filter(
                RulePolicy.scenario == rule_data["scenario"],
                RulePolicy.field_name == rule_data["field_name"],
                RulePolicy.operator == rule_data["operator"],
            )
            .first()
        )
        if rule:
            for key, value in rule_data.items():
                setattr(rule, key, value)
            rule.enabled = True
        else:
            db.add(RulePolicy(**rule_data))
    db.query(RulePolicy).filter(
        RulePolicy.rule_name == "人数范围-3到5人",
        RulePolicy.scenario == "competition_registration",
        RulePolicy.field_name == "team_size",
        RulePolicy.operator == "between",
        RulePolicy.expected_value == "3,5",
    ).update({"enabled": False})
    db.commit()


def list_rules(db, scenario: str) -> List[RulePolicy]:
    seed_default_rules(db)
    if _is_generic_scenario(scenario):
        return []
    rules = db.query(RulePolicy).filter(RulePolicy.scenario == scenario, RulePolicy.enabled.is_(True)).all()
    return rules


def _level_from_hits(missing: List[str], hit_results: List[Dict[str, Any]]) -> str:
    if any(item["severity"] == "high" and item["result"] != "passed" for item in hit_results):
        return "待补充"
    if missing:
        return "待补充"
    return "通过"


def _lookup_field_value(fields: dict[str, Any], field_name: str | None) -> Any:
    if not field_name:
        return None
    if fields.get(field_name):
        return fields.get(field_name)
    open_fields = fields.get("open_fields") if isinstance(fields.get("open_fields"), dict) else {}
    return open_fields.get(field_name)


def _structure_risk_items(details: dict[str, Any], scenario: str) -> list[str]:
    risks: list[str] = []
    structure = details.get("document_structure") or {}
    quality = structure.get("quality", {})
    if not structure.get("tables") and not structure.get("key_values"):
        risks.append("未识别到稳定的表格或键值结构，建议人工核对原文件版式。")
    if quality.get("needs_human_review"):
        risks.append("结构化解析置信度偏低，建议进入人工复核。")
    if _is_generic_scenario(scenario) and not details.get("open_fields"):
        risks.append("其他场景未抽取到开放字段，可检查文件是否为扫描图片或纯图片版文档。")
    for note in details.get("llm_fallback", {}).get("risk_notes", []):
        if isinstance(note, str):
            risks.append(note)
    return risks


def audit_material(
    material_name: str,
    text: str,
    scenario: str,
    rules: List[RulePolicy],
    extra_fields: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    details = merge_field_details(text, extra_fields, scenario=scenario)
    fields = details["recognized_fields"]
    required_fields = _required_fields_for(fields, scenario)
    missing = [FIELD_LABELS.get(field, field) for field in required_fields if not fields.get(field)]
    rule_hits: list[dict[str, Any]] = []

    for rule in rules:
        field_value = _lookup_field_value(fields, rule.field_name)
        result = "passed"
        suggestion = rule.suggestion
        if rule.operator == "required" and not field_value:
            result = "missing"
        elif rule.operator == "recommended" and not field_value:
            result = "recommended"
        elif rule.operator == "between":
            try:
                bounds = [int(item) for item in str(rule.expected_value or "3,5").split(",")[:2]]
                number = int(str(field_value))
            except Exception:
                result = "invalid"
            else:
                if not (bounds[0] <= number <= bounds[1]):
                    result = "invalid"
        rule_hits.append(
            {
                "rule_name": rule.rule_name,
                "severity": rule.severity,
                "result": result,
                "field_name": FIELD_LABELS.get(rule.field_name or "", rule.field_name),
                "suggestion": suggestion,
            }
        )

    level = _level_from_hits(missing, rule_hits)
    passed = level == "通过"
    quality = details["document_structure"].get("quality", {})
    extraction_confidence = float(quality.get("confidence") or 0)
    completeness = max(0, int((len(required_fields) - len(missing)) / max(1, len(required_fields)) * 100))
    structure_risks = _structure_risk_items(details, scenario)
    warnings = [item["suggestion"] for item in rule_hits if item["result"] in {"missing", "invalid", "recommended"}] + structure_risks
    conclusion = "材料字段较完整，可以进入表单预填和下一步办理。" if passed else "材料仍有缺失或风险项，建议补充并确认后再提交。"
    return {
        "material_name": material_name,
        "recognized_fields": fields,
        "raw_fields": details["raw_fields"],
        "open_fields": details["open_fields"],
        "synonym_fields": details["synonym_fields"],
        "document_structure": details["document_structure"],
        "field_matches": details["field_matches"],
        "unmapped_fields": details["unmapped_fields"],
        "missing_items": missing,
        "warnings": warnings,
        "passed": passed,
        "conclusion": conclusion,
        "level": level,
        "rule_hits": rule_hits,
        "risk_items": warnings,
        "suggestions": warnings or ["可继续生成表单预填和下一步计划。"],
        "completeness_score": completeness,
        "extraction_confidence": extraction_confidence,
        "needs_human_review": bool(quality.get("needs_human_review")) or bool(warnings),
        "llm_fallback_used": bool(details.get("llm_fallback", {}).get("used")),
    }
