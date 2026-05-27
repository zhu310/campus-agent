"""审核规则查询接口。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas import RulePolicyItem
from app.services.audit_service import list_rules

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RulePolicyItem])
def get_rules(scenario: str = "competition_registration", db: Session = Depends(get_db)):
    rules = list_rules(db, scenario)
    return [
        RulePolicyItem(
            id=item.id,
            rule_name=item.rule_name,
            scenario=item.scenario,
            field_name=item.field_name,
            operator=item.operator,
            expected_value=item.expected_value,
            severity=item.severity,
            suggestion=item.suggestion,
        )
        for item in rules
    ]
