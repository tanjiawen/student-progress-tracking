import { useEffect, useState } from 'react'
import {
  Card,
  Tag,
  Badge,
  Row,
  Col,
  Typography,
  Button,
  Table,
  Skeleton,
  Empty,
  message,
  Space,
} from 'antd'
import { EyeOutlined, CheckCircleOutlined, ScanOutlined, FileDoneOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { examsApi } from '@/api/exams'
import type { Exam, Question } from '@/types'

const { Title, Text } = Typography

const statusMap: Record<string, { text: string; color: string; badge: 'success' | 'processing' | 'warning' | 'default' }> = {
  processing: { text: '处理中', color: 'blue', badge: 'default' },
  ready: { text: '待OCR', color: 'orange', badge: 'warning' },
  grading: { text: '判卷中', color: 'purple', badge: 'processing' },
  graded: { text: '已判卷', color: 'green', badge: 'success' },
}

const typeMap: Record<string, string> = {
  choice: '选择题',
  fill_blank: '填空题',
  calculation: '计算题',
  essay: '解答题',
}

const ExamDetail: React.FC = () => {
  const { examId } = useParams<{ examId: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [exam, setExam] = useState<Exam | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const id = Number(examId)

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      setLoading(true)
      try {
        const [examRes, questionsRes] = await Promise.all([
          examsApi.detail(id),
          examsApi.questions(id),
        ])
        setExam(examRes)
        setQuestions(questionsRes)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  const handleStartOCR = async () => {
    setActionLoading('ocr')
    try {
      await examsApi.startOCR(id)
      message.success('OCR 任务已启动')
      const updated = await examsApi.detail(id)
      setExam(updated)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '启动失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleStartGrading = async () => {
    setActionLoading('grade')
    try {
      await examsApi.startGrading(id)
      message.success('判卷任务已启动')
      const updated = await examsApi.detail(id)
      setExam(updated)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '启动失败')
    } finally {
      setActionLoading(null)
    }
  }

  const columns = [
    {
      title: '题号',
      dataIndex: 'sequence',
      key: 'sequence',
      width: 80,
    },
    {
      title: '题型',
      dataIndex: 'type',
      key: 'type',
      render: (t: string) => <Tag>{typeMap[t] || t}</Tag>,
    },
    {
      title: '分值',
      dataIndex: 'score',
      key: 'score',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Badge
          status={s === 'graded' ? 'success' : 'processing'}
          text={s === 'graded' ? '已判卷' : '待判卷'}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Question) => (
        <Button
          icon={<EyeOutlined />}
          size="small"
          onClick={() => setSelectedQuestion(record)}
        >
          查看
        </Button>
      ),
    },
  ]

  const cfg = exam ? statusMap[exam.status] : null

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            考试详情：{exam?.title || '...'}
            {cfg && (
              <Tag color={cfg.color} style={{ marginLeft: 12 }}>
                {cfg.text}
              </Tag>
            )}
          </Title>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<ScanOutlined />}
              loading={actionLoading === 'ocr'}
              disabled={exam?.status !== 'ready'}
              onClick={handleStartOCR}
            >
              启动 OCR
            </Button>
            <Button
              icon={<FileDoneOutlined />}
              loading={actionLoading === 'grade'}
              disabled={exam?.status !== 'ready' && exam?.status !== 'processing'}
              onClick={handleStartGrading}
            >
              启动判卷
            </Button>
            <Button onClick={() => navigate('/grading')}>查看结果</Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          <Card title="题目列表">
            {loading ? (
              <Skeleton active />
            ) : questions.length === 0 ? (
              <Empty description="暂无题目" />
            ) : (
              <Table
                columns={columns}
                dataSource={questions}
                rowKey="id"
                pagination={false}
                scroll={{ x: 'max-content' }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="作答预览">
            {selectedQuestion ? (
              <div>
                <p>
                  <strong>题目：</strong>
                  {selectedQuestion.content}
                </p>
                <p>
                  <strong>分值：</strong>
                  {selectedQuestion.score} 分
                </p>
                {selectedQuestion.answer && (
                  <p>
                    <strong>标准答案：</strong>
                    <Text type="success">{selectedQuestion.answer}</Text>
                  </p>
                )}
                {selectedQuestion.knowledge_points && selectedQuestion.knowledge_points.length > 0 && (
                  <p>
                    <strong>知识点：</strong>
                    {selectedQuestion.knowledge_points.map((kp) => (
                      <Tag key={kp}>{kp}</Tag>
                    ))}
                  </p>
                )}
                {selectedQuestion.status === 'graded' ? (
                  <div
                    style={{
                      marginTop: 16,
                      padding: 16,
                      background: '#f6ffed',
                      borderRadius: 8,
                    }}
                  >
                    <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                    <Text>该题已判卷</Text>
                  </div>
                ) : (
                  <div
                    style={{
                      marginTop: 16,
                      padding: 16,
                      background: '#fff7e6',
                      borderRadius: 8,
                    }}
                  >
                    <Text type="warning">该题待判卷</Text>
                  </div>
                )}
              </div>
            ) : (
              <Empty description="请点击左侧题目查看详情" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default ExamDetail
