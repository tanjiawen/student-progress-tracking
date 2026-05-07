import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Tag,
  Button,
  InputNumber,
  Select,
  Row,
  Col,
  Typography,
  Space,
  message,
  Skeleton,
  Empty,
  Modal,
} from 'antd'
import { CheckOutlined, RollbackOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { GradingItem } from '@/types'

const { Title, Text } = Typography

const mockGradingData: GradingItem[] = [
  {
    question_id: 1,
    student_id: 101,
    student_name: '张三',
    answer_text: '选 C',
    ai_score: 3,
    ai_comment: '答案正确',
    standard_answer: 'C',
    final_score: 3,
    error_type: '',
    status: 'pending',
  },
  {
    question_id: 2,
    student_id: 101,
    student_name: '张三',
    answer_text: 'x=2',
    ai_score: 2,
    ai_comment: '答案不完整，缺少 x=3',
    standard_answer: 'x=2 或 x=3',
    final_score: 2,
    error_type: 'missing_step',
    status: 'pending',
  },
  {
    question_id: 3,
    student_id: 102,
    student_name: '李四',
    answer_text: '1/3',
    ai_score: 6,
    ai_comment: '计算正确',
    standard_answer: '1/3',
    final_score: 6,
    error_type: '',
    status: 'pending',
  },
]

const errorTypeOptions = [
  { value: '', label: '无' },
  { value: 'calculation_error', label: '计算错误' },
  { value: 'concept_error', label: '概念错误' },
  { value: 'missing_step', label: '步骤遗漏' },
  { value: 'formula_error', label: '公式错误' },
  { value: 'logic_break', label: '逻辑断裂' },
]

const GradingReview: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<GradingItem[]>([])
  const [selected, setSelected] = useState<GradingItem | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  useEffect(() => {
    const timer = setTimeout(() => {
      setItems(mockGradingData)
      setLoading(false)
    }, 600)
    return () => clearTimeout(timer)
  }, [])

  const updateItem = (questionId: number, updates: Partial<GradingItem>) => {
    setItems((prev) =>
      prev.map((i) => (i.question_id === questionId ? { ...i, ...updates } : i))
    )
    if (selected?.question_id === questionId) {
      setSelected((prev) => (prev ? { ...prev, ...updates } : prev))
    }
  }

  const handleConfirm = (item: GradingItem) => {
    updateItem(item.question_id, { status: 'confirmed' })
    message.success('已确认')
  }

  const handleReject = (item: GradingItem) => {
    updateItem(item.question_id, { status: 'rejected' })
    message.info('已打回重判')
  }

  const handleBatchConfirm = () => {
    Modal.confirm({
      title: '批量确认',
      content: `确认选中的 ${selectedRowKeys.length} 条记录？`,
      onOk: () => {
        setItems((prev) =>
          prev.map((i) =>
            selectedRowKeys.includes(i.question_id) ? { ...i, status: 'confirmed' as const } : i
          )
        )
        setSelectedRowKeys([])
        message.success('批量确认完成')
      },
    })
  }

  const columns = [
    { title: '题号', dataIndex: 'question_id', width: 80 },
    { title: '学生', dataIndex: 'student_name', width: 100 },
    {
      title: 'AI 评分',
      dataIndex: 'ai_score',
      width: 90,
      render: (s: number) => <Tag color="blue">{s} 分</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => {
        const map: Record<string, { text: string; color: string }> = {
          pending: { text: '待审核', color: 'orange' },
          confirmed: { text: '已确认', color: 'green' },
          rejected: { text: '已打回', color: 'red' },
        }
        const cfg = map[s] || { text: s, color: 'default' }
        return <Tag color={cfg.color}>{cfg.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: GradingItem) => (
        <Space>
          <Button
            icon={<CheckOutlined />}
            size="small"
            type="primary"
            disabled={record.status !== 'pending'}
            onClick={() => handleConfirm(record)}
          >
            确认
          </Button>
          <Button
            icon={<RollbackOutlined />}
            size="small"
            danger
            disabled={record.status !== 'pending'}
            onClick={() => handleReject(record)}
          >
            打回
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>判卷审核工作台</Title>
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            disabled={selectedRowKeys.length === 0}
            onClick={handleBatchConfirm}
          >
            批量确认 ({selectedRowKeys.length})
          </Button>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          <Card>
            {loading ? (
              <Skeleton active />
            ) : items.length === 0 ? (
              <Empty description="暂无待审核记录" />
            ) : (
              <Table
                columns={columns}
                dataSource={items}
                rowKey="question_id"
                pagination={{ pageSize: 10 }}
                rowSelection={{
                  selectedRowKeys,
                  onChange: setSelectedRowKeys,
                }}
                onRow={(record) => ({
                  onClick: () => setSelected(record),
                  style: { cursor: 'pointer' },
                })}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="审核详情">
            {selected ? (
              <div>
                <p>
                  <strong>学生：</strong>
                  {selected.student_name}
                </p>
                <p>
                  <strong>学生作答：</strong>
                  <Text code>{selected.answer_text}</Text>
                </p>
                <p>
                  <strong>标准答案：</strong>
                  <Text type="success">{selected.standard_answer}</Text>
                </p>
                <p>
                  <strong>AI 评语：</strong>
                  {selected.ai_comment}
                </p>
                <p>
                  <strong>AI 评分：</strong>
                  {selected.ai_score} 分
                </p>
                <p>
                  <strong>最终分数：</strong>
                  <InputNumber
                    min={0}
                    max={selected.ai_score + 2}
                    value={selected.final_score}
                    onChange={(v) => updateItem(selected.question_id, { final_score: v ?? 0 })}
                    style={{ width: 100 }}
                  />
                </p>
                <p>
                  <strong>错误类型：</strong>
                  <Select
                    options={errorTypeOptions}
                    value={selected.error_type}
                    onChange={(v) => updateItem(selected.question_id, { error_type: v })}
                    style={{ width: 160 }}
                  />
                </p>
                <Space style={{ marginTop: 16 }}>
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    onClick={() => handleConfirm(selected)}
                    disabled={selected.status !== 'pending'}
                  >
                    确认
                  </Button>
                  <Button
                    danger
                    icon={<RollbackOutlined />}
                    onClick={() => handleReject(selected)}
                    disabled={selected.status !== 'pending'}
                  >
                    打回重判
                  </Button>
                </Space>
              </div>
            ) : (
              <Empty description="请点击左侧记录查看详情" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default GradingReview
