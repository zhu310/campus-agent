"""Document-grounded workflow planning service.

The workflow plan should be derived from uploaded notices, rules and form
templates whenever they are available. Scenario names are treated only as hints;
they no longer select fixed business templates.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.document_structure_service import build_document_structure, clean_cell
from app.services.llm_service import chat_completion


DATE_RE = re.compile(
    r"(?:(?:20\d{2})[年./-]\s*)?\d{1,2}\s*[月./-]\s*\d{1,2}\s*日?(?:\s*(?:前|之前|截止|止))?"
    r"|20\d{2}\s*[年./-]\s*\d{1,2}\s*(?:[月./-]\s*\d{1,2}\s*日?)?"
)
SUBMIT_RE = re.compile(r"(?:提交|报送|发送|上传|递交|交至|发送至|邮箱|系统|平台|办公室|联系人|联系电话).{0,80}")
MATERIAL_RE = re.compile(r"(?:材料|附件|表|证明|申请书|承诺书|名单|作品|报告|截图|身份证|成绩单|证书)")
RISK_RE = re.compile(r"(?:逾期|不予|无效|退回|取消|不得|必须|需|应|不得|风险|注意|未按|缺失).{0,80}")


def _lines_from_documents(documents: list[dict[str, Any]]) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    for doc in documents:
        structure = build_document_structure(str(doc.get("content") or ""))
        for item in structure.get("lines", []):
            text = clean_cell(item.get("text"))
            if text:
                lines.append(
                    {
                        "filename": str(doc.get("filename") or "选中文件"),
                        "location": str(item.get("location") or ""),
                        "text": text,
                    }
                )
    return lines


def _unique(items: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = clean_cell(item)
        key = re.sub(r"\s+", "", text).lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text[:140])
        if len(result) >= limit:
            break
    return result


def _extract_deadlines(lines: list[dict[str, str]]) -> list[str]:
    hits: list[str] = []
    for item in lines:
        text = item["text"]
        if any(word in text for word in ["截止", "时间", "日期", "前", "报送", "提交"]):
            matches = DATE_RE.findall(text)
            if matches:
                hits.append(f"{matches[0].strip()}：{text}")
    return _unique(hits, 5)


def _extract_submit_methods(lines: list[dict[str, str]]) -> list[str]:
    return _unique([match.group(0) for item in lines for match in SUBMIT_RE.finditer(item["text"])], 6)


def _extract_required_materials(lines: list[dict[str, str]]) -> list[str]:
    candidates: list[str] = []
    for item in lines:
        text = item["text"]
        if MATERIAL_RE.search(text):
            if "|" in text:
                candidates.extend(cell for cell in text.split("|") if MATERIAL_RE.search(cell))
            else:
                candidates.append(text)
    return _unique(candidates, 10)


def _extract_risks(lines: list[dict[str, str]]) -> list[str]:
    return _unique([match.group(0) for item in lines for match in RISK_RE.finditer(item["text"])], 8)


def _llm_workflow(request_text: str, documents: list[dict[str, Any]], facts: dict[str, list[str]]) -> dict[str, Any] | None:
    if not documents:
        return None
    compact_docs = [
        {
            "filename": doc.get("filename"),
            "content_preview": str(doc.get("content") or "")[:3000],
        }
        for doc in documents[:5]
    ]
    prompt = (
        "请只基于用户请求、上传文件内容和已抽取事实生成办理流程 JSON，不要编造文件中没有的截止时间、提交方式或材料。\n"
        "输出格式："
        '{"summary":"...","todos":["..."],"steps":[{"title":"...","detail":"...","deadline":null}],'
        '"required_materials":["..."],"risk_reminders":["..."]}\n\n'
        f"用户请求：{request_text}\n"
        f"已抽取事实：{facts}\n"
        f"文件摘要：{compact_docs}"
    )
    answer = chat_completion("你是高校事务办理流程规划助手，只输出合法 JSON。", prompt)
    if not answer:
        return None
    start = answer.find("{")
    end = answer.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        import json

        data = json.loads(answer[start : end + 1])
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    return {
        "intent": "workflow_plan",
        "summary": str(data.get("summary") or "已基于选中文件生成办理流程。"),
        "todos": [str(item) for item in data.get("todos", []) if str(item).strip()][:8],
        "steps": [
            {
                "title": str(item.get("title") or "办理步骤"),
                "detail": str(item.get("detail") or ""),
                "deadline": item.get("deadline") if item.get("deadline") else None,
            }
            for item in steps
            if isinstance(item, dict)
        ][:8],
        "required_materials": [str(item) for item in data.get("required_materials", []) if str(item).strip()][:10],
        "risk_reminders": [str(item) for item in data.get("risk_reminders", []) if str(item).strip()][:8],
        "fallback_used": False,
    }


def _fallback_workflow(request_text: str, scenario: str, facts: dict[str, list[str]], has_documents: bool) -> dict[str, Any]:
    materials = facts["required_materials"] or ["办理材料或个人信息", "相关表单模板", "必要证明附件"]
    deadlines = facts["deadlines"]
    submit_methods = facts["submit_methods"]
    risks = facts["risks"]

    steps = [
        {
            "title": "确认办理依据",
            "detail": "阅读选中的制度、通知或表单说明，确认适用对象、材料范围和关键限制。",
            "deadline": deadlines[0].split("：", 1)[0] if deadlines else None,
        },
        {
            "title": "整理并上传材料",
            "detail": "按文件要求准备个人信息、证明附件和待填写表格，并确认解析结果可读。",
            "deadline": None,
        },
        {
            "title": "抽取字段并审核缺失",
            "detail": "运行字段抽取和规则审核，重点核对必填字段、时间、联系方式、签名盖章等项目。",
            "deadline": None,
        },
        {
            "title": "生成表单草稿",
            "detail": "根据上传表格模板中的真实字段生成草稿，未匹配字段保持空缺并进入补充清单。",
            "deadline": None,
        },
        {
            "title": "提交与留痕",
            "detail": submit_methods[0] if submit_methods else "按通知指定渠道提交，并保存系统审核结果和提交记录。",
            "deadline": deadlines[0].split("：", 1)[0] if deadlines else None,
        },
    ]
    summary = "已基于选中文件抽取办理材料、时间和提交要求，生成可执行流程。" if has_documents else "当前未选择制度/通知文件，流程只能基于通用办理链路生成。"
    if request_text.strip():
        summary = f"{summary} 用户目标：{request_text.strip()[:80]}"
    return {
        "intent": "workflow_plan",
        "summary": summary,
        "todos": [step["title"] for step in steps],
        "steps": steps,
        "required_materials": materials,
        "risk_reminders": risks or ["未上传规则文件时，截止时间、提交渠道和材料清单需要人工确认。"],
        "fallback_used": True,
        "scenario_hint": scenario,
    }


def plan_workflow(request_text: str, scenario: str = "general", documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    docs = documents or []
    lines = _lines_from_documents(docs)
    facts = {
        "deadlines": _extract_deadlines(lines),
        "submit_methods": _extract_submit_methods(lines),
        "required_materials": _extract_required_materials(lines),
        "risks": _extract_risks(lines),
    }
    llm_result = _llm_workflow(request_text, docs, facts)
    if llm_result and llm_result["steps"]:
        if not llm_result["todos"]:
            llm_result["todos"] = [step["title"] for step in llm_result["steps"]]
        if not llm_result["required_materials"]:
            llm_result["required_materials"] = facts["required_materials"]
        if not llm_result["risk_reminders"]:
            llm_result["risk_reminders"] = facts["risks"]
        return llm_result
    return _fallback_workflow(request_text, scenario, facts, bool(docs))
