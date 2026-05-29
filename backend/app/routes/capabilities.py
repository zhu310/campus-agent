"""产品能力清单接口。

前端用这里的静态能力描述展示系统支持的场景、工具和演示亮点。
"""

from fastapi import APIRouter

from app.services.llm_service import model_runtime_status
from app.services.vector_service import vector_runtime_status

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("")
def get_capabilities():
    return {
        "required": [
            {"name": "Web 端业务工作台", "status": "completed", "detail": "Dashboard、三栏工作台、文件中心、结果分区和会话留痕已接入。"},
            {"name": "RAG 检索问答", "status": "completed", "detail": "支持 PDF/DOCX/TXT/MD 解析、切块、Qdrant 入库、混合召回和引用回答。"},
            {"name": "工具调用链路", "status": "completed", "detail": "search_knowledge、ocr_parse_file、extract_fields、validate_rules、prefill_form、generate_todo_plan、save_record 均有接口和 tool_logs 留痕。"},
            {"name": "大模型调用", "status": "completed", "detail": "兼容 OpenAI 风格国产模型 API，可使用 DeepSeek/Qwen/百炼/火山等提供方。"},
            {"name": "意图识别与路由", "status": "completed", "detail": "支持知识问答、材料审核、表单预填、流程规划、综合办理五类意图。"},
            {"name": "记录留痕", "status": "completed", "detail": "问答、审核、表单、待办和工具调用均写入数据库，可查看最近记录。"},
        ],
        "recommended": [
            {"name": "规则配置化", "status": "completed", "detail": "规则存储于 PostgreSQL rule_policies 表，按场景读取。"},
            {"name": "审核记录页", "status": "completed", "detail": "前端提供记录页，可查看问答、审核、表单、待办和工具日志。"},
            {"name": "证据引用高亮", "status": "completed", "detail": "RAG 结果返回 citations、highlight、score 与 rerank_score。"},
            {"name": "导出能力", "status": "completed", "detail": "支持审核摘要、表单结果和待办计划导出为 Markdown 文本。"},
        ],
        "extensions": [
            {"name": "多 Agent 编排", "status": "available", "detail": "以 Intent/RAG/Audit/Form/Workflow/Supervisor 的模块化服务实现轻量编排，保留 LangGraph 替换边界。"},
            {"name": "国产模型本地部署", "status": "available", "detail": "通过 OPENAI_BASE_URL/OPENAI_API_KEY/LLM_MODEL 切换本地 OpenAI-compatible 推理服务，模型可小于 70B。"},
            {"name": "数据制作与微调说明", "status": "available", "detail": "提供 FAQ、OCR 字段、规则样本三类数据集结构说明，可导入百炼/飞桨等平台。"},
            {"name": "多场景扩展", "status": "available", "detail": "请假、奖助学金、报销、社团活动复用同一文件-抽取-审核-表单-待办链路。"},
        ],
        "model_runtime": model_runtime_status()
        | {"local_model_hint": "将 OPENAI_BASE_URL 指向本地 vLLM/Ollama/百炼兼容服务即可切换本地国产模型。"},
        "vector_runtime": vector_runtime_status(),
    }
