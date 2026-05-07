import { useState } from 'react'
import {
  Card,
  Button,
  Radio,
  Input,
  Progress,
  Space,
  Typography,
  Tag,
  Result,
  message,
  Skeleton,
} from 'antd'
import { CheckCircleOutlined, ArrowRightOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ExerciseQuestion, ExerciseResult } from '@/types'

const { Title, Text } = Typography

const mockQuestions: ExerciseQuestion[] = [
  {
    id: 1,
    type: 'choice',
    content: '下列哪个数是质数？',
    options: ['A. 1', 'B. 4', 'C. 7', 'D. 9'],
    answer: 'C',
    knowledge_point: '质数与合数',
    explanation: '质数是指大于1且只有1和它本身两个因数的自然数。7 是质数。',
  },
  {
    id: 2,
    type: 'choice',
    content: '方程 x² - 5x + 6 = 0 的解为',
    options: ['A. x=1', 'B. x=2 或 x=3', 'C. x=6', 'D. 无解'],
    answer: 'B',
    knowledge_point: '一元二次方程',
    explanation: '因式分解得 (x-2)(x-3)=0，所以 x=2 或 x=3。',
  },
  {
    id: 3,
    type: 'essay',
    content: '简述勾股定理的内容及其应用场景。',
    answer: '直角三角形两直角边的平方和等于斜边的平方。应用于测量、建筑、导航等领域。',
    knowledge_point: '勾股定理',
    explanation: '勾股定理：a² + b² = c²，其中 c 为斜边。',
  },
]

const ExercisePage: React.FC = () => {
  const [questions] = useState<ExerciseQuestion[]>(mockQuestions)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [results, setResults] = useState<ExerciseResult[]>([])
  const [loading] = useState(false)

  const current = questions[currentIndex]
  const total = questions.length
  const progress = Math.round(((currentIndex + 1) / total) * 100)

  const handleAnswer = (value: string) => {
    setAnswers((prev) => ({ ...prev, [current.id]: value }))
  }

  const handleSubmit = () => {
    if (!answers[current.id]) {
      message.warning('请先作答')
      return
    }
    if (currentIndex < total - 1) {
      setCurrentIndex((prev) => prev + 1)
    } else {
      const res: ExerciseResult[] = questions.map((q) => {
        const userAns = answers[q.id] || ''
        const correct = q.type === 'choice' ? userAns === q.answer : userAns.length > 10
        return {
          question_id: q.id,
          correct,
          user_answer: userAns,
          correct_answer: q.answer || '',
          explanation: q.explanation || '',
          score: correct ? 10 : 0,
        }
      })
      setResults(res)
      setSubmitted(true)
    }
  }

  const handleRestart = () => {
    setCurrentIndex(0)
    setAnswers({})
    setSubmitted(false)
    setResults([])
  }

  if (loading) {
    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Skeleton active />
      </div>
    )
  }

  if (submitted) {
    const correctCount = results.filter((r) => r.correct).length
    const totalScore = results.reduce((sum, r) => sum + r.score, 0)

    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <Result
          status="success"
          icon={<CheckCircleOutlined />}
          title="练习完成！"
          subTitle={`得分: ${totalScore} 分 | 正确: ${correctCount}/${total}`}
          extra={[
            <Button type="primary" key="restart" icon={<ReloadOutlined />} onClick={handleRestart}>
              再来一次
            </Button>,
          ]}
        />
        {results.map((r, idx) => (
          <Card key={r.question_id} style={{ marginBottom: 16 }} title={`第 ${idx + 1} 题`}>
            <Tag color={r.correct ? 'green' : 'red'}>{r.correct ? '正确' : '错误'}</Tag>
            <p style={{ marginTop: 8 }}>
              <Text strong>你的答案：</Text>
              <Text>{r.user_answer}</Text>
            </p>
            {!r.correct && (
              <p>
                <Text strong type="success">正确答案：</Text>
                <Text type="success">{r.correct_answer}</Text>
              </p>
            )}
            <p>
              <Text strong>解析：</Text>
              <Text>{r.explanation}</Text>
            </p>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <Card>
        <div style={{ marginBottom: 24 }}>
          <Progress percent={progress} status="active" format={() => `${currentIndex + 1}/${total}`} />
        </div>

        <Tag color="blue">{current.knowledge_point}</Tag>
        <Title level={5} style={{ marginTop: 12 }}>
          {current.content}
        </Title>

        {current.type === 'choice' && current.options && (
          <Radio.Group
            onChange={(e) => handleAnswer(e.target.value)}
            value={answers[current.id]}
            style={{ display: 'block', marginTop: 16 }}
          >
            <Space direction="vertical">
              {current.options.map((opt) => (
                <Radio key={opt} value={opt.charAt(0)}>
                  {opt}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        )}

        {current.type === 'essay' && (
          <Input.TextArea
            rows={6}
            placeholder="请输入你的答案..."
            value={answers[current.id] || ''}
            onChange={(e) => handleAnswer(e.target.value)}
            style={{ marginTop: 16 }}
          />
        )}

        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <Button
            type="primary"
            size="large"
            icon={<ArrowRightOutlined />}
            onClick={handleSubmit}
          >
            {currentIndex < total - 1 ? '下一题' : '提交'}
          </Button>
        </div>
      </Card>
    </div>
  )
}

export default ExercisePage
