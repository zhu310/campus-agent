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
  prefill_sources?: Record<string, unknown>
  review_fields?: string[]
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

export interface DemoAsset {
  name: string
  type: string
  content: string
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
  model_runtime: Record<string, string | boolean>
}

export interface TaskDetail {
  id: number
  type: string
  title: string
  summary: string
  payload: Record<string, unknown>
  created_at: string
}
