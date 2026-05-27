"""流程规划服务。

根据场景返回稳定的办理步骤模板；比赛报名、社会实践、请假等高频场景有专门
模板，其余场景走通用办理计划。
"""

from typing import Any, Dict


def _competition_workflow() -> Dict[str, Any]:
    return {
        "intent": "workflow_plan",
        "summary": "系统识别为比赛报名办理场景，建议按确认资格、组建团队、补齐报名表、整理作品材料、邮件提交和路演准备推进。",
        "todos": ["确认参赛资格", "组建3-5人团队", "补齐报名表", "整理作品材料", "发送邮件提交", "准备路演"],
        "steps": [
            {"title": "确认参赛规则", "detail": "核对参赛对象、队伍人数、报名截止时间和作品提交要求。", "deadline": None},
            {"title": "组建团队", "detail": "确认队伍人数符合3-5人要求，并明确负责人或队长。", "deadline": "尽快"},
            {"title": "补齐报名表", "detail": "补齐负责人、联系方式、邮箱、项目名称、成员信息、指导教师等字段。", "deadline": "2026-05-12 18:00"},
            {"title": "整理作品材料", "detail": "准备作品说明、核心亮点、技术路线、商业价值和演示材料。", "deadline": "2026-05-30"},
            {"title": "邮件提交", "detail": "将报名表和作品材料打包后发送到通知指定邮箱。", "deadline": "2026-05-30"},
            {"title": "准备路演", "detail": "准备10分钟展示、系统演示脚本和网络异常降级方案。", "deadline": "2026-06-06"},
        ],
        "required_materials": ["比赛通知", "报名表", "作品说明", "团队成员信息", "演示材料"],
        "risk_reminders": ["队伍人数不满足3-5人会影响合规性。", "报名表和作品材料要分别关注截止时间。", "建议准备离线截图或演示视频作为备用。"],
    }


def _social_practice_workflow() -> Dict[str, Any]:
    return {
        "intent": "workflow_plan",
        "summary": "系统识别为思想政治理论课综合实践周志材料，建议围绕基础信息、成员任务、实践内容、数据证据和提交归档推进。",
        "todos": ["核对基础信息", "检查成员任务记录", "整理实践内容", "补充数据证据", "格式归档"],
        "steps": [
            {"title": "核对基础信息", "detail": "检查团队名称、团队编号、实践题目、学院班级、队长姓名、联系方式和周次时间。", "deadline": None},
            {"title": "检查成员任务记录", "detail": "确认每位成员均有任务分工和完成情况，避免成员遗漏。", "deadline": None},
            {"title": "整理实践内容", "detail": "梳理访谈、调研数据、跨场景对比、矛盾点识别和阶段性结论。", "deadline": None},
            {"title": "补充数据证据", "detail": "补充数据来源、样本数量、统计方法或截图附件，增强材料可信度。", "deadline": None},
            {"title": "格式归档", "detail": "统一格式后导出或提交到课程指定平台。", "deadline": "按课程要求"},
        ],
        "required_materials": ["实践周志", "成员任务记录", "调研数据", "分析结论", "课程提交说明"],
        "risk_reminders": ["成员任务记录不完整会影响过程性评价。", "数据结论需有来源支撑。", "格式不统一会影响老师快速审核。"],
    }


def _leave_workflow() -> Dict[str, Any]:
    return {
        "intent": "workflow_plan",
        "summary": "系统识别为请假审批场景，建议按证明材料、请假单预填、辅导员/学院审批和销假归档推进。",
        "todos": ["准备证明材料", "填写请假单", "提交审批", "关注审批结果", "按时销假"],
        "steps": [
            {"title": "准备证明材料", "detail": "根据病假、事假或公假类型准备病历、证明或说明材料。", "deadline": None},
            {"title": "填写请假单", "detail": "补齐姓名、学号、学院班级、请假时间、请假原因和联系方式。", "deadline": "提交前"},
            {"title": "提交审批", "detail": "按学院流程提交给辅导员、导师或学院负责人审批。", "deadline": None},
            {"title": "销假归档", "detail": "返校后按要求销假并保存审批记录。", "deadline": "返校后"},
        ],
        "required_materials": ["请假单", "证明材料", "联系方式", "请假时间说明"],
        "risk_reminders": ["请假时间和证明材料不一致会影响审批。", "未及时销假可能影响后续请假记录。"],
    }


def _generic_workflow(scenario: str) -> Dict[str, Any]:
    name = scenario or "自定义场景"
    return {
        "intent": "workflow_plan",
        "summary": f"系统识别为{name}办理场景，建议复用统一链路：确认规则、抽取字段、审核缺失、预填表单、生成下一步并留痕。",
        "todos": ["确认办理规则", "整理办理材料", "提取材料字段", "审核缺失风险", "生成下一步计划"],
        "steps": [
            {"title": "确认办理规则", "detail": "优先上传该场景的制度、通知或流程说明，用于问答和审核依据。", "deadline": None},
            {"title": "整理办理材料", "detail": "上传或粘贴当前办理材料，确保包含姓名、联系方式、事项名称等核心字段。", "deadline": None},
            {"title": "提取材料字段", "detail": "运行字段抽取，将材料转成结构化信息。", "deadline": None},
            {"title": "审核与补充", "detail": "根据缺失项和风险提示补充材料。", "deadline": None},
            {"title": "表单与待办", "detail": "生成表单草稿和下一步办理清单，并保存记录。", "deadline": None},
        ],
        "required_materials": ["制度/通知", "办理材料", "证明附件", "联系方式"],
        "risk_reminders": ["自定义场景建议先上传规则文件，否则审核只能基于通用字段完整性。"],
    }


def plan_workflow(request_text: str, scenario: str = "competition_registration") -> Dict[str, Any]:
    text = request_text or ""
    if any(word in text for word in ["思想政治理论课综合实践", "实践周志", "团队成员实践任务", "周次时间"]):
        return _social_practice_workflow()
    if scenario == "leave_approval" or "请假" in text:
        return _leave_workflow()
    if scenario == "competition_registration" or any(word in text for word in ["比赛", "报名", "参赛", "作品提交", "队伍人数"]):
        return _competition_workflow()
    return _generic_workflow(scenario)
