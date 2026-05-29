// 数据分析智能体页面：按会话保存表格上传、分析摘要和连续追问。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Col, Descriptions, Empty, Input, List, Row, Space, Table, Tag, Typography, Upload, message } from 'antd'
import { BarChartOutlined, DeleteOutlined, FileExcelOutlined, SendOutlined, ThunderboltOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import api from '../api'
import type { DataAnalysisBlock, DataAnalysisChatResponse, DataAnalysisResponse, SessionDetail, SessionItem } from '../types'

const { Dragger } = Upload
const { Paragraph, Text, Title } = Typography

const DEFAULT_TASK = '请分析这批校园业务数据的整体情况、异常和后续建议'

type AnalysisMessage =
  | { id: string; type: 'system'; title: string; content: string; createdAt: string }
  | { id: string; type: 'analysis'; title: string; payload: DataAnalysisResponse; createdAt: string }
  | { id: string; type: 'question'; title: string; content: string; createdAt: string }
  | { id: string; type: 'answer'; title: string; content: string; fallback_used: boolean; createdAt: string }

function makeMessage(type: AnalysisMessage['type'], title: string, contentOrPayload: string | DataAnalysisResponse, fallback_used = false): AnalysisMessage {
  const base = { id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, title, createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  if (type === 'analysis') return { ...base, type, payload: contentOrPayload as DataAnalysisResponse }
  if (type === 'answer') return { ...base, type, content: contentOrPayload as string, fallback_used }
  if (type === 'question') return { ...base, type, content: contentOrPayload as string }
  return { ...base, type: 'system', content: contentOrPayload as string }
}

export default function DataAnalysisPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [task, setTask] = useState(DEFAULT_TASK)
  const [question, setQuestion] = useState('请进一步说明这些数据里最需要关注的问题')
  const [loading, setLoading] = useState<string | null>(null)
  const [result, setResult] = useState<DataAnalysisResponse | null>(null)
  const [messages, setMessages] = useState<AnalysisMessage[]>([
    makeMessage('system', '数据分析智能体已就绪', '新建会话后可上传多个 Excel/CSV 文件，系统会先给出总体分析，然后你可以继续追问。'),
  ])
  const streamRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  const loadSessions = async () => {
    const res = await api.get<SessionItem[]>('/analytics/sessions')
    setSessions(res.data)
  }

  useEffect(() => {
    loadSessions().catch(() => undefined)
  }, [])

  const createSession = async () => {
    const res = await api.post<SessionItem>('/analytics/sessions')
    setActiveSessionId(res.data.id)
    setSessions((items) => [res.data, ...items.filter((item) => item.id !== res.data.id)])
    setResult(null)
    setMessages([makeMessage('system', '已创建新会话', '请上传一个或多个表格文件开始分析。')])
    message.success('已新建数据分析会话')
  }

  const restoreSession = async (id: number) => {
    const res = await api.get<SessionDetail>(`/analytics/sessions/${id}`)
    setActiveSessionId(id)
    const restored: AnalysisMessage[] = []
    let latest: DataAnalysisResponse | null = null
    res.data.events.forEach((event) => {
      if (event.event_type === 'analytics_analysis') {
        const analysis = event.payload.result as DataAnalysisResponse | undefined
        if (analysis) {
          latest = analysis
          restored.push(makeMessage('analysis', event.title || analysis.task, analysis))
        }
      }
      if (event.event_type === 'analytics_chat') {
        restored.push(makeMessage('question', '我的追问', String(event.payload.question || event.title)))
        restored.push(makeMessage('answer', '分析回答', String(event.payload.answer || ''), Boolean(event.payload.fallback_used)))
      }
    })
    setResult(latest)
    setMessages(restored.length ? restored : [makeMessage('system', '已恢复会话', '这个会话还没有分析记录。')])
  }

  const deleteSession = async (id: number) => {
    if (!window.confirm('确认删除该数据分析会话？')) return
    await api.delete(`/analytics/sessions/${id}`)
    if (activeSessionId === id) {
      setActiveSessionId(null)
      setResult(null)
      setMessages([makeMessage('system', '会话已删除', '可以新建会话重新开始分析。')])
    }
    await loadSessions()
    message.success('会话已删除')
  }

  const ensureSession = async () => {
    if (activeSessionId) return activeSessionId
    const res = await api.post<SessionItem>('/analytics/sessions')
    setActiveSessionId(res.data.id)
    setSessions((items) => [res.data, ...items.filter((item) => item.id !== res.data.id)])
    return res.data.id
  }

  const analyze = async () => {
    const files = fileList.map((file) => file.originFileObj).filter(Boolean)
    if (!files.length) {
      message.warning('请先上传 Excel 或 CSV 文件')
      return
    }
    const sessionId = await ensureSession()
    const form = new FormData()
    files.forEach((file) => form.append('files', file as File))
    form.append('task', task)
    form.append('session_id', String(sessionId))
    setLoading('analyze')
    try {
      const res = await api.post<DataAnalysisResponse>('/analytics/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      setMessages((items) => [...items, makeMessage('analysis', task, res.data)])
      setFileList([])
      await loadSessions()
      message.success('数据分析完成')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '数据分析失败')
    } finally {
      setLoading(null)
    }
  }

  const ask = async () => {
    if (!activeSessionId) {
      message.warning('请先新建会话并上传表格')
      return
    }
    if (!question.trim()) return
    setLoading('ask')
    const currentQuestion = question.trim()
    setMessages((items) => [...items, makeMessage('question', '我的追问', currentQuestion)])
    try {
      const res = await api.post<DataAnalysisChatResponse>('/analytics/chat', { session_id: activeSessionId, question: currentQuestion })
      setMessages((items) => [...items, makeMessage('answer', '分析回答', res.data.answer, res.data.fallback_used)])
      setQuestion('')
      await loadSessions()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '追问失败')
    } finally {
      setLoading(null)
    }
  }

  const activeBlock = result?.blocks[0]
  const previewColumns = useMemo(() => activeBlock
    ? Object.keys(activeBlock.preview[0] || {}).map((key) => ({
        title: key,
        dataIndex: key,
        key,
        ellipsis: true,
        render: (value: unknown) => String(value ?? ''),
      }))
    : [], [activeBlock])

  const renderAnalysis = (analysis: DataAnalysisResponse) => (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Descriptions size="small" bordered column={3}>
        <Descriptions.Item label="数据块">{analysis.block_count}</Descriptions.Item>
        <Descriptions.Item label="文件数">{analysis.files.length}</Descriptions.Item>
        <Descriptions.Item label="模式">{analysis.fallback_used ? '规则分析' : '模型增强'}</Descriptions.Item>
      </Descriptions>
      <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{analysis.insights}</Paragraph>
      <Space wrap>
        {analysis.blocks.slice(0, 6).map((block: DataAnalysisBlock) => (
          <Tag key={block.key}>{block.file_name} / {block.row_count} 行 / 缺失 {(block.missing_rate * 100).toFixed(1)}%</Tag>
        ))}
      </Space>
    </Space>
  )

  return (
    <Row gutter={[16, 16]} className="analytics-page">
      <Col xs={24} xl={5}>
        <Card title="分析会话" bordered={false} className="workspace-card records-panel">
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Button type="primary" block onClick={createSession}>新建会话</Button>
            <List
              size="small"
              dataSource={sessions}
              locale={{ emptyText: '暂无分析会话' }}
              renderItem={(item, index) => (
                <List.Item className="recent-session-row" onClick={() => restoreSession(item.id)}>
                  <div className="session-row-main">
                    <Space><Tag color={activeSessionId === item.id ? 'blue' : 'default'}>{index + 1}</Tag><Text strong>{item.name}</Text></Space>
                    <div><Text type="secondary">{item.summary || '暂无分析记录'}</Text></div>
                  </div>
                  <Button danger size="small" type="text" icon={<DeleteOutlined />} onClick={(event) => { event.stopPropagation(); deleteSession(item.id) }} />
                </List.Item>
              )}
            />
          </Space>
        </Card>
      </Col>
      <Col xs={24} xl={12}>
        <Card title={<Space><BarChartOutlined />数据分析对话</Space>} bordered={false} className="workspace-card records-panel">
          <div className="analytics-stream" ref={streamRef}>
            {messages.map((item) => (
              <div key={item.id} className={`copilot-message copilot-message-${item.type}`}>
                <Space align="center" style={{ marginBottom: 8 }}><Tag>{item.createdAt}</Tag><Text strong>{item.title}</Text></Space>
                {item.type === 'analysis' ? renderAnalysis(item.payload) : <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{item.content}</Paragraph>}
              </div>
            ))}
          </div>
        </Card>
      </Col>
      <Col xs={24} xl={7}>
        <Card title="数据与追问" bordered={false} className="workspace-card records-panel">
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Alert type="info" showIcon message="每个会话可上传多个表格，分析结果和追问都会保存在当前会话中。" />
            <Dragger multiple beforeUpload={() => false} fileList={fileList} accept=".xlsx,.xls,.csv" onChange={({ fileList: nextList }) => setFileList(nextList)}>
              <p className="ant-upload-drag-icon"><FileExcelOutlined /></p>
              <p className="ant-upload-text">上传 Excel/CSV</p>
              <p className="ant-upload-hint">支持一次上传多个文件</p>
            </Dragger>
            <Input.TextArea rows={4} value={task} onChange={(event) => setTask(event.target.value)} placeholder="输入本次数据分析目标" />
            <Button type="primary" icon={<ThunderboltOutlined />} loading={loading === 'analyze'} onClick={analyze} block>上传并分析</Button>
            <Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="继续追问当前数据" />
            <Button icon={<SendOutlined />} loading={loading === 'ask'} onClick={ask} block>继续追问</Button>
            {activeBlock ? (
              <>
                <Title level={5}>首个数据块预览</Title>
                <Table size="small" rowKey={(_, index) => String(index)} columns={previewColumns} dataSource={activeBlock.preview} pagination={false} scroll={{ x: true }} />
              </>
            ) : <Empty description="上传表格后显示预览" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Space>
        </Card>
      </Col>
    </Row>
  )
}
