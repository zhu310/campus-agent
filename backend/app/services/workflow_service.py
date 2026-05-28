"""流程规划服务。

根据场景返回稳定的办理步骤模板。具体截止时间、人数范围、提交邮箱等事实应来自
用户选中的制度/通知文件或规则配置，不在流程模板里写死。
"""

from typing import Any, Dict


def _competition_workflow() -> Dict[str, Any]:
    return {
        "intent": "workflow_plan",
        "summary": "系统识别为比赛报名办理场景，建议按确认规则、整理团队信息、补齐报名表、准备作品材料、按通知提交和留存记录推进。",
        "todos": ["确认参赛规则", "整理团队信息", "补齐报名表", "准备作品材料", "按通知提交", "保存办理记录"],
        "steps": [
            {"title": "确认参赛规则", "detail": "从选中的制度/通知中核对参赛对象、队伍人数、截止时间和提交方式。", "deadline": "按通知要求"},
            {"title": "整理团队信息", "detail": "整理负责人、成员、联系方式、邮箱、项目名称等报名所需字段。", "deadline": "提交前"},
            {"title": "补齐报名表", "detail": "根据字段抽取和规则审核结果补充缺失信息。", "deadline": "提交前"},
            {"title": "准备作品材料", "detail": "按通知要求准备作品说明、附件、演示材料或其他指定材料。", "deadline": "按通知要求"},
            {"title": "提交与留痕", "detail": "按通知指定渠道提交材料，并保存提交记录和系统审核结果。", "deadline": "按通知要求"},
        ],
        "required_materials": ["制度/通知", "报名表", "作品材料", "团队成员信息"],
        "risk_reminders": ["具体人数范围、截止时间和提交渠道必须以选中的制度/通知为准。", "提交前建议再次运行规则审核并人工确认关键字段。"],
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
    if scenario == "leave_approval":
        return _leave_workflow()
    if scenario == "competition_registration":
        return _competition_workflow()
    return _generic_workflow(scenario)
