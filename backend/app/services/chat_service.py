"""问答生成与意图路由服务。

优先让 LLM 识别用户意图并输出受约束的工具计划；当模型不可用或返回格式不合规
时，才退回到本地规则。真正的业务执行仍由后端固定模块完成。
"""

import json
from typing import Any, Dict, List

from app.config import settings
from app.services.llm_service import chat_completion


SYSTEM_PROMPT = """你是“智审通 Campus Copilot”的高校事务办理助手。
请基于给定证据回答，必须使用以下结构：
1. 结论：直接回答问题。
2. 依据：说明来自哪些证据、通知或规则。
3. 建议动作：给出下一步办理建议。
如果证据不足，必须明确说明“不确定”，不要编造。"""

INTENT_TOOL_MAP = {
    "knowledge_qa": ["search_knowledge"],
    "material_audit": ["extract_fields", "validate_rules"],
    "form_prefill": ["extract_fields", "prefill_form"],
    "workflow_plan": ["generate_todo_plan"],
    "integrated_process": ["search_knowledge", "extract_fields", "validate_rules", "prefill_form", "generate_todo_plan"],
}

ALLOWED_TOOLS = {
    "search_knowledge",
    "ocr_parse_file",
    "extract_fields",
    "validate_rules",
    "prefill_form",
    "generate_todo_plan",
    "save_record",
}

INTENT_ROUTER_PROMPT = """你是高校事务办理系统的意图路由器。
只返回 JSON 对象，不要解释，不要输出 Markdown。
允许的 intent: knowledge_qa, material_audit, form_prefill, workflow_plan, integrated_process。
允许的 tools: search_knowledge, ocr_parse_file, extract_fields, validate_rules, prefill_form, generate_todo_plan, save_record。
要求：
1. 只根据用户请求选择意图和工具，不要执行工具。
2. 不要编造文件 ID、材料字段或审核结论。
3. 涉及删除、最终提交、外部发送、覆盖保存时 need_user_confirmation 必须为 true。
4. 输出格式：{"intent":"...","tools":[{"name":"...","arguments":{}}],"need_user_confirmation":false,"reason":"..."}"""


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


def _rule_intent(text: str) -> tuple[str, float, str]:
    """Return a deterministic fallback intent when the model is unavailable."""
    if any(word in text for word in ["完整办理", "一键办理", "从头到尾", "全流程"]):
        return "integrated_process", 0.95, "命中综合办理明确词"
    if any(word in text for word in ["审核", "缺什么", "缺失", "核验", "能不能交", "能否提交"]):
        return "material_audit", 0.9, "命中材料审核明确词"
    if any(word in text for word in ["预填", "填表", "表单", "报名表", "申请表"]):
        return "form_prefill", 0.9, "命中表单预填明确词"
    if any(word in text for word in ["待办", "下一步", "流程", "计划", "怎么做"]):
        return "workflow_plan", 0.85, "命中流程规划明确词"
    if any(word in text for word in ["帮我看看", "看看这个", "能不能报"]):
        return "integrated_process", 0.65, "命中模糊综合办理表达"
    return "knowledge_qa", 0.7, "默认知识问答"


def _sanitize_plan(data: dict[str, Any] | None, fallback_intent: str, reason: str) -> dict[str, Any]:
    intent = str((data or {}).get("intent") or fallback_intent)
    if intent not in INTENT_TOOL_MAP:
        intent = fallback_intent

    tools: list[dict[str, Any]] = []
    raw_tools = (data or {}).get("tools")
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, str):
                name = item
                arguments: dict[str, Any] = {}
            elif isinstance(item, dict):
                name = str(item.get("name") or "")
                raw_arguments = item.get("arguments")
                arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
            else:
                continue
            if name in ALLOWED_TOOLS:
                tools.append({"name": name, "arguments": arguments})

    if not tools:
        tools = [{"name": name, "arguments": {}} for name in INTENT_TOOL_MAP[intent]]

    return {
        "intent": intent,
        "tools": tools,
        "need_user_confirmation": bool((data or {}).get("need_user_confirmation", False)),
        "reason": str((data or {}).get("reason") or reason),
    }


def plan_user_request(text: str) -> dict[str, Any]:
    """LLM-first intent router with deterministic fallback."""
    rule_intent, confidence, reason = _rule_intent(text)
    if settings.DEMO_MODE:
        return _sanitize_plan(None, rule_intent, reason)

    user_prompt = json.dumps({"user_request": text}, ensure_ascii=False)
    data = _parse_json_object(chat_completion(INTENT_ROUTER_PROMPT, user_prompt))
    if data:
        return _sanitize_plan(data, rule_intent, "LLM 意图路由")
    return _sanitize_plan(data, rule_intent, reason)


def detect_intent(text: str) -> str:
    return plan_user_request(text)["intent"]


def _extract_from_contexts(question: str, contexts: List[Dict[str, Any]]) -> str:
    citations = "、".join(str(index + 1) for index, _ in enumerate(contexts[:4])) or "无"

    if not contexts:
        return (
            "1. 结论：当前没有可用证据，无法给出确定答案。\n"
            "2. 依据：未检索到选中文件中的制度、通知或规则片段。\n"
            "3. 建议动作：请先在左侧勾选相关制度/通知文件，再重新提问。"
        )

    previews = []
    for index, item in enumerate(contexts[:3], start=1):
        text = str(item.get("text") or "").strip().replace("\n", " ")
        if text:
            previews.append(f"[{index}] {text[:180]}")
    preview = "\n".join(previews)
    return (
        "1. 结论：已在选中文件的解析内容中检索到相关片段，但当前模型不可用，系统不直接生成具体业务结论。\n"
        f"2. 依据：命中的证据编号为[{citations}]。相关片段包括：\n{preview}\n"
        "3. 建议动作：请查看右侧引用依据；如需自动归纳结论，请开启模型服务后重新提问。"
    )


def generate_answer(question: str, contexts: List[Dict[str, Any]]) -> tuple[str, bool]:
    fallback_answer = _extract_from_contexts(question, contexts)
    if settings.DEMO_MODE:
        return fallback_answer, True

    context_block = "\n\n".join(f"[{index + 1}] {item.get('text', '')}" for index, item in enumerate(contexts))
    user_prompt = f"用户问题：{question}\n\n证据：\n{context_block}\n\n请按指定结构回答。"
    answer = chat_completion(SYSTEM_PROMPT, user_prompt)
    if answer:
        return answer, False
    return fallback_answer, True


def default_suggestions(question: str) -> List[str]:
    if any(word in question for word in ["报名", "参赛", "比赛"]):
        return ["上传报名材料进行审核", "预填报名表", "生成比赛报名待办计划"]
    if any(word in question for word in ["请假", "审批"]):
        return ["上传证明材料", "预填请假单", "生成审批待办"]
    return ["继续上传材料", "提取材料信息", "生成下一步计划"]
