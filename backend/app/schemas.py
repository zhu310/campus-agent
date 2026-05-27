"""
API 的 Pydantic 请求和响应结构。
把接口契约集中在这里，方便同时查看后端路由入参、返回值以及前端需要消费的数据形状。
Pydantic 就是 Python 项目里负责“检查数据格式、转换数据类型、定义数据结构”的工具。
在项目里，它主要服务于 FastAPI：请求体、响应体、配置文件，都会用到它。
"""

"""
schemas.py 一般定义的是接口数据模型，也就是 API 收到什么、返回什么。
它关心请求体校验、响应格式、哪些字段允许客户端传、哪些字段应该隐藏、字段如何序列化等。
FastAPI 里通常用 Pydantic schema 来做这个。
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    chunks_indexed: int
    status: str = "indexed"


class DocumentItem(BaseModel):
    id: int
    filename: str
    source: str
    source_type: str
    scenario: str
    created_at: str


class DocumentDetail(DocumentItem):
    content: str
    file_path: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    scenario: str = "competition_registration"
    document_ids: List[int] = Field(default_factory=list)


class Citation(BaseModel):
    document_id: int
    filename: str
    chunk_id: str
    text: str
    score: Optional[float] = None
    rerank_score: Optional[float] = None
    location: Optional[str] = None
    highlight: Optional[str] = None


class TraceStep(BaseModel):
    title: str
    status: str
    detail: str


class AskResponse(BaseModel):
    intent: str = "knowledge_qa"
    answer: str
    citations: List[Citation]
    suggestions: List[str] = []
    trace: List[TraceStep] = []
    fallback_used: bool = False


class OCRResponse(BaseModel):
    filename: str
    engine: str
    text: str
    extracted_fields: Dict[str, Any]
    open_fields: Dict[str, Any] = Field(default_factory=dict)
    document_structure: Dict[str, Any] = Field(default_factory=dict)
    raw_fields: List[Dict[str, Any]] = Field(default_factory=list)
    field_matches: List[Dict[str, Any]] = Field(default_factory=list)
    unmapped_fields: List[Dict[str, Any]] = Field(default_factory=list)
    lines: List[str]
    fallback_used: bool = False


class AuditRequest(BaseModel):
    material_name: str
    text: str
    task_type: str = "competition_registration"
    scenario: str = "competition_registration"
    ocr_fields: Dict[str, Any] = Field(default_factory=dict)


class ExtractFieldsRequest(BaseModel):
    text: str
    scenario: str = "competition_registration"
    ocr_fields: Dict[str, Any] = Field(default_factory=dict)


class ExtractFieldsResponse(BaseModel):
    fields: Dict[str, Any]
    open_fields: Dict[str, Any] = Field(default_factory=dict)
    synonym_fields: Dict[str, Any] = Field(default_factory=dict)
    document_structure: Dict[str, Any] = Field(default_factory=dict)
    raw_fields: List[Dict[str, Any]] = Field(default_factory=list)
    field_matches: List[Dict[str, Any]] = Field(default_factory=list)
    unmapped_fields: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[str]
    scenario: str


class AuditRuleHit(BaseModel):
    rule_name: str
    severity: str
    result: str
    field_name: Optional[str] = None
    suggestion: str


class AuditResponse(BaseModel):
    material_name: str
    recognized_fields: Dict[str, Any]
    open_fields: Dict[str, Any] = Field(default_factory=dict)
    synonym_fields: Dict[str, Any] = Field(default_factory=dict)
    document_structure: Dict[str, Any] = Field(default_factory=dict)
    raw_fields: List[Dict[str, Any]] = Field(default_factory=list)
    field_matches: List[Dict[str, Any]] = Field(default_factory=list)
    unmapped_fields: List[Dict[str, Any]] = Field(default_factory=list)
    missing_items: List[str]
    warnings: List[str]
    passed: bool
    conclusion: str
    level: str
    rule_hits: List[AuditRuleHit]
    risk_items: List[str]
    suggestions: List[str]
    completeness_score: int
    extraction_confidence: float = 0
    needs_human_review: bool = False
    llm_fallback_used: bool = False


class FormFillRequest(BaseModel):
    text: str
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    scenario: str = "competition_registration"


class FormFillResponse(BaseModel):
    fields: Dict[str, Any]
    template_name: str
    missing_fields: List[str]
    source_structure: Dict[str, Any] = Field(default_factory=dict)
    prefill_tables: List[Dict[str, Any]] = Field(default_factory=list)
    open_fields: Dict[str, Any] = Field(default_factory=dict)
    prefill_sources: Dict[str, Any] = Field(default_factory=dict)
    review_fields: List[str] = Field(default_factory=list)
    raw_fields: List[Dict[str, Any]] = Field(default_factory=list)
    field_matches: List[Dict[str, Any]] = Field(default_factory=list)
    unmapped_fields: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewCreateRequest(BaseModel):
    task_id: Optional[int] = None
    material_name: str = "待复核材料"
    scenario: str = "other"
    original_payload: Dict[str, Any] = Field(default_factory=dict)
    corrected_fields: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class ReviewUpdateRequest(BaseModel):
    corrected_fields: Dict[str, Any] = Field(default_factory=dict)
    status: str = "reviewed"
    notes: str = ""


class ReviewResponse(BaseModel):
    id: int
    task_id: Optional[int] = None
    material_name: str
    scenario: str
    status: str
    original_payload: Dict[str, Any]
    corrected_fields: Dict[str, Any]
    notes: str
    created_at: str
    updated_at: str


class WorkflowRequest(BaseModel):
    request_text: str
    scenario: str = "competition_registration"
    document_ids: List[int] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    title: str
    detail: str
    deadline: Optional[str] = None


class WorkflowResponse(BaseModel):
    intent: str
    summary: str
    todos: List[str]
    steps: List[WorkflowStep]
    required_materials: List[str]
    risk_reminders: List[str]


class DashboardMetric(BaseModel):
    label: str
    value: str
    trend: str


class DashboardSummary(BaseModel):
    project_name: str
    documents_count: int
    ask_count: int
    audit_count: int
    form_count: int
    workflow_count: int
    highlight: str
    metrics: List[DashboardMetric]
    business_value: List[str]
    scenarios: List[str]
    demo_mode: bool


class HistoryItem(BaseModel):
    id: Optional[int] = None
    type: str
    title: str
    summary: str
    created_at: str


class TaskDetail(BaseModel):
    id: int
    type: str
    title: str
    summary: str
    payload: Dict[str, Any]
    created_at: str


class SaveRecordRequest(BaseModel):
    task_name: str = "综合办理"
    tool_name: str = "save_record"
    status: str = "completed"
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)


class RulePolicyItem(BaseModel):
    id: int
    rule_name: str
    scenario: str
    field_name: Optional[str]
    operator: str
    expected_value: Optional[str]
    severity: str
    suggestion: str


class DemoAsset(BaseModel):
    name: str
    type: str
    content: str


class AgentRunRequest(BaseModel):
    request_text: str = ""
    material_name: str = "当前材料"
    material_text: str = ""
    scenario: str = "competition_registration"
    document_ids: List[int] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    intent: str
    answer: Optional[AskResponse] = None
    fields: Dict[str, Any]
    audit: AuditResponse
    form: FormFillResponse
    workflow: WorkflowResponse
    trace: List[TraceStep]
