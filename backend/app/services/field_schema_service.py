"""Configurable field schema layer.

The built-in dictionaries keep the demo self-contained, while this service gives
the rest of the code one place to read scenario-specific field aliases and
required fields. A future admin page can persist the same shape in the database.
"""

from __future__ import annotations

from typing import Any


FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "competition_registration": {
        "required_fields": ["name", "phone", "email", "project_name", "team_size"],
        "field_priorities": ["project_name", "name", "team_members", "team_size", "phone", "email", "advisor"],
    },
    "leave_approval": {
        "required_fields": ["name", "student_id", "college_class", "leave_reason", "leave_start", "leave_end", "phone"],
        "field_priorities": ["name", "student_id", "college_class", "leave_reason", "leave_start", "leave_end", "proof", "phone"],
    },
    "reimbursement": {
        "required_fields": ["name", "amount", "invoice", "project_name"],
        "field_priorities": ["name", "amount", "invoice", "invoice_type", "project_name", "phone"],
    },
    "scholarship": {
        "required_fields": [
            "name", "gender", "birth_date", "ethnicity", "political_status",
            "enrollment_date", "student_id", "grade", "id_number", "phone",
            "college_class", "awards", "family_population", "family_income",
            "income_source", "family_address", "postal_code", "grade_rank",
            "application_reason",
        ],
        "field_priorities": [
            "name", "gender", "birth_date", "ethnicity", "political_status",
            "enrollment_date", "student_id", "grade", "id_number", "phone",
            "college_class", "awards", "family_population", "family_income",
            "per_capita_income", "income_source", "family_address", "postal_code",
            "poverty_level", "grade_rank", "comprehensive_rank", "application_reason",
        ],
    },
    "scholarship_application": {
        "required_fields": [
            "name", "gender", "birth_date", "ethnicity", "political_status",
            "enrollment_date", "student_id", "grade", "id_number", "phone",
            "college_class", "awards", "family_population", "family_income",
            "income_source", "family_address", "postal_code", "grade_rank",
            "application_reason",
        ],
        "field_priorities": [
            "name", "gender", "birth_date", "ethnicity", "political_status",
            "enrollment_date", "student_id", "grade", "id_number", "phone",
            "college_class", "awards", "family_population", "family_income",
            "per_capita_income", "income_source", "family_address", "postal_code",
            "poverty_level", "grade_rank", "comprehensive_rank", "application_reason",
        ],
    },
    "club_activity": {
        "required_fields": ["applicant", "activity_name", "activity_time", "activity_location", "phone"],
        "field_priorities": ["applicant", "activity_name", "activity_time", "activity_location", "phone", "email"],
    },
}


GENERIC_SCENARIOS = {"", "generic", "general", "other", "custom", "其他", "其他场景", "自定义场景"}


def is_generic_scenario(scenario: str | None) -> bool:
    if scenario is None:
        return True
    normalized = str(scenario).strip().lower()
    return normalized in GENERIC_SCENARIOS or normalized not in FIELD_SCHEMAS


def scenario_schema(scenario: str | None) -> dict[str, Any]:
    if is_generic_scenario(scenario):
        return {"required_fields": [], "field_priorities": []}
    return FIELD_SCHEMAS.get(str(scenario), {"required_fields": [], "field_priorities": []})
