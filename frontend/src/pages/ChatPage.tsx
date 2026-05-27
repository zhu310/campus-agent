// 独立问答页面：用于围绕已选知识文档进行 RAG 咨询。
import { Button, Card, Col, Input, Row, Space, Typography, Upload, message, Tag, Divider, List, Descriptions } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { useState } from 'react'
import api from '../api'
import { AskResponse, AuditResponse, FormFillResponse } from '../types'

const { TextArea } = Input
const { Title, Paragraph, Text } = Typography

export default function ChatPage() {
  const [question, setQuestion] = useState('我一个人可以参加这个比赛吗？报名截止时间是什么时候？')
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [materialText, setMaterialText] = useState('姓名：张三\n手机号：13800138000\n邮箱：demo@example.com\nQQ：12345678\n项目名称：校智办——高校事务智能办理Agent\n指导教师：李老师')
  const [auditResult, setAuditResult] = useState<AuditResponse | null>(null)
  const [formResult, setFormResult] = useState<FormFillResponse | null>(null)
  const [loadingAsk, setLoadingAsk] = useState(false)
  const [loadingAudit, setLoadingAudit] = useState(false)
  const [loadingForm, setLoadingForm] = useState(false)

  const uploadProps = {
    name: 'file',
    action: 'http://localhost:8000/api/documents/upload',
    onChange(info: any) {
      if (info.file.status === 'done') {
        message.success(`上传成功：${info.file.name}`)
      } else if (info.file.status === 'error') {
        message.error(`上传失败：${info.file.name}`)
      }
    },
  }

  const handleAsk = async () => {
    try {
      setLoadingAsk(true)
      const { data } = await api.post<AskResponse>('/chat/ask', { question })
      setAnswer(data)
    } finally {
      setLoadingAsk(false)
    }
  }

  const handleAudit = async () => {
    try {
      setLoadingAudit(true)
      const { data } = await api.post<AuditResponse>('/audit', {
        material_name: '报名材料',
        text: materialText,
        task_type: 'competition_registration',
      })
      setAuditResult(data)
    } finally {
      setLoadingAudit(false)
    }
  }

  const handlePrefill = async () => {
    try {
      setLoadingForm(true)
      const { data } = await api.post<FormFillResponse>('/forms/prefill', { text: materialText })
      setFormResult(data)
    } finally {
      setLoadingForm(false)
    }
  }

  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card title="资料上传" bordered={false}>
          <Upload.Dragger {...uploadProps} accept=".pdf,.txt,.md">
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">上传通知、制度、比赛说明 PDF</p>
            <p className="ant-upload-hint">支持 pdf / txt / md</p>
          </Upload.Dragger>
          <Divider />
          <Title level={5}>推荐提问</Title>
          <Space direction="vertical">
            <Tag onClick={() => setQuestion('报名要求是什么？')} style={{ cursor: 'pointer' }}>报名要求是什么？</Tag>
            <Tag onClick={() => setQuestion('我一个人能参加吗？')} style={{ cursor: 'pointer' }}>我一个人能参加吗？</Tag>
            <Tag onClick={() => setQuestion('作品提交时间是什么时候？')} style={{ cursor: 'pointer' }}>作品提交时间是什么时候？</Tag>
          </Space>
        </Card>
      </Col>

      <Col span={10}>
        <Card title="智能问答与材料处理" bordered={false}>
          <Title level={5}>RAG 智能问答</Title>
          <TextArea rows={4} value={question} onChange={(e) => setQuestion(e.target.value)} />
          <Space style={{ marginTop: 12 }}>
            <Button type="primary" onClick={handleAsk} loading={loadingAsk}>提问</Button>
          </Space>
          {answer && (
            <>
              <Divider />
              <Title level={5}>回答结果</Title>
              <Paragraph>{answer.answer}</Paragraph>
            </>
          )}

          <Divider />
          <Title level={5}>材料文本 / OCR结果</Title>
          <TextArea rows={10} value={materialText} onChange={(e) => setMaterialText(e.target.value)} />
          <Space style={{ marginTop: 12 }}>
            <Button onClick={handleAudit} loading={loadingAudit}>审核材料</Button>
            <Button onClick={handlePrefill} loading={loadingForm}>预填表单</Button>
          </Space>
        </Card>
      </Col>

      <Col span={8}>
        <Card title="结果面板" bordered={false}>
          <Title level={5}>检索依据</Title>
          <List
            size="small"
            dataSource={answer?.citations || []}
            locale={{ emptyText: '暂无依据' }}
            renderItem={(item) => (
              <List.Item>
                <div>
                  <Text strong>{item.filename}</Text>
                  <Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} style={{ marginBottom: 0 }}>
                    {item.text}
                  </Paragraph>
                </div>
              </List.Item>
            )}
          />

          <Divider />
          <Title level={5}>材料审核结果</Title>
          {auditResult ? (
            <>
              <Tag color={auditResult.passed ? 'green' : 'red'}>{auditResult.passed ? '通过' : '未通过'}</Tag>
              <Descriptions size="small" column={1} style={{ marginTop: 12 }}>
                {Object.entries(auditResult.recognized_fields).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>{v}</Descriptions.Item>
                ))}
              </Descriptions>
              <Paragraph>
                <Text strong>缺失项：</Text> {auditResult.missing_items.length ? auditResult.missing_items.join('，') : '无'}
              </Paragraph>
              <Paragraph>
                <Text strong>提醒：</Text> {auditResult.warnings.length ? auditResult.warnings.join('；') : '无'}
              </Paragraph>
            </>
          ) : <Text type="secondary">暂无审核结果</Text>}

          <Divider />
          <Title level={5}>表单预填结果</Title>
          {formResult ? (
            <Descriptions size="small" column={1}>
              {Object.entries(formResult.fields).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>{v || '-'}</Descriptions.Item>
              ))}
            </Descriptions>
          ) : <Text type="secondary">暂无预填结果</Text>}
        </Card>
      </Col>
    </Row>
  )
}
