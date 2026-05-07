import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Tag,
  Button,
  Drawer,
  List,
  Skeleton,
  Empty,
  message,
  Typography,
} from 'antd'
import { EyeOutlined, DownloadOutlined } from '@ant-design/icons'
import { studentsApi } from '@/api/students'
import type { Report } from '@/types'

const { Title, Text } = Typography

const typeMap: Record<string, string> = {
  monthly: '月度报告',
  exam: '考试报告',
  comprehensive: '综合报告',
}

const typeColor: Record<string, string> = {
  monthly: 'blue',
  exam: 'green',
  comprehensive: 'purple',
}

const ReportView: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [reports, setReports] = useState<Report[]>([])
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [studentId] = useState<number>(1)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await studentsApi.reports(studentId)
        setReports(res)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [studentId])

  const columns = [
    { title: '报告类型', dataIndex: 'type', key: 'type', render: (t: string) => <Tag color={typeColor[t] || 'default'}>{typeMap[t] || t}</Tag> },
    { title: '生成时间', dataIndex: 'generated_at', key: 'generated_at', render: (d: string) => d?.slice(0, 16).replace('T', ' ') || '-' },
    { title: '总分', dataIndex: 'total_score', key: 'total_score' },
    { title: '排名', dataIndex: 'rank', key: 'rank' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Report) => (
        <Button
          icon={<EyeOutlined />}
          size="small"
          onClick={() => {
            setSelectedReport(record)
            setDrawerOpen(true)
          }}
        >
          查看
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Card title="学情报告">
        {loading ? (
          <Skeleton active />
        ) : reports.length === 0 ? (
          <Empty description="暂无报告" />
        ) : (
          <Table columns={columns} dataSource={reports} rowKey="id" pagination={{ pageSize: 10 }} />
        )}
      </Card>

      <Drawer
        title="报告详情"
        width={600}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Button icon={<DownloadOutlined />} onClick={() => message.info('导出功能开发中')}>
            导出 PDF
          </Button>
        }
      >
        {selectedReport && (
          <div>
            <Title level={5}>总体评价</Title>
            <Card style={{ marginBottom: 16 }}>
              <Text>{selectedReport.evaluation}</Text>
            </Card>

            <Title level={5}>薄弱知识点</Title>
            <Card style={{ marginBottom: 16 }}>
              {selectedReport.weak_knowledges.length === 0 ? (
                <Empty description="暂无" />
              ) : (
                <List
                  dataSource={selectedReport.weak_knowledges}
                  renderItem={(item) => (
                    <List.Item>
                      <Tag color="red">{item}</Tag>
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Title level={5}>错误模式</Title>
            <Card style={{ marginBottom: 16 }}>
              {selectedReport.error_patterns.length === 0 ? (
                <Empty description="暂无" />
              ) : (
                <List
                  dataSource={selectedReport.error_patterns}
                  renderItem={(item) => (
                    <List.Item>
                      <Tag color="orange">{item}</Tag>
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Title level={5}>学习建议</Title>
            <Card style={{ marginBottom: 16 }}>
              {selectedReport.suggestions.length === 0 ? (
                <Empty description="暂无" />
              ) : (
                <List
                  dataSource={selectedReport.suggestions}
                  renderItem={(item) => (
                    <List.Item>
                      <Text>• {item}</Text>
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Title level={5}>目标分数</Title>
            <Card>
              <Text style={{ fontSize: 24, fontWeight: 600, color: '#1890ff' }}>
                {selectedReport.target_score} 分
              </Text>
            </Card>
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default ReportView
