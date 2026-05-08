import { useEffect, useState } from 'react'
import { Card, Row, Col, List, Progress, Tag, Table, Skeleton, Empty, message } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useParams } from 'react-router-dom'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import type { Student, KnowledgeState, ExamRecord, WeakKnowledge } from '@/types'

const levelColor: Record<string, string> = {
  excellent: 'green',
  good: 'blue',
  medium: 'orange',
  weak: 'red',
}

const levelText: Record<string, string> = {
  excellent: '优秀',
  good: '良好',
  medium: '中等',
  weak: '薄弱',
}

const StudentProfile: React.FC = () => {
  const { studentId } = useParams<{ studentId: string }>()
  const { user } = useAuthStore()
  const [loading, setLoading] = useState(true)
  const [student, setStudent] = useState<Student | null>(null)
  const [knowledgeState, setKnowledgeState] = useState<KnowledgeState[]>([])
  const [examRecords, setExamRecords] = useState<ExamRecord[]>([])
  const [weakKnowledges, setWeakKnowledges] = useState<WeakKnowledge[]>([])

  const id = Number(studentId) || user?.id

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      setLoading(true)
      try {
        const [studentRes, ksRes, erRes, wkRes] = await Promise.all([
          studentsApi.detail(id),
          studentsApi.knowledgeState(id),
          studentsApi.examRecords(id),
          studentsApi.weakKnowledges(id),
        ])
        setStudent(studentRes)
        setKnowledgeState(ksRes)
        setExamRecords(erRes)
        setWeakKnowledges(wkRes)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  const radarOption = {
    radar: {
      indicator: knowledgeState.map((k) => ({
        name: k.subject,
        max: k.max_score || 100,
      })),
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: knowledgeState.map((k) => k.score),
            name: '当前掌握度',
            areaStyle: { opacity: 0.3 },
          },
        ],
      },
    ],
    tooltip: {},
  }

  const trendOption = {
    xAxis: {
      type: 'category',
      data: examRecords.map((e) => e.exam_name),
    },
    yAxis: { type: 'value', max: 100 },
    series: [
      {
        data: examRecords.map((e) => Math.round((e.score / (e.max_score || 100)) * 100)),
        type: 'line',
        smooth: true,
        areaStyle: {},
      },
    ],
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }

  const examColumns = [
    { title: '考试名称', dataIndex: 'exam_name' },
    {
      title: '得分',
      dataIndex: 'score',
      render: (s: number, record: ExamRecord) => `${s}/${record.max_score}`,
    },
    {
      title: '百分比',
      render: (_: unknown, record: ExamRecord) => (
        <Progress
          percent={Math.round((record.score / (record.max_score || 100)) * 100)}
          size="small"
          status={record.score / (record.max_score || 100) < 0.6 ? 'exception' : 'success'}
        />
      ),
    },
    { title: '排名', dataIndex: 'rank', render: (r?: number) => r ?? '-' },
    { title: '日期', dataIndex: 'date', render: (d: string) => d?.slice(0, 10) || '-' },
  ]

  if (loading) {
    return (
      <div>
        <Skeleton active />
        <Row gutter={16} style={{ marginTop: 24 }}>
          <Col xs={24} md={12}><Skeleton active /></Col>
          <Col xs={24} md={12}><Skeleton active /></Col>
        </Row>
      </div>
    )
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>
          {student?.name || '学生详情'}
          <Tag style={{ marginLeft: 12 }}>{student?.student_no}</Tag>
          <Tag>{student?.class_name}</Tag>
        </div>
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="知识点掌握度雷达图">
            {knowledgeState.length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={radarOption} style={{ height: 300 }} />
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="最近考试成绩趋势">
            {examRecords.length === 0 ? (
              <Empty description="暂无数据" />
            ) : (
              <ReactECharts option={trendOption} style={{ height: 300 }} />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="薄弱知识点 TOP5" style={{ marginTop: 16 }}>
        {weakKnowledges.length === 0 ? (
          <Empty description="暂无数据" />
        ) : (
          <List
            dataSource={weakKnowledges.slice(0, 5)}
            renderItem={(item) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span>{item.knowledge}</span>
                    <Tag color={levelColor[item.level] || 'default'}>
                      {item.mastery}% · {levelText[item.level] || item.level}
                    </Tag>
                  </div>
                  <Progress
                    percent={item.mastery}
                    status={item.mastery < 60 ? 'exception' : 'success'}
                  />
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>

      <Card title="最近考试记录" style={{ marginTop: 16 }}>
        <Table
          dataSource={examRecords}
          columns={examColumns}
          pagination={false}
          rowKey="id"
          scroll={{ x: 'max-content' }}
        />
      </Card>
    </div>
  )
}

export default StudentProfile
