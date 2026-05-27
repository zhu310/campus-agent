"""导出接口。

把最近一次审核、表单预填和流程规划结果导出为纯文本，方便演示或归档。
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AuditResult, ChatLog, FormFillResult, WorkflowRun

router = APIRouter(prefix="/exports", tags=["exports"])


def _fmt_dict(data: dict[str, Any]) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) if lines else "- 暂无数据"


@router.get("/audit/latest", response_class=PlainTextResponse)
def export_latest_audit(db: Session = Depends(get_db)):
    item = db.query(AuditResult).order_by(AuditResult.created_at.desc()).first()
    if not item:
        return "暂无审核摘要。"
    result = item.result or {}
    content = [
        "# 审核摘要",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"审核结论：{result.get('level', '-')}",
        f"完整度：{result.get('completeness_score', '-')}",
        "",
        "## 缺失项",
        "\n".join(f"- {x}" for x in result.get("missing_items", [])) or "- 无",
        "",
        "## 风险项",
        "\n".join(f"- {x}" for x in result.get("risk_items", [])) or "- 无",
        "",
        "## 建议",
        "\n".join(f"- {x}" for x in result.get("suggestions", [])) or "- 无",
    ]
    return "\n".join(content)


@router.get("/form/latest", response_class=PlainTextResponse)
def export_latest_form(db: Session = Depends(get_db)):
    item = db.query(FormFillResult).order_by(FormFillResult.created_at.desc()).first()
    if not item:
        return "暂无表单结果。"
    result = item.result or {}
    return "\n".join([
        "# 表单预填结果",
        f"模板：{item.template_name}",
        f"生成时间：{item.created_at.isoformat()}",
        "",
        "## 字段",
        _fmt_dict(result.get("fields", {})),
        "",
        "## 仍需补充",
        "\n".join(f"- {x}" for x in result.get("missing_fields", [])) or "- 无",
    ])


@router.get("/workflow/latest", response_class=PlainTextResponse)
def export_latest_workflow(db: Session = Depends(get_db)):
    item = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).first()
    if not item:
        return "暂无待办计划。"
    result = item.result or {}
    steps = result.get("steps", [])
    return "\n".join([
        "# 待办计划",
        result.get("summary", ""),
        "",
        "## 步骤",
        "\n".join(f"- {step.get('title')}: {step.get('detail')} {step.get('deadline') or ''}" for step in steps) or "- 无",
        "",
        "## 风险提醒",
        "\n".join(f"- {x}" for x in result.get("risk_reminders", [])) or "- 无",
    ])


@router.get("/demo/latest", response_class=PlainTextResponse)
def export_demo_summary(db: Session = Depends(get_db)):
    chat = db.query(ChatLog).order_by(ChatLog.created_at.desc()).first()
    audit = db.query(AuditResult).order_by(AuditResult.created_at.desc()).first()
    form = db.query(FormFillResult).order_by(FormFillResult.created_at.desc()).first()
    workflow = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).first()
    return "\n".join([
        "# 智审通 Campus Copilot 演示摘要",
        f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## RAG 问答",
        chat.answer if chat else "暂无问答记录。",
        "",
        "## 审核结果",
        _fmt_dict((audit.result or {}) if audit else {}),
        "",
        "## 表单结果",
        _fmt_dict((form.result or {}).get("fields", {}) if form else {}),
        "",
        "## 下一步计划",
        (workflow.result or {}).get("summary", "暂无待办计划。") if workflow else "暂无待办计划。",
    ])
