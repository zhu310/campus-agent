"""Notice reading, task-card extraction, and writing-assistant services."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.models import Document
from app.services.llm_service import chat_completion


DATE_RE = re.compile(
    r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?(?:\s*\d{1,2}[:：]\d{2})?|"
    r"\d{1,2}月\d{1,2}日(?:\s*\d{1,2}[:：]\d{2})?|"
    r"\d{1,2}[/-]\d{1,2}(?:\s*\d{1,2}[:：]\d{2})?)"
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s，。；;]+")


NOTICE_TASK_PROMPT = """你是高校通知阅读与完整办理流程梳理助手。
根据用户选中的通知/制度原文，提取用户从开始准备到最终提交/确认的完整操作流程。只返回 JSON，不要解释。
要求：
1. 所有截止时间、提交方式、材料清单、风险提醒必须来自原文证据；不确定就留空或写入 missing_information。
2. tasks 不是“下一步提醒”，而是完整办理事项。每个 task 的 steps 必须覆盖用户需要做的连续动作，例如阅读资格、准备材料、填写表单、提交、确认回执、补正或复核。
3. steps 要按执行顺序写成具体动作，尽量从整份文件提炼，不要只输出一条“下一步”。
4. 可以合并多个文件中的同类事项，但要保留 evidence。
5. 不要编造文件里没有的要求。
JSON 格式：
{"summary":"...","tasks":[{"title":"...","deadline":null,"submit_method":null,"required_materials":[],"steps":[],"risk_reminders":[],"evidence":[{"document_id":1,"filename":"...","text":"...","location":"..."}],"status":""}],"missing_information":[],"cross_document_risks":[]}"""


FILL_ASSISTANT_PROMPT = """你是高校文件填写助手。
你不能直接假装完成提交，只能根据通知/模板要求和用户已提供信息，判断还缺什么，并生成可复制的文字草稿。
只返回 JSON，不要解释。
要求：
1. required_information 写用户还需要补充的信息。
2. questions 用自然语言追问用户。
3. draft_sections 只为已有足够信息的字段生成草稿；大段文字可以生成建议稿。
4. 所有要求依据必须来自通知/模板原文或用户已提供信息，不确定不要编造。
JSON 格式：
{"required_information":[],"questions":[],"draft_sections":[{"field_name":"...","draft":"...","basis":"...","needs_user_input":false}],"risks":[],"evidence":[{"document_id":1,"filename":"...","text":"...","location":"..."}]}"""


FILL_REVIEW_PROMPT = """你是高校文件填写审核助手。
请根据通知/模板要求、用户个人信息和用户草稿，审核填写内容是否一致、完整、符合要求。
只返回 JSON，不要解释。
要求：
1. 检查是否缺字段、是否与用户信息冲突、是否违反通知/模板要求。
2. 不要判断原文没有规定的要求。
JSON 格式：
{"passed":false,"conclusion":"...","issues":[],"suggestions":[],"evidence":[{"document_id":1,"filename":"...","text":"...","location":"..."}]}"""


def _parse_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _doc_payload(doc: Document, limit: int = 9000) -> dict[str, Any]:
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "scenario": doc.scenario,
        "source_type": doc.source_type,
        "text": (doc.content or "")[:limit],
    }


def _line_evidence(doc: Document, patterns: list[str], max_items: int = 3) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    lines = [line.strip() for line in (doc.content or "").splitlines() if line.strip()]
    for idx, line in enumerate(lines, start=1):
        if any(pattern in line for pattern in patterns) or DATE_RE.search(line) or EMAIL_RE.search(line) or URL_RE.search(line):
            evidence.append({"document_id": doc.id, "filename": doc.filename, "text": line[:500], "location": f"第 {idx} 行"})
        if len(evidence) >= max_items:
            break
    if not evidence and lines:
        evidence.append({"document_id": doc.id, "filename": doc.filename, "text": lines[0][:500], "location": "第 1 行"})
    return evidence


def _fallback_notice_tasks(docs: list[Document], user_goal: str) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for doc in docs:
        text = doc.content or ""
        deadline = DATE_RE.search(text)
        emails = EMAIL_RE.findall(text)
        urls = URL_RE.findall(text)
        evidence = _line_evidence(doc, ["材料", "提交", "截止", "报名", "申请", "附件", "流程", "审核", "联系"])
        required_materials = _extract_material_hints(text)
        tasks.append(
            {
                "title": f"完整办理流程：{doc.filename}",
                "deadline": deadline.group(0) if deadline else None,
                "submit_method": emails[0] if emails else (urls[0] if urls else None),
                "required_materials": required_materials,
                "steps": _extract_flow_steps(text, required_materials, bool(deadline), bool(emails or urls)),
                "risk_reminders": ["当前为本地规则梳理结果，请结合原文逐项核对截止时间、提交入口和材料口径。"],
                "evidence": evidence,
                "status": "",
            }
        )
    return {
        "summary": f"已根据 {len(docs)} 份文件梳理完整办理流程。本地兜底不会编造原文外要求。",
        "tasks": tasks,
        "missing_information": ["如需更细的流程拆解，请开启 LLM 服务。"] if settings.DEMO_MODE else [],
        "cross_document_risks": [],
        "fallback_used": True,
    }


def _extract_material_hints(text: str) -> list[str]:
    hints: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if any(word in cleaned for word in ["材料", "附件", "提交", "报名表", "申请表", "证明"]):
            hints.append(cleaned[:120])
        if len(hints) >= 6:
            break
    return hints


def _extract_flow_steps(text: str, required_materials: list[str], has_deadline: bool, has_submit_method: bool) -> list[str]:
    steps: list[str] = []
    keyword_groups = [
        ("确认资格和适用范围", ["对象", "资格", "条件", "范围", "参赛", "申请人"]),
        ("按通知要求准备材料", ["材料", "附件", "证明", "报名表", "申请表"]),
        ("填写或完善申请/报名信息", ["填写", "填报", "报名", "申请", "登记"]),
        ("按指定方式提交材料", ["提交", "发送", "上传", "报送", "递交"]),
        ("等待审核并按要求补正", ["审核", "复核", "补正", "修改", "公示"]),
        ("保存提交记录并关注后续通知", ["通知", "联系", "群", "邮箱", "电话", "结果"]),
    ]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for fallback_step, keywords in keyword_groups:
        matched = next((line for line in lines if any(keyword in line for keyword in keywords)), "")
        if matched:
            steps.append(f"{fallback_step}：{matched[:120]}")
        elif fallback_step == "按通知要求准备材料" and required_materials:
            steps.append(f"{fallback_step}：整理原文列出的 {len(required_materials)} 项材料。")
        elif fallback_step == "按指定方式提交材料" and has_submit_method:
            steps.append(fallback_step)
    if has_deadline:
        steps.insert(0, "先确认并记录原文中的截止时间，倒排准备和提交时间。")
    if not steps:
        steps = ["通读通知原文，标出办理对象、材料要求、截止时间和提交方式。", "整理材料并按原文要求提交，提交前人工复核。"]
    return list(dict.fromkeys(steps))[:8]


def _sanitize_evidence(raw_items: Any, docs: list[Document]) -> list[dict[str, Any]]:
    doc_map = {doc.id: doc for doc in docs}
    evidence: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            doc_id = int(item.get("document_id") or 0)
            doc = doc_map.get(doc_id)
            if not doc:
                continue
            text = str(item.get("text") or "")[:600]
            evidence.append(
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "text": text,
                    "location": item.get("location"),
                }
            )
    return evidence


def generate_notice_tasks(docs: list[Document], user_goal: str, scenario: str) -> dict[str, Any]:
    fallback = _fallback_notice_tasks(docs, user_goal)
    if settings.DEMO_MODE or not docs:
        return fallback
    payload = {"user_goal": user_goal, "scenario": scenario, "documents": [_doc_payload(doc) for doc in docs]}
    parsed = _parse_json_object(chat_completion(NOTICE_TASK_PROMPT, json.dumps(payload, ensure_ascii=False)))
    if not parsed:
        return fallback
    tasks: list[dict[str, Any]] = []
    for item in parsed.get("tasks", []):
        if not isinstance(item, dict):
            continue
        tasks.append(
            {
                "title": str(item.get("title") or "未命名任务"),
                "deadline": item.get("deadline"),
                "submit_method": item.get("submit_method"),
                "required_materials": item.get("required_materials") if isinstance(item.get("required_materials"), list) else [],
                "steps": item.get("steps") if isinstance(item.get("steps"), list) else [],
                "risk_reminders": item.get("risk_reminders") if isinstance(item.get("risk_reminders"), list) else [],
                "evidence": _sanitize_evidence(item.get("evidence"), docs),
                "status": str(item.get("status") or ""),
            }
        )
    return {
        "summary": str(parsed.get("summary") or fallback["summary"]),
        "tasks": tasks or fallback["tasks"],
        "missing_information": parsed.get("missing_information") if isinstance(parsed.get("missing_information"), list) else [],
        "cross_document_risks": parsed.get("cross_document_risks") if isinstance(parsed.get("cross_document_risks"), list) else [],
        "fallback_used": False,
    }


def generate_fill_assistant(docs: list[Document], user_profile: str, form_text: str, draft_content: str, scenario: str) -> dict[str, Any]:
    fallback = {
        "required_information": ["姓名/身份信息", "办理事项名称", "申请理由或说明", "联系方式"],
        "questions": ["请补充你的基本信息、办理目标、已有材料和需要生成的大段文字。"],
        "draft_sections": [],
        "risks": ["模型不可用，无法可靠生成填写草稿。"],
        "evidence": _line_evidence(docs[0], ["材料", "填写", "要求"]) if docs else [],
        "fallback_used": True,
    }
    if settings.DEMO_MODE:
        return fallback
    payload = {
        "scenario": scenario,
        "user_profile": user_profile[:6000],
        "form_text": form_text[:6000],
        "draft_content": draft_content[:6000],
        "documents": [_doc_payload(doc, 7000) for doc in docs],
    }
    parsed = _parse_json_object(chat_completion(FILL_ASSISTANT_PROMPT, json.dumps(payload, ensure_ascii=False)))
    if not parsed:
        return fallback
    return {
        "required_information": parsed.get("required_information") if isinstance(parsed.get("required_information"), list) else [],
        "questions": parsed.get("questions") if isinstance(parsed.get("questions"), list) else [],
        "draft_sections": parsed.get("draft_sections") if isinstance(parsed.get("draft_sections"), list) else [],
        "risks": parsed.get("risks") if isinstance(parsed.get("risks"), list) else [],
        "evidence": _sanitize_evidence(parsed.get("evidence"), docs),
        "fallback_used": False,
    }


def review_filled_content(docs: list[Document], user_profile: str, draft_content: str, scenario: str) -> dict[str, Any]:
    fallback = {
        "passed": False,
        "conclusion": "模型不可用，无法完成基于通知要求的语义审核；请人工核对引用原文、个人信息和草稿内容。",
        "issues": ["未执行 LLM 审核"],
        "suggestions": ["开启模型服务后重新审核，或人工逐项核对通知要求。"],
        "evidence": _line_evidence(docs[0], ["要求", "材料", "填写"]) if docs else [],
        "fallback_used": True,
    }
    if settings.DEMO_MODE:
        return fallback
    payload = {
        "scenario": scenario,
        "user_profile": user_profile[:6000],
        "draft_content": draft_content[:10000],
        "documents": [_doc_payload(doc, 7000) for doc in docs],
    }
    parsed = _parse_json_object(chat_completion(FILL_REVIEW_PROMPT, json.dumps(payload, ensure_ascii=False)))
    if not parsed:
        return fallback
    return {
        "passed": bool(parsed.get("passed")),
        "conclusion": str(parsed.get("conclusion") or ""),
        "issues": parsed.get("issues") if isinstance(parsed.get("issues"), list) else [],
        "suggestions": parsed.get("suggestions") if isinstance(parsed.get("suggestions"), list) else [],
        "evidence": _sanitize_evidence(parsed.get("evidence"), docs),
        "fallback_used": False,
    }
