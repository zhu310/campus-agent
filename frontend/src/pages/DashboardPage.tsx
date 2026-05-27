// 首页数据看板：展示项目能力、核心指标和场景入口。
import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Col, List, Row, Space, Statistic, Tag, Typography } from 'antd'
import {
  AuditOutlined, CheckCircleOutlined, ClockCircleOutlined, FileSearchOutlined,
  FormOutlined, OrderedListOutlined, RocketOutlined, SettingOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import api from '../api'
import { HistoryItem, SummaryResponse } from '../types'

const { Title, Paragraph, Text } = Typography

interface Props {
  onStart: (scenario?: string) => void
}

const SCENARIO_CARDS = [
  { title: '比赛报名', desc: '通知问答、报名材料核验、表单预填、截止提醒', icon: <FileSearchOutlined /> },
  { title: '请假审批', desc: '制度咨询、证明材料识别、请假单预填、审批待办', icon: <CheckCircleOutlined /> },
  { title: '奖助学金申请', desc: '资格规则问答、材料缺失识别、申请表预填', icon: <AuditOutlined /> },
  { title: '报销办理', desc: '票据材料核验、金额字段提取、报销流程计划', icon: <FormOutlined /> },
  { title: '社团活动审批', desc: '活动通知解析、风险项审核、流程清单生成', icon: <OrderedListOutlined /> },
  { title: '其他场景', desc: '自定义业务名称，复用问答、抽取、审核、表单、待办链路', icon: <SettingOutlined /> },
]

export default function DashboardPage({ onStart }: Props) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])

  useEffect(() => {
    Promise.all([
      api.get<SummaryResponse>('/dashboard/summary'),
      api.get<HistoryItem[]>('/tasks/recent'),
    ]).then(([summaryRes, historyRes]) => {
      setSummary(summaryRes.data)
      setHistory(historyRes.data)
    }).catch(() => undefined)
  }, [])

  const metrics = useMemo(() => summary?.metrics || [], [summary])

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <section className="dashboard-hero">
        <div>
          <Space wrap>
            <Tag color="cyan">高校智能办理平台</Tag>
            <Tag color={summary?.demo_mode ? 'orange' : 'green'}>{summary?.demo_mode ? '演示降级模式' : '真实模型模式'}</Tag>
          </Space>
          <Title className="dashboard-title">智审通 Campus Copilot</Title>
          <Paragraph className="dashboard-desc">
            面向高校行政与学生事务的智能审批与材料办理平台。统一上传制度、通知和办理材料，按需完成 RAG 问答、字段抽取、规则审核、表单预填、下一步计划与记录留痕。
          </Paragraph>
          <Space wrap>
            <Button type="primary" size="large" icon={<RocketOutlined />} onClick={() => onStart('比赛报名')}>进入智能办理</Button>
            <Button size="large" href="http://localhost:8000/api/exports/demo/latest" target="_blank">导出演示摘要</Button>
          </Space>
        </div>
        <div className="dashboard-value">
          <Paragraph>减少重复咨询：通过制度/通知检索，答案带引用依据。</Paragraph>
          <Paragraph>减少漏材料：材料字段抽取后自动识别缺失项和风险项。</Paragraph>
          <Paragraph>提升办理效率：同一材料可继续预填表单并生成下一步清单。</Paragraph>
        </div>
      </section>

      <Row gutter={[16, 16]}>
        {metrics.map((item, index) => (
          <Col xs={24} md={12} xl={6} key={item.label}>
            <Card bordered={false} className="metric-card">
              <Statistic
                title={item.label}
                value={item.value}
                prefix={[<ClockCircleOutlined />, <AuditOutlined />, <FileSearchOutlined />, <FormOutlined />][index % 4]}
              />
              <Text type="secondary">{item.trend}</Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card title="快捷场景" bordered={false} className="workspace-card dashboard-section-card">
            <Row gutter={[12, 12]}>
              {SCENARIO_CARDS.map((item) => (
                <Col xs={24} md={12} xl={8} key={item.title}>
                  <button className="scenario-card" onClick={() => onStart(item.title)}>
                    <span className="scenario-card-icon">{item.icon}</span>
                    <span className="scenario-card-title">{item.title}</span>
                    <span className="scenario-card-desc">{item.desc}</span>
                  </button>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card title="最近任务" bordered={false} className="workspace-card dashboard-section-card">
            <List
              dataSource={history.slice(0, 6)}
              locale={{ emptyText: '暂无办理记录' }}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Space><Tag>{item.type}</Tag><Text strong>{item.title}</Text></Space>}
                    description={<Space direction="vertical" size={2}><Text type="secondary">{item.summary}</Text><Text type="secondary">{dayjs(item.created_at).format('MM-DD HH:mm')}</Text></Space>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
