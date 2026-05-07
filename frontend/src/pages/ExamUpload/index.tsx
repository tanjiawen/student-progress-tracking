import { useEffect, useState } from 'react'
import { Upload, Button, Form, Input, Select, message, Card, Progress, Spin } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { useNavigate } from 'react-router-dom'
import { examsApi } from '@/api/exams'
import { knowledgeApi } from '@/api/knowledge'
import { classesApi } from '@/api/classes'
import type { Subject, ClassItem } from '@/types'

const { Dragger } = Upload

const ExamUpload: React.FC = () => {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [percent, setPercent] = useState(0)
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [classes, setClasses] = useState<ClassItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [subjectsRes, classesRes] = await Promise.all([
          knowledgeApi.subjects(),
          classesApi.list(),
        ])
        setSubjects(subjectsRes)
        setClasses(classesRes)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载数据失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const handleUpload = async () => {
    const values = await form.validateFields()
    if (fileList.length === 0) {
      message.error('请上传试卷文件')
      return
    }

    setUploading(true)
    setPercent(0)

    const fd = new FormData()
    fd.append('file', fileList[0].originFileObj as File)
    fd.append('title', values.title)
    fd.append('subject', values.subject)
    fd.append('class_id', String(values.class_id))

    try {
      const exam = await examsApi.upload(fd, (p) => setPercent(p))
      message.success('上传成功')
      setFileList([])
      form.resetFields()
      setPercent(0)
      navigate(`/exams/${exam.id}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  return (
    <Card title="试卷上传">
      <Form form={form} layout="vertical">
        <Form.Item
          name="title"
          label="考试标题"
          rules={[{ required: true, message: '请输入考试标题' }]}
        >
          <Input placeholder="例如：2026年春季期中考试" />
        </Form.Item>
        <Form.Item name="subject" label="学科" rules={[{ required: true, message: '请选择学科' }]}>
          <Select placeholder="选择学科">
            {subjects.map((s) => (
              <Select.Option key={s.code} value={s.name}>
                {s.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          name="class_id"
          label="班级"
          rules={[{ required: true, message: '请选择班级' }]}
        >
          <Select placeholder="选择班级">
            {classes.map((c) => (
              <Select.Option key={c.id} value={c.id}>
                {c.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item label="试卷文件">
          <Dragger
            fileList={fileList}
            onChange={({ fileList: fl }) => setFileList(fl)}
            beforeUpload={() => false}
            accept=".pdf,.jpg,.jpeg,.png,.webp"
            multiple={false}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">支持 PDF、JPG、PNG、WEBP 格式</p>
          </Dragger>
        </Form.Item>
        {uploading && (
          <Progress percent={percent} status={percent < 100 ? 'active' : 'success'} />
        )}
        <Form.Item>
          <Button type="primary" onClick={handleUpload} loading={uploading} block>
            开始上传
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default ExamUpload
