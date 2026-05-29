// 综合工作台页面：把上传、问答、材料审核、表单预填和流程规划串在一起。
import { useEffect, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import {
  Alert, Button, Card, Checkbox, Col, Descriptions, Divider, Empty, Input, List,
  message, Modal, Radio, Row, Space, Tabs, Tag, Timeline,
  Typography, Upload,
} from 'antd'
import {
  DeleteOutlined, FileSearchOutlined,
  FormOutlined, InboxOutlined, OrderedListOutlined, SearchOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import type { UploadRequestOption } from 'rc-upload/lib/interface'
import api from '../api'
import {
  AskResponse, AuditResponse, DocumentDetail, DocumentItem,
  FillAssistantResponse, FormFillResponse,
  NoticeTaskResponse, OCRResponse, SessionDetail, SessionItem, SummaryResponse, WorkflowResponse,
} from '../types'

const { TextArea } = Input
const { Title, Paragraph, Text } = Typography

const SCENARIOS = ['比赛报名', '请假审批', '奖助学金申请', '报销办理', '社团活动审批']

const SCENARIO_CODES: Record<string, string> = {
  比赛报名: 'competition_registration',
  请假审批: 'leave_approval',
  奖助学金申请: 'scholarship_application',
  报销办理: 'reimbursement',
  社团活动审批: 'club_activity',
}

function normalizeScenarioName(value: string) {
  return value === '其他场景' ? '自定义场景' : value
}

const SCENARIO_PRESETS: Record<string, { question: string; quickQuestions: string[]; uploadMode: UploadMode }> = {
  比赛报名: {
    question: '参赛对象是谁？',
    quickQuestions: ['单人能否参赛？', '报名截止时间是什么？', '作品提交到哪里？', '参赛对象是谁？'],
    uploadMode: 'knowledge_base',
  },
  请假审批: {
    question: '请假需要提交哪些证明材料？',
    quickQuestions: ['请假需要提交哪些证明材料？', '病假和事假流程有什么区别？', '请假单需要哪些字段？', '审批下一步怎么做？'],
    uploadMode: 'material',
  },
  奖助学金申请: {
    question: '奖助学金申请需要哪些材料？',
    quickQuestions: ['奖助学金申请需要哪些材料？', '成绩排名是否会影响资格？', '缺少困难认定表怎么办？', '申请表可以预填哪些字段？'],
    uploadMode: 'material',
  },
  报销办理: {
    question: '报销申请需要哪些票据？',
    quickQuestions: ['报销申请需要哪些票据？', '发票金额需要核验什么？', '缺少审批截图能否提交？', '报销流程下一步是什么？'],
    uploadMode: 'material',
  },
  社团活动审批: {
    question: '社团活动审批需要哪些材料？',
    quickQuestions: ['社团活动审批需要哪些材料？', '活动安全预案是否必需？', '预计人数会影响审批吗？', '活动流程清单怎么生成？'],
    uploadMode: 'material',
  },
}

const FIELD_LABELS: Record<string, string> = {
  material_type: '材料类型',
  name: '姓名/负责人',
  student_id: '学号',
  gender: '性别',
  birth_date: '出生年月',
  ethnicity: '民族',
  political_status: '政治面貌',
  enrollment_date: '入学时间',
  grade: '所在年级',
  id_number: '身份证号码',
  college_class: '学院/班级',
  school: '学校',
  student_level: '学生层次',
  phone: '联系方式',
  project_name: '项目/作品/实践题目',
  team_size: '队伍人数',
  advisor: '指导教师',
  professional_advisor: '专业指导教师',
  english_advisor: '英语指导教师',
  email: '邮箱',
  team_members: '团队成员',
  abstract: '摘要/内容',
  integrity_statement: '诚信承诺',
  awards: '曾获何种奖励',
  family_population: '家庭人口总数',
  family_income: '家庭月总收入',
  per_capita_income: '人均月收入',
  income_source: '收入来源',
  family_address: '家庭住址',
  postal_code: '邮政编码',
  poverty_level: '困难情况认定档次',
  grade_rank: '成绩排名',
  comprehensive_rank: '综合考评排名',
  application_reason: '申请理由',
}

type UploadMode = 'knowledge_base' | 'material' | 'both'
type CopilotMessageType = 'system' | 'user' | 'answer' | 'tasks' | 'fields' | 'audit' | 'form' | 'workflow' | 'fillAssist'

interface CopilotMessage {
  id: string
  type: CopilotMessageType
  title: string
  content?: string
  payload?: AskResponse | NoticeTaskResponse | FillAssistantResponse | AuditResponse | FormFillResponse | WorkflowResponse | Record<string, unknown>
  createdAt: string
}

interface WorkspacePageProps {
  initialScenario?: string
}

function emptyAnswer(): AskResponse {
  return { answer: '', citations: [], suggestions: [], trace: [], fallback_used: false }
}

function sourceTypeLabel(value: string) {
  if (value === 'knowledge_base') return '规则/表单模板'
  if (value === 'material') return '个人材料/填写草稿'
  if (value === 'both') return '模板+材料'
  return value
}

function orderedFieldEntries(fields: Record<string, unknown>) {
  const order = Object.keys(FIELD_LABELS)
  return Object.entries(fields).sort(([a], [b]) => {
    const left = order.indexOf(a)
    const right = order.indexOf(b)
    return (left === -1 ? 99 : left) - (right === -1 ? 99 : right)
  })
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const simple = value.every((item) => ['string', 'number', 'boolean'].includes(typeof item))
    return simple ? value.map(String).join('、') : JSON.stringify(value, null, 2).slice(0, 800)
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2).slice(0, 800)
  }
  return String(value)
}

function renderStructuredAnswer(text: string) {
  const normalized = (text || '').trim()
  if (!normalized) return <Paragraph>暂无回答</Paragraph>

  const parts = [
    { key: '结论', pattern: /(?:^|\n)\s*(?:\d+[.、]\s*)?\*{0,2}结论\*{0,2}\s*[:：]\s*([\s\S]*?)(?=\n?\s*(?:\d+[.、]\s*)?\*{0,2}(?:依据|建议动作)\*{0,2}\s*[:：]|$)/ },
    { key: '依据', pattern: /(?:^|\n)\s*(?:\d+[.、]\s*)?\*{0,2}依据\*{0,2}\s*[:：]\s*([\s\S]*?)(?=\n?\s*(?:\d+[.、]\s*)?\*{0,2}(?:结论|建议动作)\*{0,2}\s*[:：]|$)/ },
    { key: '建议动作', pattern: /(?:^|\n)\s*(?:\d+[.、]\s*)?\*{0,2}建议动作\*{0,2}\s*[:：]\s*([\s\S]*?)$/ },
  ].map((item) => ({ key: item.key, value: normalized.match(item.pattern)?.[1]?.trim() || '' }))

  if (parts.some((item) => item.value)) {
    return (
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        {parts.filter((item) => item.value).map((item) => (
          <Card key={item.key} size="small" title={item.key}>
            <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{item.value}</Paragraph>
          </Card>
        ))}
      </Space>
    )
  }

  return <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{normalized}</Paragraph>
}

