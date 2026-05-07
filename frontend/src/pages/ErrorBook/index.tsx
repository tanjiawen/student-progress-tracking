import { useEffect, useState } from 'react'
import {
  Card,
  List,
  Tag,
  Select,
  Row,
  Col,
  Typography,
  Button,
  Skeleton,
  Empty,
  message,
} from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { studentsApi } from '@/api/students'
import type { ErrorBookItem } from '@/types'

const { Text } = Typography

const errorTypeMap: Record<string, string> = {
  calculation_error: '计算错误',
  concept_error: '概念错误',
  missing_step: '步骤遗漏',
  formula_error: '公式错误',
  logic_break: '逻辑断裂',
  careless: '粗心大意',
}

const errorTypeColor: Record<string, string> = {
  calculation_error: 'orange',
  concept_error: 'red',
  missing_step: 'blue',
  formula_error: 'purple',
  logic_break: 'volcano',
  careless: 'default',
}

const ErrorBook: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<ErrorBookItem[]>([])
  const [filterKnowledge, setFilterKnowledge] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [studentId] = useState<number>(1)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await studentsApi.errorBook(studentId)
        setItems(res)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [studentId])

  const knowledgeOptions = Array.from(new Set(items.map((i) => i.knowledge_point)))
  const typeOptions = Array.from(new Set(items.map((i) => i.error_type)))

  const filtered = items
    .filter((item) => (filterKnowledge === 'all' ? true : item.knowledge_point === filterKnowledge))
    .filter((item) => (filterType === 'all' ? true : item.error_type === filterType))
    .sort(
      (a, b) =>
        new Date(a.next_review_at).getTime() - new Date(b.next_review_at).getTime()
    )

  const handleMaster = async (errorId: number) => {
    try {
      await studentsApi.markErrorMastered(studentId, errorId)
      message.success('已标记为掌握')
      setItems((prev) => prev.filter((i) => i.id !== errorId))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={8}>
          <Select
            style={{ width: '100%' }}
            value={filterKnowledge}
            onChange={setFilterKnowledge}
            placeholder="按知识点筛选"
          >
            <Select.Option value="all">全部知识点</Select.Option>
            {knowledgeOptions.map((k) => (
              <Select.Option key={k} value={k}>
                {k}
              </Select.Option>
            ))}
          </Select>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Select
            style={{ width: '100%' }}
            value={filterType}
            onChange={setFilterType}
            placeholder="按错误类型筛选"
          >
            <Select.Option value="all">全部类型</Select.Option>
            {typeOptions.map((t) => (
              <Select.Option key={t} value={t}>
                {errorTypeMap[t] || t}
              </Select.Option>
            ))}
          </Select>
        </Col>
      </Row>

      <Card title={`错题列表 (${filtered.length})`}>
        {loading ? (
          <Skeleton active />
        ) : filtered.length === 0 ? (
          <Empty description="暂无错题记录" />
        ) : (
          <List
            dataSource={filtered}
            renderItem={(item) => (
              <List.Item
                key={item.id}
                extra={
                  <div style={{ textAlign: 'right' }}>
                    <Tag color="default">出错 {item.error_count} 次</Tag>
                    <br />
                    <Button
                      type="link"
                      size="small"
                      icon={<CheckCircleOutlined />}
                      onClick={() => handleMaster(item.id)}
                    >
                      标记已掌握
                    </Button>
                  </div>
                }
              >
                <List.Item.Meta
                  title={
                    <div>
                      <Tag color={errorTypeColor[item.error_type] || 'default'}>
                        {errorTypeMap[item.error_type] || item.error_type}
                      </Tag>
                      <span style={{ marginLeft: 8, fontWeight: 500 }}>
                        {item.question_content}
                      </span>
                    </div>
                  }
                  description={
                    <div>
                      <Text type="secondary">知识点: {item.knowledge_point}</Text>
                      <br />
                      <Text type="secondary">
                        下次复习: {item.next_review_at?.slice(0, 10) || '-'}
                      </Text>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}

export default ErrorBook
