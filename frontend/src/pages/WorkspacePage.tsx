// 综合工作台页面：把上传、问答、材料审核、表单预填和流程规划串在一起。
import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Button, Card, Checkbox, Col, Descriptions, Divider, Empty, Input, List,
  message, Popconfirm, Radio, Row, Space, Statistic, Tabs, Tag, Timeline,
  Typography, Upload,
} from 'antd'
import {
  AuditOutlined, CheckCircleOutlined, DeleteOutlined, FileSearchOutlined,
  FormOutlined, InboxOutlined, OrderedListOutlined, RobotOutlined, SearchOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import type { UploadRequestOption } from 'rc-upload/lib/interface'
import api from '../api'
import {
  AskResponse, AuditResponse, DemoAsset, DocumentDetail, DocumentItem,
  FormFillResponse, HistoryItem, OCRResponse, SummaryResponse, WorkflowResponse,
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

const SCENARIO_PRESETS: Record<string, { question: string; quickQuestions: string[]; material: string; uploadMode: UploadMode }> = {
  比赛报名: {
    question: '参赛对象是谁？',
    quickQuestions: ['单人能否参赛？', '报名截止时间是什么？', '作品提交到哪里？', '参赛对象是谁？'],
    material: '姓名：张三\n学号：2023001001\n学院/班级：计算机学院 软件工程 2023级1班\n联系方式：13800138000\n项目名称：智审通 Campus Copilot\n队伍人数：4\n指导教师：李老师\n邮箱：demo@example.com\n团队成员：张三、李四、王五、赵六',
    uploadMode: 'knowledge_base',
  },
  请假审批: {
    question: '请假需要提交哪些证明材料？',
    quickQuestions: ['请假需要提交哪些证明材料？', '病假和事假流程有什么区别？', '请假单需要哪些字段？', '审批下一步怎么做？'],
    material: '姓名：李明\n学号：2023002002\n学院/班级：计算机学院 2023级2班\n联系方式：13900139000\n请假类型：病假\n请假时间：2026-05-10 至 2026-05-12\n请假原因：发热需就医\n证明材料：门诊病历照片',
    uploadMode: 'material',
  },
  奖助学金申请: {
    question: '奖助学金申请需要哪些材料？',
    quickQuestions: ['奖助学金申请需要哪些材料？', '成绩排名是否会影响资格？', '缺少困难认定表怎么办？', '申请表可以预填哪些字段？'],
    material: '姓名：王同学\n学号：2023003003\n学院/班级：计算机学院 2023级3班\n联系方式：13700137000\n申请类型：助学金\n成绩排名：20%\n困难认定：已通过',
    uploadMode: 'material',
  },
  报销办理: {
    question: '报销申请需要哪些票据？',
    quickQuestions: ['报销申请需要哪些票据？', '发票金额需要核验什么？', '缺少审批截图能否提交？', '报销流程下一步是什么？'],
    material: '申请人：赵老师\n学院：计算机学院\n联系方式：13600136000\n报销事项：竞赛材料采购\n报销金额：1280.50\n附件：电子发票、支付截图、审批截图',
    uploadMode: 'material',
  },
  社团活动审批: {
    question: '社团活动审批需要哪些材料？',
    quickQuestions: ['社团活动审批需要哪些材料？', '活动安全预案是否必需？', '预计人数会影响审批吗？', '活动流程清单怎么生成？'],
    material: '活动名称：AI 创新分享会\n主办单位：智能社团\n负责人：陈同学\n联系方式：13500135000\n活动时间：2026-05-18 14:00\n活动地点：教学楼报告厅\n预计人数：80\n附件：活动方案、安全预案、场地申请',
    uploadMode: 'material',
  },
}

const FIELD_LABELS: Record<string, string> = {
  material_type: '材料类型',
  name: '姓名/负责人',
  student_id: '学号',
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
}

type UploadMode = 'knowledge_base' | 'material' | 'both'

interface WorkspacePageProps {
  initialScenario?: string
}

function emptyAnswer(): AskResponse {
  return { answer: '', citations: [], suggestions: [], trace: [], fallback_used: false }
}

function sourceTypeLabel(value: string) {
  if (value === 'knowledge_base') return '制度/通知'
  if (value === 'material') return '办理材料'
  if (value === 'both') return '双用途'
  return value
}

function orderedFieldEntries(fields: Record<string, string>) {
  const order = Object.keys(FIELD_LABELS)
  return Object.entries(fields).sort(([a], [b]) => {
    const left = order.indexOf(a)
    const right = order.indexOf(b)
    return (left === -1 ? 99 : left) - (right === -1 ? 99 : right)
  })
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

export default function WorkspacePage({ initialScenario = '比赛报名' }: WorkspacePageProps) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [demoAssets, setDemoAssets] = useState<DemoAsset[]>([])
  const [scenario, setScenario] = useState(normalizeScenarioName(initialScenario))
  const [customScenario, setCustomScenario] = useState('')
  const [uploadMode, setUploadMode] = useState<UploadMode>('knowledge_base')
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<number[]>([])
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)
  const [question, setQuestion] = useState(SCENARIO_PRESETS[initialScenario]?.question || SCENARIO_PRESETS['比赛报名'].question)
  const [quickQuestions, setQuickQuestions] = useState(SCENARIO_PRESETS[initialScenario]?.quickQuestions || SCENARIO_PRESETS['比赛报名'].quickQuestions)
  const [materialText, setMaterialText] = useState(SCENARIO_PRESETS[initialScenario]?.material || SCENARIO_PRESETS['比赛报名'].material)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [fieldResult, setFieldResult] = useState<Record<string, string>>({})
  const [ocrResult, setOcrResult] = useState<OCRResponse | null>(null)
  const [auditResult, setAuditResult] = useState<AuditResponse | null>(null)
  const [formResult, setFormResult] = useState<FormFillResponse | null>(null)
  const [workflowResult, setWorkflowResult] = useState<WorkflowResponse | null>(null)
  const [previewDocument, setPreviewDocument] = useState<DocumentDetail | null>(null)
  const [activePanel, setActivePanel] = useState('preview')
  const [loadingAction, setLoadingAction] = useState<string | null>(null)

  const scenarioCode = SCENARIO_CODES[scenario] || 'competition_registration'
  const knowledgeDocs = documents.filter((item) => item.source_type === 'knowledge_base' || item.source_type === 'both')
  const materialDocs = documents.filter((item) => item.source_type === 'material' || item.source_type === 'both')
  const selectedMaterial = materialDocs.find((item) => item.id === selectedMaterialId)
  const canPlanWorkflow = selectedKnowledgeIds.length > 0 || materialText.trim().length > 0 || !!auditResult

  const statItems = useMemo(
    () => (summary?.metrics || []).map((item) => ({
      ...item,
      icon: item.label.includes('耗时') ? <OrderedListOutlined /> : item.label.includes('漏') ? <CheckCircleOutlined /> : <FileSearchOutlined />,
    })),
    [summary],
  )

  const loadAll = async () => {
    // 工作台启动时并行拉取摘要、文档、历史和演示素材，减少首屏等待。
    const [s, d, h, assets] = await Promise.all([
      api.get<SummaryResponse>('/dashboard/summary'),
      api.get<DocumentItem[]>('/documents'),
      api.get<HistoryItem[]>('/tasks/recent'),
      api.get<DemoAsset[]>('/demo/assets'),
    ])
    setSummary(s.data)
    setDocuments(d.data)
    setHistory(h.data)
    setDemoAssets(assets.data)
  }

  useEffect(() => {
    loadAll().catch(() => undefined)
  }, [])

  const applyScenarioPreset = (nextScenario: string) => {
    // 切换场景时同步替换问题、快捷问法、示例材料和上传用途。
    const preset = SCENARIO_PRESETS[nextScenario] || SCENARIO_PRESETS['比赛报名']
    setScenario(nextScenario)
    setQuestion(preset.question)
    setQuickQuestions(preset.quickQuestions)
    setMaterialText(preset.material)
    setUploadMode(preset.uploadMode)
    setAnswer(null)
    setFieldResult({})
    setOcrResult(null)
    setAuditResult(null)
    setFormResult(null)
    setWorkflowResult(null)
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
    setSelectedMaterialId(id)
    const res = await api.get<DocumentDetail>(`/documents/${id}`)
    setPreviewDocument(res.data)
    setMaterialText(res.data.content || '')
    setActivePanel('preview')
  }

  const deleteDocument = async (id: number) => {
    await api.delete(`/documents/${id}`)
    setSelectedKnowledgeIds((ids) => ids.filter((item) => item !== id))
    if (selectedMaterialId === id) setSelectedMaterialId(null)
    if (previewDocument?.id === id) setPreviewDocument(null)
    message.success('文件已删除')
    await loadAll()
  }

  const handleUpload = async (options: UploadRequestOption) => {
    // 图片类材料走 OCR，文本/文档类材料走后端文档解析和可选知识库索引。
    const file = options.file as File
    const suffix = file.name.split('.').pop()?.toLowerCase() || ''
    const isImage = ['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(suffix)
    const form = new FormData()
    form.append('file', file)
    setLoadingAction('upload')
    try {
      if (isImage) {
        const res = await api.post<OCRResponse>('/audit/upload', form)
        setOcrResult(res.data)
        setMaterialText(res.data.text)
        setFieldResult(res.data.extracted_fields || {})
        setActivePanel('fields')
      } else {
        form.append('scenario', scenarioCode)
        form.append('source_type', uploadMode)
        const res = await api.post('/documents/upload', form)
        const id = res.data.document_id as number
        if (uploadMode === 'knowledge_base' || uploadMode === 'both') {
          setSelectedKnowledgeIds((ids) => Array.from(new Set([...ids, id])))
        }
        if (uploadMode === 'material' || uploadMode === 'both') {
          setSelectedMaterialId(id)
          await loadMaterial(id)
        }
      }
      message.success(`${file.name} 上传成功`)
      await loadAll()
      options.onSuccess?.({}, new XMLHttpRequest())
    } catch (error: any) {
      message.error(error?.response?.data?.detail || `${file.name} 上传失败`)
      options.onError?.(error)
    } finally {
      setLoadingAction(null)
    }
  }

  const importDemoNotice = async () => {
    setLoadingAction('demo')
    try {
      const res = await api.post('/demo/load-contest-notice')
      setSelectedKnowledgeIds((ids) => Array.from(new Set([...ids, res.data.document_id])))
      message.success('示例比赛通知已导入')
      await loadAll()
    } finally {
      setLoadingAction(null)
    }
  }

  const askQuestion = async () => {
    if (!selectedKnowledgeIds.length) {
      message.warning('请先在左侧勾选用于问答的制度/通知文件')
      return emptyAnswer()
    }
    setLoadingAction('ask')
    try {
      const res = await api.post<AskResponse>('/chat/query', {
        question,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
      })
      setAnswer(res.data)
      setActivePanel('rag')
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const identifyFields = async () => {
    setLoadingAction('fields')
    try {
      const res = await api.post('/audit/extract-fields', {
        text: materialText,
        scenario: scenarioCode,
        ocr_fields: ocrResult?.extracted_fields || {},
      })
      setFieldResult(res.data.fields || {})
      setActivePanel('fields')
      await loadAll()
      return res.data.fields || {}
    } finally {
      setLoadingAction(null)
    }
  }

  const auditMaterial = async () => {
    // 审核前确保已有结构化字段；如果用户没手动提取，就先自动提取一次。
    setLoadingAction('audit')
    try {
      const fields = Object.keys(fieldResult).length ? fieldResult : await identifyFields()
      const res = await api.post<AuditResponse>('/audit/run', {
        material_name: selectedMaterial?.filename || '当前材料文本',
        text: materialText,
        task_type: scenarioCode,
        scenario: scenarioCode,
        ocr_fields: fields,
      })
      setAuditResult(res.data)
      setFieldResult(res.data.recognized_fields || fields)
      setActivePanel('audit')
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
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
      })
      setFormResult(res.data)
      setActivePanel('form')
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const generateWorkflow = async () => {
    if (!canPlanWorkflow) {
      message.warning('请先选择制度/通知文件，或上传/粘贴一份办理材料')
      return null
    }
    setLoadingAction('workflow')
    try {
      // 把审核结论和材料正文拼进流程规划请求，让下一步建议更贴近当前材料状态。
      const auditContext = auditResult
        ? `\n审核结论：${auditResult.level}\n缺失项：${auditResult.missing_items.join('、') || '无'}\n审核建议：${auditResult.suggestions.join('、') || auditResult.conclusion}`
        : ''
      const materialContext = materialText.trim() ? `\n当前材料内容：\n${materialText.slice(0, 8000)}` : ''
      const res = await api.post<WorkflowResponse>('/workflow/plan', {
        request_text: `${question}${auditContext}${materialContext}`,
        scenario: scenarioCode,
        document_ids: selectedKnowledgeIds,
      })
      setWorkflowResult(res.data)
      setActivePanel('workflow')
      await loadAll()
      return res.data
    } finally {
      setLoadingAction(null)
    }
  }

  const runFullChain = async () => {
    // 完整闭环按依赖顺序执行：问答可选，字段识别、审核、预填、规划依次推进。
    setLoadingAction('full')
    try {
      if (selectedKnowledgeIds.length) await askQuestion()
      await identifyFields()
      await auditMaterial()
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
      label: '材料信息',
      children: Object.keys(fieldResult).length ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type="info" showIcon message="这里展示从当前办理材料中抽取出的字段，用于后续审核和表单预填。" />
          <Descriptions size="small" column={1} bordered>
            {orderedFieldEntries(fieldResult).map(([key, value]) => (
              <Descriptions.Item key={key} label={FIELD_LABELS[key] || key}>{value || '-'}</Descriptions.Item>
            ))}
          </Descriptions>
        </Space>
      ) : <Empty description="上传材料或点击“提取材料信息”后显示结构化字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
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
      ) : <Empty description="点击“审核材料”后，这里展示基于当前材料字段的审核结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'form',
      label: '表单',
      children: formResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Descriptions size="small" column={1} bordered>
            {Object.entries(formResult.fields).map(([key, value]) => <Descriptions.Item key={key} label={key}>{value || '-'}</Descriptions.Item>)}
          </Descriptions>
          <List size="small" header="仍需补充字段" dataSource={formResult.missing_fields} locale={{ emptyText: '表单字段已较完整' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="点击“预填表单”后，这里展示可写入表单的结构化结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
    {
      key: 'workflow',
      label: '下一步',
      children: workflowResult ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert type="success" showIcon message={workflowResult.summary} />
          <Timeline items={workflowResult.steps.map((item) => ({ children: <div><Text strong>{item.title}</Text><div>{item.detail}</div>{item.deadline ? <Tag color="gold">{item.deadline}</Tag> : null}</div> }))} />
          <List size="small" header="风险提醒" dataSource={workflowResult.risk_reminders} locale={{ emptyText: '暂无风险提醒' }} renderItem={(item) => <List.Item>{item}</List.Item>} />
        </Space>
      ) : <Empty description="点击“生成下一步”后，这里会按当前材料和选中文件生成计划" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <section className="compact-hero">
        <div>
          <Space wrap align="center">
            <Title level={2} className="compact-title">智审通 Campus Copilot</Title>
            <Tag color="cyan">高校智能办理平台</Tag>
            <Tag color={summary?.demo_mode ? 'orange' : 'green'}>{summary?.demo_mode ? '演示降级模式' : '真实模型模式'}</Tag>
          </Space>
          <Paragraph className="compact-desc">统一文件中心，选择文件后按需运行问答、材料核验、表单预填和下一步计划。</Paragraph>
        </div>
        <Space wrap>{statItems.slice(0, 3).map((item) => <Statistic key={item.label} title={item.label} value={item.value} prefix={item.icon} />)}</Space>
      </section>

      <Row gutter={[16, 16]} align="stretch" className="workspace-grid">
        <Col xs={24} xl={6} className="workspace-col">
          <Card title="文件中心" className="workspace-card fixed-panel" bordered={false}>
            <div className="panel-scroll">
              <Radio.Group value={uploadMode} onChange={(event) => setUploadMode(event.target.value)} optionType="button" buttonStyle="solid" className="upload-mode">
                <Radio.Button value="knowledge_base">制度/通知</Radio.Button>
                <Radio.Button value="material">办理材料</Radio.Button>
                <Radio.Button value="both">双用途</Radio.Button>
              </Radio.Group>
              <Upload.Dragger customRequest={handleUpload} showUploadList={false} accept=".png,.jpg,.jpeg,.bmp,.webp,.pdf,.docx,.txt,.md">
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">上传{sourceTypeLabel(uploadMode)}</p>
                <p className="ant-upload-hint">通知和材料在同一文件时选择“双用途”。上传后可在下方勾选或查看。</p>
              </Upload.Dragger>
              <Button block style={{ marginTop: 10 }} loading={loadingAction === 'demo'} onClick={importDemoNotice}>导入示例通知</Button>

              <Divider />
              <Title level={5}>制度/通知</Title>
              <Checkbox.Group value={selectedKnowledgeIds} onChange={(values) => setSelectedKnowledgeIds(values as number[])} style={{ width: '100%' }}>
                <List size="small" dataSource={knowledgeDocs} locale={{ emptyText: <Empty description="暂无制度/通知文件" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} renderItem={(item) => (
                  <List.Item actions={[
                    <Button size="small" type="text" onClick={() => previewFile(item.id)}>查看</Button>,
                    <Popconfirm title="确认删除该文件？" onConfirm={() => deleteDocument(item.id)}><Button danger size="small" type="text" icon={<DeleteOutlined />} /></Popconfirm>,
                  ]}>
                    <Checkbox value={item.id}><Text>{item.filename}</Text></Checkbox>
                  </List.Item>
                )} />
              </Checkbox.Group>

              <Divider />
              <Title level={5}>办理材料</Title>
              <List size="small" dataSource={materialDocs} locale={{ emptyText: <Empty description="暂无办理材料" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} renderItem={(item) => (
                <List.Item onClick={() => loadMaterial(item.id)} className={selectedMaterialId === item.id ? 'selected-file-row' : 'file-row'} actions={[
                  <Button size="small" type="text" onClick={(event) => { event.stopPropagation(); previewFile(item.id) }}>查看</Button>,
                  <Popconfirm title="确认删除该文件？" onConfirm={() => deleteDocument(item.id)}><Button danger size="small" type="text" icon={<DeleteOutlined />} /></Popconfirm>,
                ]}>
                  <Space direction="vertical" size={2}>
                    <Text strong={selectedMaterialId === item.id}>{item.filename}</Text>
                    <Text type="secondary">{dayjs(item.created_at).format('MM-DD HH:mm')}</Text>
                  </Space>
                </List.Item>
              )} />

              <Divider />
              <Title level={5}>最近任务</Title>
              <List size="small" dataSource={history.slice(0, 8)} locale={{ emptyText: '暂无任务记录' }} renderItem={(item) => (
                <List.Item><div><Space><Tag>{item.type}</Tag><Text strong>{item.title}</Text></Space><div><Text type="secondary">{item.summary}</Text></div></div></List.Item>
              )} />
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={10} className="workspace-col">
          <Card title="操作台" className="workspace-card fixed-panel" bordered={false}>
            <div className="panel-scroll">
              <Alert type="info" showIcon message={`当前选择：制度/通知 ${selectedKnowledgeIds.length} 份，办理材料 ${selectedMaterialId ? '1 份' : '未选择'}`} style={{ marginBottom: 16 }} />
              <Title level={5}>场景</Title>
              <Space wrap>{SCENARIOS.map((item) => <Tag key={item} color={scenario === item ? 'blue' : 'default'} className="action-tag" onClick={() => applyScenarioPreset(item)}>{item}</Tag>)}</Space>
              <Space.Compact style={{ width: '100%', marginTop: 12 }}>
                <Input value={customScenario} onChange={(event) => setCustomScenario(event.target.value)} placeholder="其他场景，如：实践周志、科研立项、宿舍维修" />
                <Button onClick={applyCustomScenario}>应用场景</Button>
              </Space.Compact>

              <Divider />
              <Title level={5}>提问咨询</Title>
              <TextArea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} />
              <Space wrap style={{ marginTop: 10 }}>{quickQuestions.map((item) => <Tag key={item} className="action-tag" onClick={() => setQuestion(item)}>{item}</Tag>)}</Space>
              <div style={{ marginTop: 12 }}>
                <Button type="primary" icon={<SearchOutlined />} loading={loadingAction === 'ask'} onClick={askQuestion}>提问咨询</Button>
              </div>

              <Divider />
              <Title level={5}>材料核验与填表</Title>
              <TextArea rows={10} value={materialText} onChange={(event) => setMaterialText(event.target.value)} />
              <Space wrap style={{ marginTop: 12 }}>
                <Button loading={loadingAction === 'fields'} onClick={identifyFields}>提取材料信息</Button>
                <Button icon={<AuditOutlined />} loading={loadingAction === 'audit'} onClick={auditMaterial}>审核材料</Button>
                <Button icon={<FormOutlined />} loading={loadingAction === 'form'} onClick={prefillForm}>预填表单</Button>
                <Button loading={loadingAction === 'workflow'} disabled={!canPlanWorkflow} onClick={generateWorkflow}>生成下一步</Button>
                <Button type="primary" loading={loadingAction === 'full'} disabled={!canPlanWorkflow} onClick={runFullChain}>运行完整闭环</Button>
              </Space>
              <Space wrap style={{ marginTop: 10 }}>{demoAssets.filter((item) => item.type === 'material').map((item) => <Button key={item.name} onClick={() => setMaterialText(item.content)}>{item.name}</Button>)}</Space>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8} className="workspace-col">
          <Card
            title="结果面板"
            className="workspace-card fixed-panel"
            bordered={false}
            extra={<Space wrap>
              <Button size="small" href="http://localhost:8000/api/exports/audit/latest" target="_blank">导出审核</Button>
              <Button size="small" href="http://localhost:8000/api/exports/form/latest" target="_blank">导出表单</Button>
              <Button size="small" href="http://localhost:8000/api/exports/workflow/latest" target="_blank">导出待办</Button>
            </Space>}
          >
            <div className="panel-scroll"><Tabs activeKey={activePanel} onChange={setActivePanel} items={resultTabs} /></div>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
