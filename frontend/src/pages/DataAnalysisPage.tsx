// 数据分析智能体页面：上传 Excel/CSV，展示结构化摘要和智能洞察。
import { useState } from 'react'
import { Alert, Button, Card, Col, Descriptions, Empty, Input, Row, Space, Table, Tag, Typography, Upload, message } from 'antd'
import { BarChartOutlined, FileExcelOutlined, ThunderboltOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import api from '../api'
import type { DataAnalysisBlock, DataAnalysisResponse } from '../types'

const { Dragger } = Upload
const { Paragraph, Text, Title } = Typography

const DEFAULT_TASK = '请分析这批校园业务数据的整体情况、异常和后续建议'

export default function DataAnalysisPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [task, setTask] = useState(DEFAULT_TASK)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DataAnalysisResponse | null>(null)

  const analyze = async () => {
    const files = fileList.map((file) => file.originFileObj).filter(Boolean)
    if (!files.length) {
      message.warning('请先上传 Excel 或 CSV 文件')
      return
    }
    const form = new FormData()
    files.forEach((file) => form.append('files', file as File))
    form.append('task', task)
    setLoading(true)
    try {
      const res = await api.post<DataAnalysisResponse>('/analytics/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      message.success('数据分析完成')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '数据分析失败')
    } finally {
      setLoading(false)
    }
  }

  const activeBlock = result?.blocks[0]
  const previewColumns = activeBlock
    ? Object.keys(activeBlock.preview[0] || {}).map((key) => ({
        title: key,
        dataIndex: key,
        key,
        ellipsis: true,
        render: (value: unknown) => String(value ?? ''),
      }))
    : []

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={9}>
        <Card title={<Space><BarChartOutlined />数据分析智能体</Space>} bordered={false} className="workspace-card records-panel">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert
              type="info"
              showIcon
              message="支持上传 Excel/CSV，后端会自动识别表格数据块并生成数据体检、字段摘要和分析建议。"
            />
            <Dragger
              multiple
              beforeUpload={() => false}
              fileList={fileList}
              accept=".xlsx,.xls,.csv"
              onChange={({ fileList: nextList }) => setFileList(nextList)}
            >
              <p className="ant-upload-drag-icon"><FileExcelOutlined /></p>
              <p className="ant-upload-text">拖拽或点击上传表格文件</p>
              <p className="ant-upload-hint">可一次上传多个文件，适合报名统计、材料清单、任务台账等场景。</p>
            </Dragger>
            <Input.TextArea
              rows={5}
              value={task}
              onChange={(event) => setTask(event.target.value)}
              placeholder="输入本次数据分析目标"
            />
            <Button type="primary" icon={<ThunderboltOutlined />} loading={loading} onClick={analyze} block>
              开始分析
            </Button>
          </Space>
        </Card>
      </Col>
      <Col xs={24} xl={15}>
        <Card title="分析结果" bordered={false} className="workspace-card records-panel">
          {!result ? (
            <Empty description="上传表格后查看分析结果" />
          ) : (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Descriptions size="small" bordered column={3}>
                <Descriptions.Item label="数据块">{result.block_count}</Descriptions.Item>
                <Descriptions.Item label="文件数">{result.files.length}</Descriptions.Item>
                <Descriptions.Item label="模式">{result.fallback_used ? '规则分析' : '模型增强'}</Descriptions.Item>
              </Descriptions>
              <Card size="small" title="智能洞察">
                <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{result.insights}</Paragraph>
              </Card>
              <Title level={5}>数据块概览</Title>
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                {result.blocks.map((block: DataAnalysisBlock) => (
                  <Card size="small" key={block.key}>
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <Space wrap>
                        <Text strong>{block.key}</Text>
                        <Tag>{block.row_count} 行</Tag>
                        <Tag>{block.column_count} 列</Tag>
                        <Tag color={block.missing_rate > 0.15 ? 'orange' : 'green'}>缺失率 {(block.missing_rate * 100).toFixed(1)}%</Tag>
                      </Space>
                      <Space wrap>
                        {block.columns.slice(0, 8).map((column) => (
                          <Tag key={column.name}>{column.name} · {column.type}</Tag>
                        ))}
                      </Space>
                    </Space>
                  </Card>
                ))}
              </Space>
              {activeBlock && (
                <>
                  <Title level={5}>首个数据块预览</Title>
                  <Table
                    size="small"
                    rowKey={(_, index) => String(index)}
                    columns={previewColumns}
                    dataSource={activeBlock.preview}
                    pagination={false}
                    scroll={{ x: true }}
                  />
                </>
              )}
            </Space>
          )}
        </Card>
      </Col>
    </Row>
  )
}
