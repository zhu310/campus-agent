// 系统设置页：面向管理员/演示人员查看模型接入状态和切换方案。
import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Descriptions, List, Radio, Row, Space, Tag, Typography, message } from 'antd'
import { ApiOutlined, CloudServerOutlined, ReloadOutlined } from '@ant-design/icons'
import api from '../api'

const { Paragraph, Text, Title } = Typography

const PROVIDERS = {
  deepseek: {
    name: 'DeepSeek API',
    baseUrl: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    description: '适合比赛现场快速接入云端模型，延迟和稳定性取决于网络。',
  },
  qwen_local: {
    name: '本地 Qwen',
    baseUrl: 'http://127.0.0.1:8001/v1',
    model: 'qwen2.5-7b-instruct',
    description: '适合离线或内网演示，可通过 vLLM、Ollama、LMDeploy 暴露 OpenAI-compatible 接口。',
  },
  custom: {
    name: '自定义 OpenAI-compatible',
    baseUrl: 'https://your-service.example.com/v1',
    model: 'your-model-name',
    description: '适配百炼、火山、硅基流动、LMDeploy、vLLM 等兼容 OpenAI API 的模型服务。',
  },
}

export default function ExtensionsPage() {
  const [modelCheck, setModelCheck] = useState<Record<string, unknown> | null>(null)
  const [provider, setProvider] = useState<keyof typeof PROVIDERS>('deepseek')

  const checkModel = async () => {
    const res = await api.get<Record<string, unknown>>('/extensions/model/check')
    setModelCheck(res.data)
    const active = String(res.data.active_provider || 'deepseek') as keyof typeof PROVIDERS
    if (active in PROVIDERS) setProvider(active)
    message.success('模型状态已刷新')
  }

  const applyProvider = async () => {
    try {
      const res = await api.post<Record<string, unknown>>('/extensions/model/provider', { provider })
      setModelCheck(res.data)
      message.success(`已切换到 ${PROVIDERS[provider].name}`)
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '模型切换失败，请检查 backend/.env 配置')
    }
  }

  useEffect(() => {
    checkModel().catch(() => undefined)
  }, [])

  const selected = PROVIDERS[provider]

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={15}>
        <Card title="系统设置" bordered={false} className="workspace-card records-panel">
          <Space direction="vertical" size={18} style={{ width: '100%' }}>
            <Alert
              type="info"
              showIcon
              message="模型服务由后端环境变量控制，前端只展示状态和配置建议，不在浏览器保存 API Key。"
            />
            <Space wrap>
              <Button type="primary" icon={<ReloadOutlined />} onClick={checkModel}>测试当前连接</Button>
              <Button icon={<CloudServerOutlined />} onClick={applyProvider}>应用模型</Button>
              <Button href="http://localhost:8000/api/extensions/local-model-guide" target="_blank">本地模型接入说明</Button>
            </Space>
            <Descriptions title="当前后端模型状态" bordered size="small" column={1}>
              {Object.entries(modelCheck || {}).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {key.includes('api_key') ? (value ? '已配置' : '未配置') : String(value)}
                </Descriptions.Item>
              ))}
            </Descriptions>

            <Title level={5}>切换方案</Title>
            <Radio.Group value={provider} onChange={(event) => setProvider(event.target.value)} optionType="button" buttonStyle="solid">
              <Radio.Button value="deepseek">DeepSeek API</Radio.Button>
              <Radio.Button value="qwen_local">本地 Qwen</Radio.Button>
              <Radio.Button value="custom">自定义服务</Radio.Button>
            </Radio.Group>
            <Card size="small">
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Space><CloudServerOutlined /><Text strong>{selected.name}</Text><Tag>OpenAI-compatible</Tag></Space>
                <Paragraph>{selected.description}</Paragraph>
                <Descriptions size="small" bordered column={1}>
                  <Descriptions.Item label="OPENAI_BASE_URL"><Text code>{selected.baseUrl}</Text></Descriptions.Item>
                  <Descriptions.Item label="LLM_MODEL"><Text code>{selected.model}</Text></Descriptions.Item>
                  <Descriptions.Item label="DEMO_MODE"><Text code>false</Text></Descriptions.Item>
                </Descriptions>
                <Alert type="warning" showIcon message="点击“应用模型”后才会切换后端后续 LLM 调用；如果提示未配置，请先在 backend/.env 中补齐对应 API Key。" />
              </Space>
            </Card>
          </Space>
        </Card>
      </Col>
      <Col xs={24} xl={9}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card title="为什么不在这里保存 Key" bordered={false} className="workspace-card">
            <List
              size="small"
              dataSource={[
                'API Key 不应明文保存在浏览器中，避免被复制、截屏或泄露。',
                '可以在 backend/.env 同时配置 DeepSeek 和本地 Qwen 的 Key。',
                '前端只发送 provider 名称，后端用对应 .env 配置切换运行时模型。',
              ]}
              renderItem={(item) => <List.Item>{item}</List.Item>}
            />
          </Card>
          <Card title="建议配置流程" bordered={false} className="workspace-card">
            <List
              size="small"
              dataSource={[
                '选择 DeepSeek API 或本地 Qwen 方案。',
                '把 Base URL、模型名和 API Key 写入 backend/.env。',
                '重启 FastAPI 后端。',
                '回到本页点击“测试当前连接”。',
                '再进入智能办理页面上传通知并提问。',
              ]}
              renderItem={(item, index) => <List.Item><Space><Tag>{index + 1}</Tag>{item}</Space></List.Item>}
            />
          </Card>
          <Card title="保留的开发者入口" bordered={false} className="workspace-card">
            <Space direction="vertical">
              <Button icon={<ApiOutlined />} href="http://localhost:8000/docs" target="_blank">打开 API 文档</Button>
            </Space>
          </Card>
        </Space>
      </Col>
    </Row>
  )
}
