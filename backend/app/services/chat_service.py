"""问答生成服务。

优先调用外部大模型生成结构化答案；模型不可用时，根据检索证据本地抽取结论，
保证演示流程仍可闭环。
"""

from typing import Any, Dict, List

from app.config import settings
from app.services.llm_service import chat_completion


SYSTEM_PROMPT = """你是“智审通 Campus Copilot”的高校事务办理助手。
请基于给定证据回答，必须使用以下结构：
1. 结论：直接回答问题。
2. 依据：说明来自哪些证据、通知或规则。
3. 建议动作：给出下一步办理建议。
如果证据不足，必须明确说明“不确定”，不要编造。"""


def detect_intent(text: str) -> str:
    if any(word in text for word in ["审核", "缺什么", "缺失", "材料", "核验"]):
        return "material_audit"
    if any(word in text for word in ["预填", "填表", "表单", "报名表", "申请表"]):
        return "form_prefill"
    if any(word in text for word in ["待办", "下一步", "流程", "计划", "怎么做"]):
        return "workflow_plan"
    if any(word in text for word in ["帮我看看", "能不能报", "完整办理", "一键办理"]):
        return "integrated_process"
    return "knowledge_qa"


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _extract_from_contexts(question: str, contexts: List[Dict[str, Any]]) -> str:
    context_text = "\n".join(item.get("text", "") for item in contexts)
    citations = "、".join(str(index + 1) for index, _ in enumerate(contexts[:4])) or "无"

    if not contexts:
        return (
            "1. 结论：当前没有可用证据，无法给出确定答案。\n"
            "2. 依据：未检索到选中文件中的制度、通知或规则片段。\n"
            "3. 建议动作：请先在左侧勾选相关制度/通知文件，再重新提问。"
        )

    if _contains_any(question, ["单人", "一个人", "个人参赛", "能否参赛"]):
        if _contains_any(context_text, ["3-5人", "3~5人", "3 至 5", "3至5", "每队3", "每队 3"]):
            return (
                "1. 结论：单人不能参赛。本次比赛要求以团队形式参加，每队人数为3至5人。\n"
                f"2. 依据：证据[{citations}]中提到组队方式为每队3-5人，并需要选出一名队长。\n"
                "3. 建议动作：请再寻找2至4名同学组队，确定队长后再填写报名表。"
            )

    if _contains_any(question, ["截止", "报名时间", "什么时候报名"]):
        if _contains_any(context_text, ["5月12日", "5 月 12", "18:00"]):
            return (
                "1. 结论：报名截止时间为5月12日18:00。\n"
                f"2. 依据：证据[{citations}]中的报名安排写明需在5月12日18:00前提交报名材料。\n"
                "3. 建议动作：请提前整理报名表、团队成员信息和联系方式，避免临近截止时间提交失败。"
            )

    if _contains_any(question, ["作品提交", "提交到哪里", "邮箱", "发送到哪里"]):
        if "jsjkcb2025@163.com" in context_text:
            return (
                "1. 结论：作品或报名材料需要发送到邮箱 jsjkcb2025@163.com。\n"
                f"2. 依据：证据[{citations}]中给出了材料接收邮箱。\n"
                "3. 建议动作：发送前请检查邮件标题、附件命名、报名表和作品材料是否齐全。"
            )

    if _contains_any(question, ["参赛对象", "谁能参加", "哪些学院"]):
        for line in context_text.splitlines():
            if "参赛对象" in line or "计算机学院" in line or "相关技术方向学院" in line:
                return (
                    "1. 结论：参赛对象以通知中的具体说明为准，当前证据显示面向山东科技大学计算机学院以及其他相关技术方向学院学生。\n"
                    f"2. 依据：证据[{citations}]中出现了“参赛对象”“计算机学院”“相关技术方向学院”等描述。\n"
                    "3. 建议动作：如所在学院不确定是否属于相关技术方向，建议联系学院或赛事负责人确认。"
                )

    preview = contexts[0].get("text", "")[:220]
    return (
        "1. 结论：已根据选中文件检索到相关依据，但需要结合右侧引用片段进一步确认细节。\n"
        f"2. 依据：证据[{citations}]命中文件内容，例如：{preview}\n"
        "3. 建议动作：请查看右侧引用依据；如要继续办理，可上传材料后进行字段抽取、审核和表单预填。"
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
