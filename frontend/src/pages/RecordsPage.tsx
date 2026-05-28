// 任务历史页：面向用户回看历史对话、任务卡、填写建议和审核结果。
import { useEffect, useState } from 'react'
import { Card, Col, Descriptions, Empty, List, Row, Space, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import api from '../api'
import { HistoryItem, TaskDetail } from '../types'

const { Text, Paragraph } = Typography

function typeLabel(type: string) {
  if (type.includes('chat') || type.includes('问答')) return '问答'
  if (type.includes('workflow') || type.includes('待办') || type.includes('任务')) return '任务卡'
  if (type.includes('form') || type.includes('填写')) return '填写'
  if (type.includes('audit') || type.includes('审核')) return '审核'
  return type || '记录'
}

function readablePayload(payload: Record<string, unknown>) {
  const output = payload.output_payload as Record<string, unknown> | undefined
  const input = payload.input_payload as Record<string, unknown> | undefined
  const result = payload.result as Record<string, unknown> | undefined
  return result || output || input || payload
}

export default function RecordsPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [detail, setDetail] = useState<TaskDetail | null>(null)

  const loadItems = async () => {
    const res = await api.get<HistoryItem[]>('/tasks/recent')
    setItems(res.data)
  }

  useEffect(() => {
    loadItems().catch(() => undefined)
  }, [])

  const openDetail = async (item: HistoryItem) => {
    if (!item.id) return
    const res = await api.get<TaskDetail>(`/tasks/${item.id}`)
    setDetail(res.data)
  }

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={8}>
        <Card title="任务历史" bordered={false} className="workspace-card records-panel">
          <List dataSource={items} locale={{ emptyText: <Empty description="暂无历史记录" /> }} renderItem={(item) => (
            <List.Item className="record-row" onClick={() => openDetail(item)}>
              <List.Item.Meta
                title={<Space wrap><Tag>{typeLabel(item.type)}</Tag><Text strong>{item.title}</Text></Space>}
                description={(
                  <Space direction="vertical" size={2}>
                    <Text type="secondary">{item.summary}</Text>
                    <Text type="secondary">{dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}</Text>
                  </Space>
                )}
              />
            </List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} xl={16}>
        <Card title="历史详情" bordered={false} className="workspace-card records-panel">
          {detail ? (
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="类型"><Tag>{typeLabel(detail.type)}</Tag></Descriptions.Item>
                <Descriptions.Item label="标题">{detail.title}</Descriptions.Item>
                <Descriptions.Item label="摘要">{detail.summary}</Descriptions.Item>
                <Descriptions.Item label="时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
              </Descriptions>
              <Card size="small" title="本次输出">
                <pre className="document-preview">{JSON.stringify(readablePayload(detail.payload), null, 2)}</pre>
              </Card>
              <Paragraph type="secondary">
                这里保留的是用户可回看的任务结果和关键输入输出；底层工具调用字段仅作为排查模型、检索和文件选择问题的依据。
              </Paragraph>
            </Space>
          ) : (
            <Empty description="点击左侧记录查看历史问答、任务卡、填写建议或审核结果" />
          )}
        </Card>
      </Col>
    </Row>
  )
}
