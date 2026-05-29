// 前端与后端 API 对齐的数据类型定义。
export interface Citation {
  document_id: number
  filename: string
  chunk_id: string
  text: string
  score?: number
  rerank_score?: number
  location?: string
  highlight?: string
}

export interface TraceStep {
  title: string
  status: string
  detail: string
}

export interface AskResponse {
  intent?: string
  answer: string
  citations: Citation[]
  suggestions: string[]
  trace: TraceStep[]
  fallback_used: boolean
}

export interface OCRResponse {
  document_id?: number | null
  chunks_indexed?: number
  filename: string
  engine: string
  text: string
  extracted_fields: Record<string, string>
  raw_fields?: Record<string, unknown>[]
  field_matches?: Record<string, unknown>[]
  unmapped_fields?: Record<string, unknown>[]
  lines: string[]
  fallback_used: boolean
}

export interface AuditRuleHit {
  rule_name: string
  severity: string
  result: string
  field_name?: string | null
  suggestion: string
}

export interface AuditResponse {
  material_name: string
  recognized_fields: Record<string, string>
  raw_fields?: Record<string, unknown>[]
  field_matches?: Record<string, unknown>[]
  unmapped_fields?: Record<string, unknown>[]
  missing_items: string[]
  warnings: string[]
  passed: boolean
  conclusion: string
  level: string
  rule_hits: AuditRuleHit[]
  risk_items: string[]
  suggestions: string[]
  completeness_score: number
}

export interface FormFillResponse {
  fields: Record<string, string>
  template_name: string
  missing_fields: string[]
  quality?: Record<string, unknown>
  prefill_sources?: Record<string, unknown>
  review_fields?: string[]
  quality_warnings?: string[]
  raw_fields?: Record<string, unknown>[]
  field_matches?: Record<string, unknown>[]
  unmapped_fields?: Record<string, unknown>[]
}

export interface WorkflowStep {
  title: string
  detail: string
  deadline?: string | null
}

export interface WorkflowResponse {
  intent: string
  summary: string
  todos: string[]
  steps: WorkflowStep[]
  required_materials: string[]
  risk_reminders: string[]
  fallback_used?: boolean
}

export interface NoticeEvidence {
  document_id: number
  filename: string
  text: string
  location?: string | null
}

export interface NoticeTaskCard {
  title: string
  deadline?: string | null
  submit_method?: string | null
  required_materials: string[]
  steps: string[]
  risk_reminders: string[]
  evidence: NoticeEvidence[]
  status: string
}

export interface NoticeTaskResponse {
  summary: string
  tasks: NoticeTaskCard[]
  missing_information: string[]
  cross_document_risks: string[]
  fallback_used: boolean
}

export interface DraftSection {
  field_name: string
  draft: string
  basis: string
  needs_user_input: boolean
}

export interface FillAssistantResponse {
  required_information: string[]
  questions: string[]
  draft_sections: DraftSection[]
  risks: string[]
  evidence: NoticeEvidence[]
  fallback_used: boolean
}

export interface DashboardMetric {
  label: string
  value: string
  trend: string
}

export interface SummaryResponse {
  project_name: string
  documents_count: number
  ask_count: number
  audit_count: number
  form_count: number
  workflow_count: number
  highlight: string
  metrics: DashboardMetric[]
  business_value: string[]
  scenarios: string[]
  demo_mode: boolean
}

export interface HistoryItem {
  id?: number | null
  type: string
  title: string
  summary: string
  created_at: string
}

export interface DocumentItem {
  id: number
  filename: string
  source: string
  source_type: string
  scenario: string
  created_at: string
}

export interface DocumentDetail extends DocumentItem {
  content: string
  file_path?: string | null
}

export interface RulePolicyItem {
  id: number
  rule_name: string
  scenario: string
  field_name?: string | null
  operator: string
  expected_value?: string | null
  severity: string
  suggestion: string
}

export interface CapabilityItem {
  name: string
  status: string
  detail: string
}

export interface CapabilityResponse {
  required: CapabilityItem[]
  recommended: CapabilityItem[]
  extensions: CapabilityItem[]
  model_runtime: Record<string, unknown>
}

export interface TaskDetail {
  id: number
  type: string
  title: string
  summary: string
  payload: Record<string, unknown>
  created_at: string
}

export interface SessionEventItem {
  id: number
  event_type: string
  title: string
  payload: Record<string, unknown>
  created_at: string
}

export interface SessionItem {
  id: number
  name: string
  scenario: string
  summary: string
  document_ids: number[]
  created_at: string
  updated_at: string
}

export interface SessionDetail extends SessionItem {
  events: SessionEventItem[]
}

export interface MemoryItem {
  id: number
  key: string
  value: string
  category: string
  source: string
  confirmed: boolean
  created_at: string
  updated_at: string
}

export interface DataAnalysisColumn {
  name: string
  type: string
  non_null: number
  missing: number
  unique: number
}

export interface NumericSummary {
  column: string
  min: number | null
  max: number | null
  mean: number | null
  sum: number | null
}

export interface DataAnalysisBlock {
  key: string
  file_name: string
  sheet: string
  row_count: number
  column_count: number
  missing_cells: number
  missing_rate: number
  columns: DataAnalysisColumn[]
  numeric_summary: NumericSummary[]
  preview: Record<string, unknown>[]
}

export interface DataAnalysisResponse {
  session_id?: number
  task: string
  files: { file_name: string; blocks: number }[]
  block_count: number
  blocks: DataAnalysisBlock[]
  insights: string
  fallback_used: boolean
}

export interface DataAnalysisChatResponse {
  question: string
  answer: string
  fallback_used: boolean
}
