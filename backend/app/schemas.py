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
    session_id: Optional[int] = None


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
    document_id: Optional[int] = None
    chunks_indexed: int = 0
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
    document_ids: List[int] = Field(default_factory=list)
    session_id: Optional[int] = None


class ExtractFieldsRequest(BaseModel):
    text: str
    scenario: str = "competition_registration"
    ocr_fields: Dict[str, Any] = Field(default_factory=dict)
    document_ids: List[int] = Field(default_factory=list)
    session_id: Optional[int] = None


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
    document_ids: List[int] = Field(default_factory=list)
    session_id: Optional[int] = None


class FormFillResponse(BaseModel):
    fields: Dict[str, Any]
    template_name: str
    missing_fields: List[str]
    quality: Dict[str, Any] = Field(default_factory=dict)
    source_structure: Dict[str, Any] = Field(default_factory=dict)
    prefill_tables: List[Dict[str, Any]] = Field(default_factory=list)
    open_fields: Dict[str, Any] = Field(default_factory=dict)
    prefill_sources: Dict[str, Any] = Field(default_factory=dict)
    review_fields: List[str] = Field(default_factory=list)
    quality_warnings: List[str] = Field(default_factory=list)
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
    session_id: Optional[int] = None


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
    fallback_used: bool = False


class NoticeTaskRequest(BaseModel):
    document_ids: List[int] = Field(default_factory=list)
    user_goal: str = "帮我整理这些通知需要做什么"
    scenario: str = "general"
    session_id: Optional[int] = None


class NoticeEvidence(BaseModel):
    document_id: int
    filename: str
    text: str
    location: Optional[str] = None


class NoticeTaskCard(BaseModel):
    title: str
    deadline: Optional[str] = None
    submit_method: Optional[str] = None
    required_materials: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    risk_reminders: List[str] = Field(default_factory=list)
    evidence: List[NoticeEvidence] = Field(default_factory=list)
    status: str = ""


class NoticeTaskResponse(BaseModel):
    summary: str
    tasks: List[NoticeTaskCard]
    missing_information: List[str] = Field(default_factory=list)
    cross_document_risks: List[str] = Field(default_factory=list)
    fallback_used: bool = False


class FillAssistantRequest(BaseModel):
    document_ids: List[int] = Field(default_factory=list)
    user_profile: str = ""
    form_text: str = ""
    draft_content: str = ""
    scenario: str = "general"
    session_id: Optional[int] = None


class DraftSection(BaseModel):
    field_name: str
    draft: str
    basis: str = ""
    needs_user_input: bool = False


class FillAssistantResponse(BaseModel):
    required_information: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)
    draft_sections: List[DraftSection] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    evidence: List[NoticeEvidence] = Field(default_factory=list)
    fallback_used: bool = False


class ModelProviderRequest(BaseModel):
    provider: str


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


class SessionCreateRequest(BaseModel):
    name: str = "新的办理会话"
    scenario: str = "general"
    document_ids: List[int] = Field(default_factory=list)


class SessionUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SessionEventCreateRequest(BaseModel):
    event_type: str
    title: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class SessionEventItem(BaseModel):
    id: int
    event_type: str
    title: str
    payload: Dict[str, Any]
    created_at: str


class SessionItem(BaseModel):
    id: int
    name: str
    scenario: str
    summary: str = ""
    document_ids: List[int] = Field(default_factory=list)
    created_at: str
    updated_at: str


class SessionDetail(SessionItem):
    events: List[SessionEventItem] = Field(default_factory=list)


class MemoryCreateRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    category: str = "profile"
    source: str = "user_confirmed"


class MemoryItem(BaseModel):
    id: int
    key: str
    value: str
    category: str
    source: str
    confirmed: bool
    created_at: str
    updated_at: str


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
