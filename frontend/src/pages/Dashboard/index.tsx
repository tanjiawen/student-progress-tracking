import { useEffect, useState } from 'react'
import {
  Card,
  Statistic,
  Table,
  Tag,
  Row,
  Col,
  Skeleton,
  Empty,
  Button,
  message,
} from 'antd'
import {
  FileTextOutlined,
  CheckCircleOutlined,
  TeamOutlined,
  ExclamationCircleOutlined,
  UploadOutlined,
  BarChartOutlined,
  FormOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { examsApi } from '@/api/exams'
import { classesApi } from '@/api/classes'
import type { Exam } from '@/types'

const statusMap: Record<string, { text: string; color: string }> = {
  processing: { text: '处理中', color: 'blue' },
  ready: { text: '待OCR', color: 'orange' },
  grading: { text: '判卷中', color: 'purple' },
  graded: { text: '已判卷', color: 'green' },
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [exams, setExams] = useState<Exam[]>([])
  const [classCount, setClassCount] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [examsRes, classesRes] = await Promise.all([
          examsApi.list(),
          classesApi.list(),
        ])
        const examList = examsRes.items || []
        setExams(examList)
        setClassCount(classesRes.length)
        setPendingCount(
          examList.filter((e) => e.status === 'ready' || e.status === 'grading').length
        )
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const stats = [
    {
      title: '班级数量',
      value: classCount,
      icon: <TeamOutlined />,
      color: '#3f8600',
    },
    {
      title: '最近考试',
      value: exams.length,
      icon: <FileTextOutlined />,
      color: '#1890ff',
    },
    {
      title: '待判卷',
      value: pendingCount,
      icon: <ExclamationCircleOutlined />,
      color: '#cf1322',
    },
    {
      title: '已判卷',
      value: exams.filter((e) => e.status === 'graded').length,
      icon: <CheckCircleOutlined />,
      color: '#3f8600',
    },
  ]

  const examColumns = [
    { title: '考试名称', dataIndex: 'title', key: 'title' },
    { title: '学科', dataIndex: 'subject', key: 'subject' },
    { title: '班级', dataIndex: 'class_name', key: 'class_name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => {
        const cfg = statusMap[s] || { text: s, color: 'default' }
        return <Tag color={cfg.color}>{cfg.text}</Tag>
      },
    },
    {
      title: '日期',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => d?.slice(0, 10) || '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Exam) => (
        <Button type="link" size="small" onClick={() => navigate(`/exams/${record.id}`)}>
          查看
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {stats.map((s) => (
          <Col xs={24} sm={12} md={6} key={s.title}>
            <Card>
              {loading ? (
                <Skeleton active paragraph={false} />
              ) : (
                <Statistic
                  title={s.title}
                  value={s.value}
                  valueStyle={{ color: s.color }}
                  prefix={s.icon}
                />
              )}
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/exams')}>
            <div style={{ textAlign: 'center' }}>
              <UploadOutlined style={{ fontSize: 32, color: '#1890ff' }} />
              <div style={{ marginTop: 8, fontWeight: 500 }}>上传试卷</div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/reports')}>
            <div style={{ textAlign: 'center' }}>
              <BarChartOutlined style={{ fontSize: 32, color: '#52c41a' }} />
              <div style={{ marginTop: 8, fontWeight: 500 }}>查看报告</div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable onClick={() => navigate('/exercise')}>
            <div style={{ textAlign: 'center' }}>
              <FormOutlined style={{ fontSize: 32, color: '#faad14' }} />
              <div style={{ marginTop: 8, fontWeight: 500 }}>生成练习</div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="最近考试">
        {loading ? (
          <Skeleton active />
        ) : exams.length === 0 ? (
          <Empty description="暂无考试记录" />
        ) : (
          <Table
            columns={examColumns}
            dataSource={exams}
            pagination={{ pageSize: 10 }}
            rowKey="id"
          />
        )}
      </Card>
    </div>
  )
}

export default Dashboard
