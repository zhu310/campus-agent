"""扩展能力接口。

提供本地模型运行状态、智能体图谱、训练数据导出和场景模板等高级演示能力。
"""

import json
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.config import settings

router = APIRouter(prefix="/extensions", tags=["extensions"])


@router.get("/model/check")
def check_model_runtime():
    return {
        "mode": "demo" if settings.DEMO_MODE else "real",
        "api_key_configured": bool(settings.OPENAI_API_KEY),
        "base_url": settings.OPENAI_BASE_URL,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "local_model_compatible": True,
        "checked_at": datetime.now().isoformat(),
        "suggestion": "如需本地国产模型，将 OPENAI_BASE_URL 指向本地 OpenAI-compatible 服务，并设置 LLM_MODEL。",
    }


@router.get("/agent-graph")
def get_agent_graph():
    return {
        "nodes": [
            {"id": "intent", "name": "Intent Agent", "role": "识别知识问答、材料审核、表单预填、流程规划、综合办理"},
            {"id": "rag", "name": "RAG Agent", "role": "检索制度/通知，生成带引用回答"},
            {"id": "audit", "name": "Audit Agent", "role": "OCR/文档解析、字段抽取、规则校验"},
            {"id": "form", "name": "Form Agent", "role": "将字段映射到报名/审批表"},
            {"id": "workflow", "name": "Workflow Agent", "role": "生成下一步办理清单、截止提醒、风险提示"},
            {"id": "record", "name": "Record Agent", "role": "保存问答、审核、表单、待办和工具调用留痕"},
            {"id": "supervisor", "name": "Supervisor Agent", "role": "串联主链路并处理降级策略"},
        ],
        "edges": [
            ["intent", "rag"],
            ["intent", "audit"],
            ["rag", "workflow"],
            ["audit", "form"],
            ["audit", "workflow"],
            ["form", "record"],
            ["workflow", "record"],
            ["supervisor", "intent"],
        ],
        "langgraph_ready": True,
        "note": "当前以轻量服务编排实现，多 Agent 节点边界已固定，可替换为 LangGraph StateGraph。",
    }


@router.get("/datasets/faq.jsonl", response_class=PlainTextResponse)
def export_faq_dataset():
    samples = [
        {"instruction": "单人能否参赛？", "output": "不能。通知要求每队 3-5 人，并确定 1 名队长。", "scenario": "competition_registration"},
        {"instruction": "报名截止时间是什么？", "output": "报名截止时间为 5 月 12 日 18:00。", "scenario": "competition_registration"},
        {"instruction": "作品提交截止时间是什么？", "output": "作品提交截止时间为 5 月 30 日。", "scenario": "competition_registration"},
        {"instruction": "请假审批需要哪些材料？", "output": "通常需要请假申请、请假原因说明和相应证明材料。", "scenario": "leave_approval"},
        {"instruction": "报销申请要核验哪些内容？", "output": "需要核验票据、金额、申请人、事项说明和审批附件。", "scenario": "reimbursement"},
    ]
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in samples)


@router.get("/datasets/ocr-fields.jsonl", response_class=PlainTextResponse)
def export_ocr_field_dataset():
    samples = [
        {"text": "姓名：张三\n联系方式：13800138000\n项目名称：智审通\n队伍人数：4", "fields": {"name": "张三", "phone": "13800138000", "project_name": "智审通", "team_size": "4"}},
        {"text": "作品标题 | Campus Copilot | 学院 | 计算机学院 | E-mail地址 | demo@example.com", "fields": {"project_name": "Campus Copilot", "college_class": "计算机学院", "email": "demo@example.com"}},
        {"text": "报销金额：1280.50\n票据类型：电子发票\n申请人：赵老师", "fields": {"amount": "1280.50", "invoice_type": "电子发票", "name": "赵老师"}},
    ]
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in samples)


@router.get("/datasets/rules.json", response_class=PlainTextResponse)
def export_rule_dataset():
    samples = {
        "competition_registration": [
            {"field": "team_size", "operator": "between", "expected": [3, 5], "severity": "high", "suggestion": "队伍人数需控制在 3-5 人。"},
            {"field": "email", "operator": "required", "severity": "high", "suggestion": "补充可接收通知的邮箱。"},
        ],
        "leave_approval": [
            {"field": "leave_reason", "operator": "required", "severity": "high", "suggestion": "补充请假原因。"},
            {"field": "proof", "operator": "recommended", "severity": "medium", "suggestion": "建议上传证明材料。"},
        ],
        "reimbursement": [
            {"field": "amount", "operator": "required", "severity": "high", "suggestion": "补充报销金额。"},
            {"field": "invoice", "operator": "required", "severity": "high", "suggestion": "上传发票或票据。"},
        ],
    }
    return json.dumps(samples, ensure_ascii=False, indent=2)


@router.get("/local-model-guide", response_class=PlainTextResponse)
def local_model_guide():
    return """# 国产模型本地部署适配说明

1. 启动本地 OpenAI-compatible 推理服务，例如 vLLM、Ollama OpenAI API、LMDeploy。
2. 在 backend/.env 中设置：

OPENAI_BASE_URL=http://127.0.0.1:8001/v1
OPENAI_API_KEY=local-key
LLM_MODEL=qwen2.5-7b-instruct
DEMO_MODE=false

3. 重启后端服务。
4. 打开“拓展选择 -> 检测模型配置”，确认 base_url 和模型名称已切换。

建议模型小于 70B，并优先选择 Qwen、DeepSeek、Baichuan、ChatGLM 等国产模型。
"""


@router.get("/scenario-templates")
def scenario_templates():
    return {
        "比赛报名": ["通知问答", "报名材料核验", "表单预填", "截止提醒"],
        "请假审批": ["制度咨询", "证明材料识别", "请假单预填", "审批待办"],
        "奖助学金申请": ["资格规则问答", "材料缺失识别", "申请表预填"],
        "报销办理": ["票据材料核验", "金额字段提取", "报销流程计划"],
        "社团活动审批": ["活动通知解析", "风险项审核", "流程清单生成"],
    }