function makeMessage(type: CopilotMessageType, title: string, content?: string, payload?: CopilotMessage['payload']): CopilotMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type,
    title,
    content,
    payload,
    createdAt: dayjs().format('HH:mm'),
  }
}

export default function WorkspacePage({ initialScenario = '比赛报名' }: WorkspacePageProps) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | null>(() => {
    const stored = window.localStorage.getItem('campus-active-session-id')
    return stored ? Number(stored) || null : null
  })
  const [scenario, setScenario] = useState(normalizeScenarioName(initialScenario))
  const [customScenario, setCustomScenario] = useState('')
  const [uploadMode, setUploadMode] = useState<UploadMode>('knowledge_base')
  const [uploadDisplayName, setUploadDisplayName] = useState('')
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<number[]>([])
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [question, setQuestion] = useState(SCENARIO_PRESETS[initialScenario]?.question || SCENARIO_PRESETS['比赛报名'].question)
  const [quickQuestions, setQuickQuestions] = useState(SCENARIO_PRESETS[initialScenario]?.quickQuestions || SCENARIO_PRESETS['比赛报名'].quickQuestions)
  const [materialText, setMaterialText] = useState('')
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [fieldResult, setFieldResult] = useState<Record<string, string>>({})
  const [ocrResult, setOcrResult] = useState<OCRResponse | null>(null)
  const [auditResult, setAuditResult] = useState<AuditResponse | null>(null)
  const [formResult, setFormResult] = useState<FormFillResponse | null>(null)
  const [workflowResult, setWorkflowResult] = useState<WorkflowResponse | null>(null)
  const [noticeTaskResult, setNoticeTaskResult] = useState<NoticeTaskResponse | null>(null)
  const [fillAssistantResult, setFillAssistantResult] = useState<FillAssistantResponse | null>(null)
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([
    makeMessage('system', 'Campus Copilot 已就绪', '先上传规则、通知或表单模板，再选择个人材料或粘贴填写草稿，就可以问答、审核和生成表单草稿。'),
  ])
  const [previewDocument, setPreviewDocument] = useState<DocumentDetail | null>(null)
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [activePanel, setActivePanel] = useState('preview')
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const streamRef = useRef<HTMLDivElement | null>(null)

  const scenarioCode = SCENARIO_CODES[scenario] || 'competition_registration'
  const knowledgeDocs = documents.filter((item) => item.source_type === 'knowledge_base' || item.source_type === 'both')
  const materialDocs = documents.filter((item) => item.source_type === 'material' || item.source_type === 'both')
  const selectedMaterial = materialDocs.find((item) => item.id === selectedMaterialId)
  const canPlanWorkflow = selectedKnowledgeIds.length > 0 || materialText.trim().length > 0 || !!auditResult

  const pushMessage = (messageItem: CopilotMessage) => {
    setCopilotMessages((items) => [...items, messageItem])
  }

  const stopControlEvent = (event?: MouseEvent<HTMLElement>) => {
    event?.preventDefault()
    event?.stopPropagation()
  }

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' })
  }, [copilotMessages.length])

  const loadAll = async () => {
    // 工作台启动时并行拉取摘要、文档和最近会话，减少首屏等待。
    const [s, d, sessionRes] = await Promise.all([
      api.get<SummaryResponse>('/dashboard/summary'),
      api.get<DocumentItem[]>('/documents'),
      api.get<SessionItem[]>('/sessions/recent'),
    ])
    setSummary(s.data)
    setDocuments(d.data)
    setSessions(sessionRes.data)
  }

  useEffect(() => {
    loadAll().catch(() => undefined)
  }, [])

  useEffect(() => {
    if (activeSessionId) {
      window.localStorage.setItem('campus-active-session-id', String(activeSessionId))
    }
  }, [activeSessionId])

  const ensureActiveSession = async () => {
    if (activeSessionId) return activeSessionId
    const res = await api.post<SessionItem>('/sessions', {
      name: '新建对话',
      scenario: scenarioCode,
      document_ids: selectedKnowledgeIds,
    })
    setActiveSessionId(res.data.id)
    setSessions((items) => [res.data, ...items.filter((item) => item.id !== res.data.id)])
    window.localStorage.setItem('campus-active-session-id', String(res.data.id))
    return res.data.id
  }

  const updateActiveSessionDocuments = async (documentIds = selectedKnowledgeIds) => {
    if (!activeSessionId) return
    await api.post(`/sessions/${activeSessionId}/events`, {
      event_type: 'context',
      title: '更新会话文件',
      payload: { document_ids: documentIds, scenario: scenarioCode },
    })
    await loadAll()
  }

  const startNewSession = async () => {
    const res = await api.post<SessionItem>('/sessions', {
      name: '新建对话',
      scenario: scenarioCode,
      document_ids: selectedKnowledgeIds,
    })
    setActiveSessionId(res.data.id)
    setSessions((items) => [res.data, ...items.filter((item) => item.id !== res.data.id)])
    setCopilotMessages([
      makeMessage('system', '已创建新的办理会话', '后续问答、办理流程、填写建议和审核结果会记录到这个会话中。'),
    ])
    setAnswer(null)
    setNoticeTaskResult(null)
    setFillAssistantResult(null)
    setActivePanel('preview')
    window.localStorage.setItem('campus-active-session-id', String(res.data.id))
    message.success('已新建对话')
  }

  const restoreSession = async (sessionId: number) => {
    const res = await api.get<SessionDetail>(`/sessions/${sessionId}`)
    const detail = res.data
    setActiveSessionId(detail.id)
    if (detail.document_ids.length) {
      setSelectedKnowledgeIds(detail.document_ids)
    }
    const restored: CopilotMessage[] = []
    detail.events.forEach((event) => {
      try {
        const payload = event.payload || {}
        if (event.event_type === 'answer') {
          const answerPayload = {
            answer: String(payload.answer || ''),
            citations: Array.isArray(payload.citations) ? payload.citations : [],
            suggestions: [],
            trace: Array.isArray(payload.trace) ? payload.trace : [],
            fallback_used: false,
          } as AskResponse
          restored.push(makeMessage('user', '我的问题', String(payload.question || event.title)))
          restored.push(makeMessage('answer', '历史回答', answerPayload.answer, answerPayload))
        }
        if (event.event_type === 'tasks') {
          const result = payload.result as NoticeTaskResponse | undefined
          if (result) restored.push(makeMessage('tasks', '历史办理流程', result.summary, result))
        }
        if (event.event_type === 'fields') {
          restored.push(makeMessage('fields', '历史信息抽取', '已恢复材料字段抽取结果。', payload))
        }
        if (event.event_type === 'audit') {
          const result = payload.result as AuditResponse | undefined
          if (result) restored.push(makeMessage('audit', '历史材料审核', result.conclusion, result))
        }
        if (event.event_type === 'form') {
          const result = payload.result as FormFillResponse | undefined
          if (result) restored.push(makeMessage('form', '历史表单预填', `仍需补充 ${result.missing_fields?.length || 0} 项字段。`, result))
        }
        if (event.event_type === 'workflow') {
          const result = payload.result as WorkflowResponse | undefined
          if (result) restored.push(makeMessage('workflow', '历史流程计划', result.summary, result))
        }
        if (event.event_type === 'fill_assist') {
          const result = payload.result as FillAssistantResponse | undefined
          if (result) restored.push(makeMessage('fillAssist', '历史补全建议', '已恢复填写建议。', result))
        }
      } catch {
        restored.push(makeMessage('system', '历史记录恢复异常', `已跳过一条无法展示的历史记录：${event.title}`))
      }
    })
    setCopilotMessages(restored.length ? restored : [
      makeMessage('system', '已恢复办理会话', '该会话暂无可展示的历史消息，后续操作会继续写入当前会话。'),
    ])
    message.success('已恢复会话')
  }

  const renameSession = async (event: MouseEvent<HTMLElement>, item: SessionItem) => {
    stopControlEvent(event)
    const nextName = window.prompt('请输入新的会话名称', item.name)
    if (!nextName?.trim() || nextName.trim() === item.name) return
    try {
      const res = await api.patch<SessionItem>(`/sessions/${item.id}`, { name: nextName.trim() })
      setSessions((items) => items.map((session) => session.id === item.id ? res.data : session))
      message.success('会话已重命名')
      await loadAll()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '会话重命名失败')
    }
  }

  const deleteSession = async (event: MouseEvent<HTMLElement> | undefined, sessionId: number) => {
    stopControlEvent(event)
    if (!window.confirm('确认删除该会话？')) return
    try {
      await api.delete(`/sessions/${sessionId}`)
      setSessions((items) => items.filter((item) => item.id !== sessionId))
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
        window.localStorage.removeItem('campus-active-session-id')
        setCopilotMessages([makeMessage('system', '已删除当前会话', '可以新建对话，或从最近任务中恢复其他会话。')])
      }
      message.success('会话已删除')
      await loadAll()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '会话删除失败')
    }
  }

  const applyScenarioPreset = (nextScenario: string) => {
    // 切换场景时同步替换问题、快捷问法和上传用途。
    const preset = SCENARIO_PRESETS[nextScenario] || SCENARIO_PRESETS['比赛报名']
    setScenario(nextScenario)
    setQuestion(preset.question)
    setQuickQuestions(preset.quickQuestions)
    setUploadMode(preset.uploadMode)
    setAnswer(null)
    setFieldResult({})
    setOcrResult(null)
    setAuditResult(null)
    setFormResult(null)
    setWorkflowResult(null)
    setNoticeTaskResult(null)
    setFillAssistantResult(null)
    setActivePanel('preview')
  }

  const applyCustomScenario = () => {
    const value = customScenario.trim()
    if (!value) {
      message.warning('请输入自定义场景名称')
      return
    }
    setScenario(value)
    setQuestion(`请根据当前文件说明“${value}”需要满足哪些要求？`)
    setQuickQuestions([
      `${value}需要提交哪些材料？`,
      `${value}有哪些缺失风险？`,
      `${value}表单可以预填哪些字段？`,
      `${value}下一步怎么做？`,
    ])
    setUploadMode('both')
    setAnswer(null)
    setFieldResult({})
    setOcrResult(null)
      setAuditResult(null)
      setFormResult(null)
      setWorkflowResult(null)
      setNoticeTaskResult(null)
      setFillAssistantResult(null)
    setActivePanel('preview')
  }

  useEffect(() => {
    const normalized = normalizeScenarioName(initialScenario)
    if (SCENARIO_PRESETS[normalized]) {
      applyScenarioPreset(normalized)
    } else {
      setScenario(normalized)
      setCustomScenario(normalized === '自定义场景' ? '' : normalized)
      setQuestion(`请根据当前文件说明“${normalized}”需要满足哪些要求？`)
      setQuickQuestions([
        `${normalized}需要提交哪些材料？`,
        `${normalized}有哪些缺失风险？`,
        `${normalized}表单可以预填哪些字段？`,
        `${normalized}下一步怎么做？`,
      ])
      setUploadMode('both')
    }
  }, [initialScenario])

  const previewFile = async (id: number) => {
    const res = await api.get<DocumentDetail>(`/documents/${id}`)
    setPreviewDocument(res.data)
    setActivePanel('preview')
  }

  const loadMaterial = async (id: number) => {
    if (selectedMaterialId === id) {
      clearSelectedMaterial()
      return
    }
    setSelectedMaterialId(id)
    const res = await api.get<DocumentDetail>(`/documents/${id}`)
    setPreviewDocument(res.data)
    setMaterialText(res.data.content || '')
    setActivePanel('preview')
  }

  const clearSelectedKnowledge = () => {
    setSelectedKnowledgeIds([])
    updateActiveSessionDocuments([]).catch(() => undefined)
  }

  const clearSelectedMaterial = () => {
    setSelectedMaterialId(null)
    if (previewDocument?.source_type === 'material') {
      setPreviewDocument(null)
    }
    setMaterialText('')
  }

  const deleteDocument = async (id: number) => {
    await api.delete(`/documents/${id}`)
    setSelectedKnowledgeIds((ids) => ids.filter((item) => item !== id))
    if (selectedMaterialId === id) setSelectedMaterialId(null)
    if (previewDocument?.id === id) setPreviewDocument(null)
    message.success('文件已删除')
    await loadAll()
  }

  const previewDocumentFile = async (event: MouseEvent<HTMLElement>, id: number) => {
    stopControlEvent(event)
    try {
      const res = await api.get<DocumentDetail>(`/documents/${id}`)
      setPreviewDocument(res.data)
      setPreviewModalOpen(true)
      setActivePanel('preview')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '文件查看失败')
    }
  }

  const confirmDeleteDocument = async (event: MouseEvent<HTMLElement> | undefined, id: number) => {
    stopControlEvent(event)
    if (!window.confirm('确认删除该文件？')) return
    try {
      await deleteDocument(id)
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '文件删除失败')
    }
  }

  const handleUpload = async (options: UploadRequestOption) => {
    // 图片类材料走 OCR，文本/文档类材料走后端文档解析和可选知识库索引。
    const file = options.file as File
    const suffix = file.name.split('.').pop()?.toLowerCase() || ''
    const isImage = ['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(suffix)
    const shouldUseMaterialParser = isImage || (suffix === 'pdf' && uploadMode === 'material')
    if (suffix === 'doc') {
      message.error('暂不支持 .doc 老 Word 格式，请另存为 .docx、PDF 或 txt 后上传。')
      options.onError?.(new Error('Unsupported .doc file'))
      return
    }
    const form = new FormData()
    form.append('file', file)
    form.append('scenario', scenarioCode)
    if (uploadDisplayName.trim()) {
      form.append('display_name', uploadDisplayName.trim())
    }
    setLoadingAction('upload')
    try {
      if (shouldUseMaterialParser) {
        const res = await api.post<OCRResponse>('/audit/upload', form)
        setOcrResult(res.data)
        setMaterialText(res.data.text)
        setFieldResult(res.data.extracted_fields || {})
        if (res.data.document_id) {
          const detail = await api.get<DocumentDetail>(`/documents/${res.data.document_id}`)
          setPreviewDocument(detail.data)
          setSelectedMaterialId(res.data.document_id)
        }
        setActivePanel('fields')
      } else {
        form.append('source_type', uploadMode)
        const res = await api.post('/documents/upload', form)
        const id = res.data.document_id as number
        const detail = await api.get<DocumentDetail>(`/documents/${id}`)
        setPreviewDocument(detail.data)
        if (uploadMode === 'knowledge_base' || uploadMode === 'both') {
          const nextIds = Array.from(new Set([...selectedKnowledgeIds, id]))
          setSelectedKnowledgeIds(nextIds)
          await updateActiveSessionDocuments(nextIds)
        }
        if (uploadMode === 'material' || uploadMode === 'both') {
          setSelectedMaterialId(id)
          setMaterialText(detail.data.content || '')
        }
      }
      message.success(`${file.name} 上传成功`)
      setUploadDisplayName('')
      await loadAll()
      options.onSuccess?.({}, new XMLHttpRequest())
    } catch (error: any) {
      message.error(error?.response?.data?.detail || `${file.name} 上传失败`)
      options.onError?.(error)
    } finally {
      setLoadingAction(null)
    }
  }

  const askQuestion = async (clearInputOnSuccess = true) => {
    if (!selectedKnowledgeIds.length) {
      message.warning('请先在左侧勾选用于问答的规则/表单模板')
      return emptyAnswer()
    }
    const currentQuestion = question.trim()
    if (!currentQuestion) {
      message.warning('请输入问题')
      return emptyAnswer()
    }
    setLoadingAction('ask')
    try {
      const sessionId = await ensureActiveSession()
      const res = await api.post<AskResponse>('/chat/query', {
        question: currentQuestion,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
        session_id: sessionId,
      })
      setAnswer(res.data)
      pushMessage(makeMessage('user', '我的问题', currentQuestion))
      pushMessage(makeMessage('answer', '基于选中文件的回答', res.data.answer, res.data))
      if (clearInputOnSuccess) setQuestion('')
      await loadAll()
      return res.data
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '请求失败，请检查后端服务、模型配置或文件索引状态。'
      message.error(detail)
      pushMessage(makeMessage('system', '发送失败', detail))
      return emptyAnswer()
    } finally {
      setLoadingAction(null)
    }
  }

  const askPresetQuestion = async (presetQuestion: string) => {
    if (!selectedKnowledgeIds.length) {
      message.warning('请先在左侧勾选用于问答的规则/表单模板')
      return emptyAnswer()
    }
    setQuestion(presetQuestion)
    setLoadingAction('ask')
    try {
      const sessionId = await ensureActiveSession()
      const res = await api.post<AskResponse>('/chat/query', {
        question: presetQuestion,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
        session_id: sessionId,
      })
      setAnswer(res.data)
      pushMessage(makeMessage('user', '我的问题', presetQuestion))
      pushMessage(makeMessage('answer', '基于选中文件的回答', res.data.answer, res.data))
      setQuestion('')
      await loadAll()
      return res.data
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '请求失败，请检查后端服务、模型配置或文件索引状态。'
      message.error(detail)
      pushMessage(makeMessage('system', '发送失败', detail))
      return emptyAnswer()
    } finally {
      setLoadingAction(null)
    }
  }

  const identifyFields = async () => {
    setLoadingAction('fields')
    try {
      const sessionId = await ensureActiveSession()
      const res = await api.post('/audit/extract-fields', {
        text: materialText,
        scenario: scenarioCode,
        ocr_fields: ocrResult?.extracted_fields || {},
        document_ids: selectedKnowledgeIds,
        session_id: sessionId,
      })
      setFieldResult(res.data.fields || {})
      setActivePanel('fields')
      pushMessage(makeMessage('fields', '信息抽取', '已从当前材料文本中抽取字段。', res.data))
      await loadAll()
      return res.data.fields || {}
    } finally {
      setLoadingAction(null)
    }
  }

  const auditMaterial = async (options: { keepLoading?: boolean; quiet?: boolean } = {}) => {
    // 审核前确保已有结构化字段；如果用户没手动提取，就先自动提取一次。
    if (!options.keepLoading) setLoadingAction('audit')
    try {
      const fields = Object.keys(fieldResult).length ? fieldResult : await identifyFields()
      const res = await api.post<AuditResponse>('/audit/run', {
        material_name: selectedMaterial?.filename || '当前材料文本',
        text: materialText,
        task_type: scenarioCode,
        scenario: scenarioCode,
        ocr_fields: fields,
        document_ids: selectedKnowledgeIds,
        session_id: await ensureActiveSession(),
      })
      setAuditResult(res.data)
      setFieldResult(res.data.recognized_fields || fields)
      setActivePanel('audit')
      if (!options.quiet) pushMessage(makeMessage('audit', '当前内容审核', res.data.conclusion, res.data))
      await loadAll()
      return res.data
    } finally {
      if (!options.keepLoading) setLoadingAction(null)
    }
  }

  const prefillForm = async () => {
    setLoadingAction('form')
    try {
      const fields = Object.keys(fieldResult).length ? fieldResult : await identifyFields()
      const res = await api.post<FormFillResponse>('/forms/prefill', {
        text: materialText,
        extracted_fields: fields,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
        session_id: await ensureActiveSession(),
      })
      setFormResult(res.data)
      setActivePanel('form')
      pushMessage(makeMessage('form', '表单预填', `仍需补充 ${res.data.missing_fields.length} 项字段。`, res.data))
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const generateWorkflow = async () => {
    if (!canPlanWorkflow) {
      message.warning('请先选择规则/表单模板，或上传/粘贴一份个人材料')
      return null
    }
    setLoadingAction('workflow')
    try {
      const sessionId = await ensureActiveSession()
      // 把审核结论和材料正文拼进流程规划请求，让下一步建议更贴近当前材料状态。
      const auditContext = auditResult
        ? `\n审核结论：${auditResult.level}\n缺失项：${auditResult.missing_items.join('、') || '无'}\n审核建议：${auditResult.suggestions.join('、') || auditResult.conclusion}`
        : ''
      const materialContext = materialText.trim() ? `\n当前材料内容：\n${materialText.slice(0, 8000)}` : ''
      const res = await api.post<WorkflowResponse>('/workflow/plan', {
        request_text: `${question}${auditContext}${materialContext}`,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
        session_id: sessionId,
      })
      setWorkflowResult(res.data)
      setActivePanel('workflow')
      pushMessage(makeMessage('workflow', '流程计划', res.data.summary, res.data))
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const generateNoticeTasks = async () => {
    if (!selectedKnowledgeIds.length) {
      message.warning('请先勾选需要阅读的通知、制度或说明文件')
      return null
    }
    setLoadingAction('noticeTasks')
    try {
      const sessionId = await ensureActiveSession()
      const res = await api.post<NoticeTaskResponse>('/workflow/notice-tasks', {
        document_ids: selectedKnowledgeIds,
        user_goal: question || '帮我整理这些通知需要做什么',
        scenario: scenarioCode,
        session_id: sessionId,
      })
      setNoticeTaskResult(res.data)
      pushMessage(makeMessage('tasks', '完整办理流程', res.data.summary, res.data))
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const generateFillAssistant = async (options: { keepLoading?: boolean; quiet?: boolean } = {}) => {
    if (!options.keepLoading) setLoadingAction('fillAssist')
    try {
      const sessionId = await ensureActiveSession()
      const res = await api.post<FillAssistantResponse>('/forms/assist', {
        document_ids: selectedKnowledgeIds,
        user_profile: materialText,
        form_text: previewDocument?.content || '',
        draft_content: '',
        scenario: scenarioCode,
        session_id: sessionId,
      })
      setFillAssistantResult(res.data)
      if (!options.quiet) pushMessage(makeMessage('fillAssist', '补全填写建议', '已根据选中文件和你提供的信息生成追问与草稿建议。', res.data))
      await loadAll()
      return res.data
    } finally {
      if (!options.keepLoading) setLoadingAction(null)
    }
  }

  const auditAndAssist = async () => {
    setLoadingAction('auditAssist')
    try {
      const audit = await auditMaterial({ keepLoading: true, quiet: true })
      const assist = await generateFillAssistant({ keepLoading: true, quiet: true })
      pushMessage(makeMessage('audit', '审核并补全', audit?.conclusion || '已完成当前内容审核。', audit || {}))
      pushMessage(makeMessage('fillAssist', '补全填写建议', '已根据审核结果生成追问与草稿建议。', assist || {}))
      setActivePanel('audit')
      await loadAll()
      return { audit, assist }
    } finally {
      setLoadingAction(null)
    }
  }

  const runFullChain = async () => {
    // 完整闭环按依赖顺序执行：问答可选，字段识别、审核、预填、规划依次推进。
    setLoadingAction('full')
    try {
      if (selectedKnowledgeIds.length) await askQuestion(false)
      await identifyFields()
      await auditAndAssist()
      await prefillForm()
      await generateWorkflow()
      setActivePanel('workflow')
    } finally {
      setLoadingAction(null)
    }
  }

  const resultTabs = [
    {
      key: 'preview',
      label: '文件预览',
      children: previewDocument ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            <Text strong>{previewDocument.filename}</Text>
            <Tag>{sourceTypeLabel(previewDocument.source_type)}</Tag>
            <Tag>{previewDocument.scenario}</Tag>
          </Space>
          <pre className="document-preview">{previewDocument.content || '暂无可预览文本'}</pre>
        </Space>
      ) : <Empty description="在左侧点击“查看”可预览制度、通知或材料内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'rag',
      label: '问答依据',
      children: answer ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {renderStructuredAnswer(answer.answer)}
          <List size="small" dataSource={answer.citations || []} locale={{ emptyText: '暂无引用依据' }} renderItem={(item) => (
            <List.Item>
              <div>
                <Space><Text strong>{item.filename}</Text>{item.location ? <Tag>{item.location}</Tag> : null}</Space>
                <Paragraph className="citation-text">{item.highlight || item.text}</Paragraph>
                <Text type="secondary">向量 {item.score?.toFixed(3)} / rerank {item.rerank_score?.toFixed(3)}</Text>
              </div>
            </List.Item>
          )} />
        </Space>
      ) : <Empty description="提问后这里只展示答案和引用依据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'fields',
      label: '信息抽取',
      children: Object.keys(fieldResult).length ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type="info" showIcon message="这里展示从当前材料文本中抽取出的字段，用于后续审核和表单草稿生成。" />
          <Descriptions size="small" column={1} bordered>
            {orderedFieldEntries(fieldResult).map(([key, value]) => (
              <Descriptions.Item key={key} label={FIELD_LABELS[key] || key}>{displayValue(value)}</Descriptions.Item>
            ))}
          </Descriptions>
        </Space>
      ) : <Empty description="上传材料或点击“提取材料信息”后显示结构化字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'tasks',
      label: '办理流程',
      children: noticeTaskResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type={noticeTaskResult.fallback_used ? 'warning' : 'success'} showIcon message={noticeTaskResult.summary} />
          <List size="small" dataSource={noticeTaskResult.tasks} locale={{ emptyText: '暂无办理流程' }} renderItem={(item) => (
            <List.Item>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap><Text strong>{item.title}</Text>{item.deadline ? <Tag color="gold">{item.deadline}</Tag> : null}</Space>
                {item.submit_method ? <Text>提交方式：{item.submit_method}</Text> : null}
                <List size="small" header="材料清单" dataSource={item.required_materials} locale={{ emptyText: '未从原文识别到明确材料清单' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
                <List size="small" header="步骤" dataSource={item.steps} locale={{ emptyText: '暂无步骤' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
                <List size="small" header="依据" dataSource={item.evidence} locale={{ emptyText: '暂无依据' }} renderItem={(ev) => <List.Item><div><Text strong>{ev.filename}</Text><Paragraph className="citation-text">{ev.text}</Paragraph></div></List.Item>} />
              </Space>
            </List.Item>
          )} />
          <List size="small" header="仍需确认" dataSource={noticeTaskResult.missing_information} locale={{ emptyText: '暂无需确认项' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
          <List size="small" header="跨文件风险" dataSource={noticeTaskResult.cross_document_risks} locale={{ emptyText: '暂无跨文件风险' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="点击“生成办理清单”后，这里会把规则或通知拆成完整可执行步骤" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'fillAssist',
      label: '补全建议',
      children: fillAssistantResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type={fillAssistantResult.fallback_used ? 'warning' : 'info'} showIcon message="系统先判断需要补充的信息，再生成可复制草稿。" />
          <List size="small" header="需要你补充的信息" dataSource={fillAssistantResult.required_information} locale={{ emptyText: '暂无缺失信息' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
          <List size="small" header="追问" dataSource={fillAssistantResult.questions} locale={{ emptyText: '暂无追问' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
          <List size="small" header="可复制草稿" dataSource={fillAssistantResult.draft_sections} locale={{ emptyText: '信息不足，暂未生成草稿' }} renderItem={(item) => (
            <List.Item>
              <div>
                <Space><Text strong>{item.field_name}</Text>{item.needs_user_input ? <Tag color="orange">需补充</Tag> : <Tag color="green">可用</Tag>}</Space>
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{item.draft}</Paragraph>
                {item.basis ? <Text type="secondary">依据：{item.basis}</Text> : null}
              </div>
            </List.Item>
          )} />
          <List size="small" header="风险提醒" dataSource={fillAssistantResult.risks} locale={{ emptyText: '暂无风险' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="点击“审核并补全”后，这里会显示缺失信息、追问和可复制草稿" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'audit',
      label: '审核',
      children: auditResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space>
            <Tag color={auditResult.passed ? 'green' : auditResult.level === '待补充' ? 'orange' : 'red'}>{auditResult.level}</Tag>
            <Tag>完整度 {auditResult.completeness_score}</Tag>
          </Space>
          <Paragraph>{auditResult.conclusion}</Paragraph>
          <List size="small" header="缺失项" dataSource={auditResult.missing_items} locale={{ emptyText: '暂无缺失项' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
          <List size="small" header="命中规则与建议" dataSource={auditResult.rule_hits} renderItem={(item) => (
            <List.Item><div><Text strong>{item.rule_name}</Text><div><Text type="secondary">{item.result} / {item.suggestion}</Text></div></div></List.Item>
          )} />
        </Space>
      ) : <Empty description="点击“审核并补全”后，这里展示基于当前材料文本的审核结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'form',
      label: '表单草稿',
      children: formResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {formResult.quality_warnings?.map((item) => <Alert key={item} type="warning" showIcon message={item} />)}
          {formResult.quality ? (
            <Space wrap>
              <Tag>字段 {String(formResult.quality.field_count ?? 0)}</Tag>
              <Tag color="green">已填 {String(formResult.quality.filled_count ?? 0)}</Tag>
              <Tag color="orange">待补 {String(formResult.quality.missing_count ?? 0)}</Tag>
              {formResult.quality.needs_human_review ? <Tag color="red">建议复核</Tag> : <Tag color="blue">可信度较高</Tag>}
            </Space>
          ) : null}
          <Descriptions size="small" column={1} bordered>
            {Object.entries(formResult.fields).map(([key, value]) => <Descriptions.Item key={key} label={key}>{displayValue(value)}</Descriptions.Item>)}
          </Descriptions>
          <List size="small" header="仍需补充字段" dataSource={formResult.missing_fields} locale={{ emptyText: '表单字段已较完整' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="点击“生成表单草稿”后，这里展示可写入表单的结构化结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'workflow',
      label: '下一步',
      children: workflowResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type={workflowResult.fallback_used ? 'warning' : 'success'} showIcon message={workflowResult.summary} />
          <Timeline items={workflowResult.steps.map((item) => ({ children: <div><Text strong>{item.title}</Text><div>{item.detail}</div>{item.deadline ? <Tag color="gold">{item.deadline}</Tag> : null}</div> }))} />
          <List size="small" header="风险提醒" dataSource={workflowResult.risk_reminders} locale={{ emptyText: '暂无风险提醒' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="完整闭环执行后，这里会按当前材料和选中文件生成下一步建议" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
  ]

  const renderCopilotMessage = (item: CopilotMessage) => {
    if (item.type === 'tasks') {
      const data = item.payload as NoticeTaskResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Alert type={data.fallback_used ? 'warning' : 'success'} showIcon message={data.summary} />
          <List size="small" dataSource={data.tasks} renderItem={(task) => (
            <List.Item>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap><Text strong>{task.title}</Text>{task.deadline ? <Tag color="gold">{task.deadline}</Tag> : null}</Space>
                {task.submit_method ? <Text>提交方式：{task.submit_method}</Text> : null}
                {task.required_materials.length ? <Text>材料：{task.required_materials.join('；')}</Text> : null}
                {task.steps.length ? <Text>步骤：{task.steps.join(' -> ')}</Text> : null}
                {task.evidence[0] ? <Paragraph className="citation-text">依据：{task.evidence[0].text}</Paragraph> : null}
              </Space>
            </List.Item>
          )} />
        </Space>
      )
    }
    if (item.type === 'fillAssist') {
      const data = item.payload as FillAssistantResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <List size="small" header="需要补充的信息" dataSource={data.required_information} locale={{ emptyText: '暂无缺失信息' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
          <List size="small" header="追问" dataSource={data.questions} locale={{ emptyText: '暂无追问' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
          <List size="small" header="可复制草稿" dataSource={data.draft_sections} locale={{ emptyText: '信息不足，暂未生成草稿' }} renderItem={(section) => (
            <List.Item>
              <div>
                <Text strong>{section.field_name}</Text>
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{section.draft}</Paragraph>
                {section.basis ? <Text type="secondary">依据：{section.basis}</Text> : null}
              </div>
            </List.Item>
          )} />
        </Space>
      )
    }
    if (item.type === 'fields') {
      const data = item.payload as { fields?: Record<string, string>; missing_fields?: string[] }
      const fields = data.fields || {}
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Descriptions size="small" column={1} bordered>
            {orderedFieldEntries(fields).map(([key, value]) => (
              <Descriptions.Item key={key} label={FIELD_LABELS[key] || key}>{displayValue(value)}</Descriptions.Item>
            ))}
          </Descriptions>
          <List size="small" header="仍缺字段" dataSource={data.missing_fields || []} locale={{ emptyText: '暂无缺失字段' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
        </Space>
      )
    }
    if (item.type === 'audit') {
      const data = item.payload as AuditResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Alert type={data.passed ? 'success' : 'warning'} showIcon message={data.conclusion} />
          <Space><Tag>{data.level}</Tag><Tag>完整度 {data.completeness_score}</Tag></Space>
          <List size="small" header="缺失项" dataSource={data.missing_items || []} locale={{ emptyText: '暂无缺失项' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
          <List size="small" header="建议" dataSource={data.suggestions || []} locale={{ emptyText: '暂无建议' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
        </Space>
      )
    }
    if (item.type === 'form') {
      const data = item.payload as FormFillResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Descriptions size="small" column={1} bordered>
            {Object.entries(data.fields || {}).map(([key, value]) => <Descriptions.Item key={key} label={key}>{displayValue(value)}</Descriptions.Item>)}
          </Descriptions>
          <List size="small" header="仍需补充字段" dataSource={data.missing_fields || []} locale={{ emptyText: '表单字段已较完整' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
        </Space>
      )
    }
    if (item.type === 'workflow') {
      const data = item.payload as WorkflowResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Alert type="success" showIcon message={data.summary} />
          <Timeline items={(data.steps || []).map((step) => ({ children: <div><Text strong>{step.title}</Text><div>{step.detail}</div>{step.deadline ? <Tag color="gold">{step.deadline}</Tag> : null}</div> }))} />
          <List size="small" header="风险提醒" dataSource={data.risk_reminders || []} locale={{ emptyText: '暂无风险提醒' }} renderItem={(value) => <List.Item>{value}</List.Item>} />
        </Space>
      )
    }
    if (item.type === 'answer') {
      const data = item.payload as AskResponse
      return (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          {renderStructuredAnswer(item.content || '')}
          <List size="small" header="引用依据" dataSource={data.citations || []} locale={{ emptyText: '暂无引用依据' }} renderItem={(citation) => (
            <List.Item><div><Text strong>{citation.filename}</Text><Paragraph className="citation-text">{citation.highlight || citation.text}</Paragraph></div></List.Item>
          )} />
        </Space>
      )
    }
    return <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{item.content}</Paragraph>
  }

  return (
    <div className="workspace-page-shell">
      <Modal
        title={previewDocument?.filename || '文件内容'}
        open={previewModalOpen}
        width={900}
        footer={null}
        onCancel={() => setPreviewModalOpen(false)}
      >
        {previewDocument ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space wrap>
              <Tag>{sourceTypeLabel(previewDocument.source_type)}</Tag>
              <Tag>{previewDocument.scenario}</Tag>
            </Space>
            <pre className="document-preview">{previewDocument.content || '暂无可预览文本。若原文件是图片或扫描件，说明 OCR/解析未提取到可用文字。'}</pre>
          </Space>
        ) : null}
      </Modal>
      <section className="compact-hero">
        <div>
          <Space wrap align="center">
            <Title level={2} className="compact-title">智审通 Campus Copilot</Title>
            <Tag color="cyan">高校智能办理平台</Tag>
            <Tag color={summary?.demo_mode ? 'orange' : 'green'}>{summary?.demo_mode ? '演示降级模式' : '真实模型模式'}</Tag>
          </Space>
          <Paragraph className="compact-desc">上传复杂通知，生成带依据的问答、办理流程、填写建议和审核结果。</Paragraph>
        </div>
      </section>

      <Row gutter={[16, 16]} align="stretch" className="workspace-grid">
        <Col xs={24} xl={6} className="workspace-col">
          <Card title="文件中心" className="workspace-card fixed-panel file-center-panel" bordered={false}>
            <div className="panel-scroll">
              <Radio.Group value={uploadMode} onChange={(event) => setUploadMode(event.target.value)} optionType="button" buttonStyle="solid" className="upload-mode">
                <Radio.Button value="knowledge_base">规则/模板</Radio.Button>
                <Radio.Button value="material">个人材料</Radio.Button>
                <Radio.Button value="both">两者都是</Radio.Button>
              </Radio.Group>
              <Input
                value={uploadDisplayName}
                onChange={(event) => setUploadDisplayName(event.target.value)}
                placeholder="文件显示名称，如：奖学金申请表模板"
                style={{ marginBottom: 10 }}
              />
              <Upload.Dragger className="compact-uploader" customRequest={handleUpload} showUploadList={false} accept=".png,.jpg,.jpeg,.bmp,.webp,.pdf,.docx,.txt,.md,.doc">
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">上传{sourceTypeLabel(uploadMode)}</p>
                <p className="ant-upload-hint">表格模板和填表说明放到规则/模板；个人信息、证明材料和草稿放到个人材料</p>
              </Upload.Dragger>
              <Divider />
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Title level={5} style={{ marginBottom: 0 }}>规则/表单模板</Title>
                <Button size="small" type="text" disabled={!selectedKnowledgeIds.length} onClick={clearSelectedKnowledge}>清空</Button>
              </Space>
              <Checkbox.Group
                value={selectedKnowledgeIds}
                onChange={(values) => {
                  const nextIds = values as number[]
                  setSelectedKnowledgeIds(nextIds)
                  updateActiveSessionDocuments(nextIds).catch(() => undefined)
                }}
                style={{ width: '100%' }}
              >
                <List size="small" dataSource={knowledgeDocs} locale={{ emptyText: <Empty description="暂无规则、通知或表单模板" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} renderItem={(item) => (
                  <List.Item className="file-management-row">
                    <Checkbox value={item.id} className="file-row-main"><Text>{item.filename}</Text></Checkbox>
                    <Space size={4} onMouseDown={stopControlEvent} onClick={stopControlEvent}>
                      <Button size="small" type="text" onMouseDown={stopControlEvent} onClick={(event) => previewDocumentFile(event, item.id)}>查看</Button>
                      <Button danger size="small" type="text" icon={<DeleteOutlined />} onMouseDown={stopControlEvent} onClick={(event) => confirmDeleteDocument(event, item.id)} />
                    </Space>
                  </List.Item>
                )} />
              </Checkbox.Group>

              <Divider />
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Title level={5} style={{ marginBottom: 0 }}>个人材料/填写草稿</Title>
                <Button size="small" type="text" disabled={!selectedMaterialId} onClick={clearSelectedMaterial}>清空</Button>
              </Space>
              <List size="small" dataSource={materialDocs} locale={{ emptyText: <Empty description="暂无个人材料或填写草稿" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} renderItem={(item) => (
                <List.Item className={`${selectedMaterialId === item.id ? 'selected-file-row' : 'file-row'} file-management-row`}>
                  <Checkbox checked={selectedMaterialId === item.id} className="file-row-main" onChange={() => loadMaterial(item.id)}>
                    <Space direction="vertical" size={2}>
                      <Text strong={selectedMaterialId === item.id}>{item.filename}</Text>
                      <Text type="secondary">{dayjs(item.created_at).format('MM-DD HH:mm')}</Text>
                    </Space>
                  </Checkbox>
                  <Space size={4} onMouseDown={stopControlEvent} onClick={stopControlEvent}>
                    <Button size="small" type="text" onMouseDown={stopControlEvent} onClick={(event) => previewDocumentFile(event, item.id)}>查看</Button>
                    <Button danger size="small" type="text" icon={<DeleteOutlined />} onMouseDown={stopControlEvent} onClick={(event) => confirmDeleteDocument(event, item.id)} />
                  </Space>
                </List.Item>
              )} />

              <Divider />
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Title level={5} style={{ marginBottom: 0 }}>最近任务</Title>
                <Button size="small" onClick={startNewSession}>新建对话</Button>
              </Space>
              <List size="small" dataSource={sessions.slice(0, 8)} locale={{ emptyText: '暂无可恢复会话' }} renderItem={(item, index) => (
                <List.Item className="recent-session-row" onClick={() => restoreSession(item.id)}>
                  <div className="session-row-main">
                    <Space><Tag color={activeSessionId === item.id ? 'blue' : 'default'}>{index + 1}</Tag><Text strong>{item.name}</Text></Space>
                    <div><Text type="secondary">{item.summary || '暂无摘要'}</Text></div>
                  </div>
                  <Space size={4} onMouseDown={stopControlEvent} onClick={stopControlEvent}>
                    <Button size="small" type="text" onMouseDown={stopControlEvent} onClick={(event) => renameSession(event, item)}>重命名</Button>
                    <Button danger size="small" type="text" icon={<DeleteOutlined />} onMouseDown={stopControlEvent} onClick={(event) => deleteSession(event, item.id)} />
                  </Space>
                </List.Item>
              )} />
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={18} className="workspace-col">
          <Card title="Copilot 对话工作区" className="workspace-card fixed-panel" bordered={false}>
            <div className="copilot-shell">
              <div className="copilot-context">
                <Alert type="info" showIcon message={`当前上下文：规则/模板 ${selectedKnowledgeIds.length} 份，个人材料 ${selectedMaterialId ? '1 份' : '未选择'}`} />
                <Space wrap>
                  {SCENARIOS.map((item) => <Tag key={item} color={scenario === item ? 'blue' : 'default'} className="action-tag" onClick={() => applyScenarioPreset(item)}>{item}</Tag>)}
                  <Space.Compact>
                    <Input value={customScenario} onChange={(event) => setCustomScenario(event.target.value)} placeholder="自定义场景" />
                    <Button onClick={applyCustomScenario}>应用</Button>
                  </Space.Compact>
                </Space>
              </div>
              <div className="copilot-workbench">
                <div className="copilot-stream" ref={streamRef}>
                  {copilotMessages.map((item) => (
                    <div key={item.id} className={`copilot-message copilot-message-${item.type}`}>
                      <Space align="center" style={{ marginBottom: 8 }}>
                        <Tag>{item.createdAt}</Tag>
                        <Text strong>{item.title}</Text>
                      </Space>
                      {renderCopilotMessage(item)}
                    </div>
                  ))}
                </div>
                <div className="copilot-side-panel">
                  <div className="copilot-toolbox">
                    <Button type="primary" icon={<SearchOutlined />} loading={loadingAction === 'ask'} onClick={() => askQuestion()}>发送问题</Button>
                    <Button icon={<OrderedListOutlined />} loading={loadingAction === 'noticeTasks'} onClick={generateNoticeTasks}>生成办理清单</Button>
                    <Button icon={<FileSearchOutlined />} loading={loadingAction === 'ask'} onClick={() => askPresetQuestion('请总结选中文件的核心事项、截止时间和材料要求')}>总结通知</Button>
                    <Button loading={loadingAction === 'fields'} onClick={identifyFields}>提取材料信息</Button>
                    <Button loading={loadingAction === 'auditAssist'} onClick={auditAndAssist}>审核并补全</Button>
                    <Button loading={loadingAction === 'form'} onClick={prefillForm}>生成表单草稿</Button>
                  </div>
                  <div className="copilot-side-section">
                    <Text strong>用户输入问题</Text>
                    <TextArea rows={7} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="输入问题，或直接点击上方快捷工具" />
                  </div>
                  <div className="copilot-side-section material-section">
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Text strong>当前材料文本</Text>
                      {selectedMaterial ? <Tag>{selectedMaterial.filename}</Tag> : null}
                    </Space>
                    <TextArea
                      value={materialText}
                      onChange={(event) => setMaterialText(event.target.value)}
                      placeholder="选择个人材料后自动填入，也可以粘贴个人信息、申请草稿或需要审核的内容"
                    />
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
