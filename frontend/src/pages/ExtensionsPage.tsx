// 扩展能力页面：展示智能体图谱、本地模型建议和可导出的训练数据。
import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Descriptions, List, Row, Space, Steps, Tabs, Tag, Typography, message } from 'antd'
import { ApiOutlined, BranchesOutlined, CloudServerOutlined, DatabaseOutlined, DownloadOutlined, PartitionOutlined } from '@ant-design/icons'
import api from '../api'

const { Paragraph, Text } = Typography

interface AgentGraph {
  nodes: Array<{ id: string; name: string; role: string }>
  edges: string[][]
  langgraph_ready: boolean
  note: string
}

const MODEL_STEPS = [
  { title: '启动国产模型服务', description: '使用 vLLM、Ollama、LMDeploy 或百炼/火山兼容服务暴露 OpenAI-compatible /v1 接口。' },
  { title: '修改 backend/.env', description: '配置 OPENAI_BASE_URL、OPENAI_API_KEY、LLM_MODEL，并保持 DEMO_MODE=false。' },
  { title: '重启后端', description: '重新运行 uvicorn，使模型配置生效。' },
  { title: '执行连通性检查', description: '点击本页“检查模型接入”，确认 base_url、model、demo_mode 状态。' },
]

export default function ExtensionsPage() {
  const [modelCheck, setModelCheck] = useState<Record<string, unknown> | null>(null)
  const [agentGraph, setAgentGraph] = useState<AgentGraph | null>(null)
  const [scenarioTemplates, setScenarioTemplates] = useState<Record<string, string[]> | null>(null)

  const checkModel = async () => {
    const res = await api.get<Record<string, unknown>>('/extensions/model/check')
    setModelCheck(res.data)
    message.success('模型接入状态已刷新')
  }

  const loadAgentGraph = async () => {
    const res = await api.get<AgentGraph>('/extensions/agent-graph')
    setAgentGraph(res.data)
  }

  const loadScenarioTemplates = async () => {
    const res = await api.get<Record<string, string[]>>('/extensions/scenario-templates')
    setScenarioTemplates(res.data)
  }

  useEffect(() => {
    checkModel().catch(() => undefined)
    loadAgentGraph().catch(() => undefined)
    loadScenarioTemplates().catch(() => undefined)
  }, [])

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={15}>
        <Card title="拓展中心" bordered={false} className="workspace-card records-panel">
          <Tabs
            items={[
              {
                key: 'model',
                label: '模型接入',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Alert
                      type="info"
                      showIcon
                      message="这里不是验收说明，而是模型切换操作台。当前后端已经采用 OpenAI-compatible 适配方式，可接 DeepSeek、Qwen、百炼、火山或本地国产模型服务。"
                    />
                    <Space wrap>
                      <Button type="primary" icon={<ApiOutlined />} onClick={checkModel}>检查模型接入</Button>
                      <Button href="http://localhost:8000/api/extensions/local-model-guide" target="_blank">查看本地模型接入文档</Button>
                    </Space>
                    <Descriptions bordered size="small" column={1}>
                      {Object.entries(modelCheck || {}).map(([key, value]) => (
                        <Descriptions.Item key={key} label={key}>{String(value)}</Descriptions.Item>
                      ))}
                    </Descriptions>
                    <Steps direction="vertical" size="small" items={MODEL_STEPS} />
                  </Space>
                ),
              },
              {
                key: 'agents',
                label: 'Agent 编排',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Alert type="info" showIcon message="主链路已按 Intent/RAG/Audit/Form/Workflow/Record 分层。这里展示可替换为 LangGraph 的节点和调用关系。" />
                    <Button type="primary" icon={<BranchesOutlined />} onClick={loadAgentGraph}>刷新编排图</Button>
                    <List dataSource={agentGraph?.nodes || []} renderItem={(item) => (
                      <List.Item>
                        <List.Item.Meta title={<Space><Text strong>{item.name}</Text><Tag>{item.id}</Tag></Space>} description={item.role} />
                      </List.Item>
                    )} />
                    <Card size="small" title="调用关系">
                      <Space wrap>{(agentGraph?.edges || []).map((edge) => <Tag key={edge.join('-')}>{`${edge[0]} -> ${edge[1]}`}</Tag>)}</Space>
                    </Card>
                  </Space>
                ),
              },
              {
                key: 'datasets',
                label: '数据集导出',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Alert type="success" showIcon message="这里用于生成数据制作和微调样本，不直接影响主链路运行。导出的 FAQ、OCR 字段、规则样本可导入百炼、飞桨或本地训练流程。" />
                    <Space wrap>
                      <Button icon={<DownloadOutlined />} href="http://localhost:8000/api/extensions/datasets/faq.jsonl" target="_blank">导出 FAQ 样本</Button>
                      <Button icon={<DownloadOutlined />} href="http://localhost:8000/api/extensions/datasets/ocr-fields.jsonl" target="_blank">导出 OCR 字段样本</Button>
                      <Button icon={<DownloadOutlined />} href="http://localhost:8000/api/extensions/datasets/rules.json" target="_blank">导出规则样本</Button>
                    </Space>
                    <List
                      size="small"
                      dataSource={[
                        'FAQ 样本：用于制度问答、截止时间、材料要求、流程说明微调。',
                        'OCR 字段样本：用于姓名、联系方式、项目名、学院、表格键值对抽取。',
                        '规则样本：用于必填项、人数范围、截止时间、材料缺失、风险建议。',
                      ]}
                      renderItem={(item) => <List.Item>{item}</List.Item>}
                    />
                  </Space>
                ),
              },
              {
                key: 'scenarios',
                label: '场景扩展',
                children: (
                  <Space direction="vertical" size={16} style={{ width: '100%' }}>
                    <Alert type="info" showIcon message="系统不再限制只能使用五个场景。五个是预置演示场景，工作台支持输入其他场景名称，并复用同一条问答、抽取、审核、表单、待办链路。" />
                    <Button type="primary" icon={<PartitionOutlined />} onClick={loadScenarioTemplates}>刷新场景模板</Button>
                    <List dataSource={Object.entries(scenarioTemplates || {})} renderItem={([name, steps]) => (
                      <List.Item>
                        <List.Item.Meta title={name} description={<Space wrap>{steps.map((step) => <Tag key={step}>{step}</Tag>)}</Space>} />
                      </List.Item>
                    )} />
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      </Col>

      <Col xs={24} xl={9}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card title="操作方案" bordered={false} className="workspace-card">
            <List
              size="small"
              dataSource={[
                '先在“模型接入”确认真实模型或本地国产模型服务可用。',
                '在“Agent 编排”确认主链路节点，后续可替换为 LangGraph StateGraph。',
                '在“数据集导出”下载样本，作为百炼、飞桨或本地微调的数据起点。',
                '在“智能办理”使用五个预置场景或输入其他场景，功能链路保持一致。',
              ]}
              renderItem={(item) => <List.Item>{item}</List.Item>}
            />
          </Card>
          <Card title="接口入口" bordered={false} className="workspace-card">
            <List
              size="small"
              dataSource={[
                ['模型检查', 'GET /api/extensions/model/check', <CloudServerOutlined />],
                ['Agent 编排', 'GET /api/extensions/agent-graph', <BranchesOutlined />],
                ['FAQ 样本', 'GET /api/extensions/datasets/faq.jsonl', <DatabaseOutlined />],
                ['OCR 样本', 'GET /api/extensions/datasets/ocr-fields.jsonl', <DatabaseOutlined />],
                ['规则样本', 'GET /api/extensions/datasets/rules.json', <DatabaseOutlined />],
              ]}
              renderItem={(item) => <List.Item><Space>{item[2]}<Text>{item[0]}</Text><Text code>{item[1]}</Text></Space></List.Item>}
            />
          </Card>
        </Space>
      </Col>
    </Row>
  )
}
