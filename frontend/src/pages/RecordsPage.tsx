// 任务记录页面：按时间展示历史操作，并可查看结构化详情。
import { useEffect, useState } from 'react'
import { Card, Col, Descriptions, Empty, List, Row, Space, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import api from '../api'
import { HistoryItem, TaskDetail } from '../types'

const { Text, Paragraph } = Typography

export default function RecordsPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [detail, setDetail] = useState<TaskDetail | null>(null)

  useEffect(() => {
    api.get<HistoryItem[]>('/tasks/recent').then((res) => setItems(res.data)).catch(() => undefined)
  }, [])

  const openDetail = async (item: HistoryItem) => {
    if (!item.id) return
    const res = await api.get<TaskDetail>(`/tasks/${item.id}`)
    setDetail(res.data)
  }

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={9}>
        <Card title="审核与办理记录" bordered={false} className="workspace-card records-panel">
          <List dataSource={items} locale={{ emptyText: <Empty description="暂无办理记录" /> }} renderItem={(item) => (
            <List.Item className="record-row" onClick={() => openDetail(item)}>
              <List.Item.Meta
                title={<Space><Tag>{item.type}</Tag><Text strong>{item.title}</Text></Space>}
                description={<Space direction="vertical" size={2}><Text type="secondary">{item.summary}</Text><Text type="secondary">{dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}</Text></Space>}
              />
            </List.Item>
          )} />
        </Card>
      </Col>
      <Col xs={24} xl={15}>
        <Card title="记录详情" bordered={false} className="workspace-card records-panel">
          {detail ? (
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="类型">{detail.type}</Descriptions.Item>
                <Descriptions.Item label="标题">{detail.title}</Descriptions.Item>
                <Descriptions.Item label="摘要">{detail.summary}</Descriptions.Item>
                <Descriptions.Item label="时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
              </Descriptions>
              <pre className="document-preview">{JSON.stringify(detail.payload, null, 2)}</pre>
            </Space>
          ) : (
            <Paragraph type="secondary">点击左侧记录查看问答、审核、表单、待办或工具留痕详情。</Paragraph>
          )}
        </Card>
      </Col>
    </Row>
  )
}
