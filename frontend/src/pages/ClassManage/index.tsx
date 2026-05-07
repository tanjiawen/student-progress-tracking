import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  List,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  Table,
  Tabs,
  message,
  Skeleton,
  Empty,
  Upload,
} from 'antd'
import {
  PlusOutlined,
  TeamOutlined,
  FileTextOutlined,
  UploadOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import ReactECharts from 'echarts-for-react'
import { classesApi } from '@/api/classes'
import type { ClassItem, ClassDetail } from '@/types'

const { TabPane } = Tabs

const ClassManage: React.FC = () => {
  const [classes, setClasses] = useState<ClassItem[]>([])
  const [selectedClass, setSelectedClass] = useState<ClassDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await classesApi.list()
        setClasses(res)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const handleViewDetail = async (id: number) => {
    setDetailLoading(true)
    try {
      const res = await classesApi.detail(id)
      setSelectedClass(res)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    try {
      await classesApi.create({ name: values.name })
      message.success('创建成功')
      setModalOpen(false)
      form.resetFields()
      const res = await classesApi.list()
      setClasses(res)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败')
    }
  }

  const handleImportStudents = async () => {
    if (!selectedClass || uploadFileList.length === 0) {
      message.error('请选择文件')
      return
    }
    const fd = new FormData()
    fd.append('file', uploadFileList[0].originFileObj as File)
    try {
      await classesApi.importStudents(selectedClass.id, fd)
      message.success('导入成功')
      setUploadFileList([])
      await handleViewDetail(selectedClass.id)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导入失败')
    }
  }

  const heatmapOption = (() => {
    if (!selectedClass?.heatmap?.length) return null
    const students = Array.from(new Set(selectedClass.heatmap.map((h) => h.student_name)))
    const knowledges = Array.from(new Set(selectedClass.heatmap.map((h) => h.knowledge_point)))
    const data = selectedClass.heatmap.map((h) => [
      knowledges.indexOf(h.knowledge_point),
      students.indexOf(h.student_name),
      h.mastery,
    ])

    return {
      tooltip: { position: 'top' },
      grid: { height: '70%', top: '10%' },
      xAxis: {
        type: 'category',
        data: knowledges,
        splitArea: { show: true },
        axisLabel: { rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'category',
        data: students,
        splitArea: { show: true },
        axisLabel: { fontSize: 10 },
      },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        inRange: { color: ['#f0f9ff', '#096dd9'] },
      },
      series: [
        {
          type: 'heatmap',
          data,
          label: { show: true, fontSize: 10 },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
          },
        },
      ],
    }
  })()

  const studentColumns = [
    { title: '学号', dataIndex: 'student_no' },
    { title: '姓名', dataIndex: 'name' },
    { title: '性别', dataIndex: 'gender', render: (g?: string) => g || '-' },
    { title: '总分', dataIndex: 'total_score', render: (s?: number) => s ?? '-' },
    { title: '排名', dataIndex: 'rank', render: (r?: number) => r ?? '-' },
  ]

  const examColumns = [
    { title: '考试名称', dataIndex: 'title' },
    { title: '学科', dataIndex: 'subject' },
    { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'graded' ? 'green' : 'orange'}>{s === 'graded' ? '已判卷' : '待判卷'}</Tag> },
    { title: '日期', dataIndex: 'created_at', render: (d: string) => d?.slice(0, 10) || '-' },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <h3 style={{ margin: 0 }}>班级管理</h3>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建班级
          </Button>
        </Col>
      </Row>

      {loading ? (
        <Skeleton active />
      ) : classes.length === 0 ? (
        <Empty description="暂无班级" />
      ) : (
        <List
          grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
          dataSource={classes}
          renderItem={(cls) => (
            <List.Item>
              <Card
                hoverable
                onClick={() => handleViewDetail(cls.id)}
                actions={[
                  <Button type="link" icon={<EyeOutlined />} onClick={(e) => { e.stopPropagation(); handleViewDetail(cls.id) }}>
                    查看详情
                  </Button>,
                ]}
              >
                <Card.Meta
                  title={cls.name}
                  description={
                    <div>
                      <div>
                        <TeamOutlined /> {cls.student_count} 人
                      </div>
                      <div>
                        <FileTextOutlined /> {cls.exam_count} 场考试
                      </div>
                    </div>
                  }
                />
              </Card>
            </List.Item>
          )}
        />
      )}

      <Modal
        title={selectedClass?.name || '班级详情'}
        open={!!selectedClass}
        onCancel={() => setSelectedClass(null)}
        width={960}
        footer={null}
      >
        {detailLoading ? (
          <Skeleton active />
        ) : selectedClass ? (
          <Tabs defaultActiveKey="students">
            <TabPane tab="学生列表" key="students">
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col>
                  <Upload
                    fileList={uploadFileList}
                    beforeUpload={() => false}
                    onChange={({ fileList }) => setUploadFileList(fileList)}
                    accept=".xlsx,.xls,.json"
                  >
                    <Button icon={<UploadOutlined />}>批量导入</Button>
                  </Upload>
                </Col>
                {uploadFileList.length > 0 && (
                  <Col>
                    <Button type="primary" onClick={handleImportStudents}>
                      确认导入
                    </Button>
                  </Col>
                )}
              </Row>
              <Table
                dataSource={selectedClass.students}
                columns={studentColumns}
                rowKey="id"
                pagination={{ pageSize: 10 }}
                scroll={{ x: 'max-content' }}
              />
            </TabPane>
            <TabPane tab="考试列表" key="exams">
              <Table
                dataSource={selectedClass.exams}
                columns={examColumns}
                rowKey="id"
                pagination={{ pageSize: 10 }}
              />
            </TabPane>
            <TabPane tab="薄弱知识点热力图" key="heatmap">
              {heatmapOption ? (
                <ReactECharts option={heatmapOption} style={{ height: 500 }} />
              ) : (
                <Empty description="暂无热力图数据" />
              )}
            </TabPane>
          </Tabs>
        ) : null}
      </Modal>

      <Modal title="新建班级" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="班级名称" rules={[{ required: true, message: '请输入班级名称' }]}>
            <Input placeholder="例如：初三(1)班" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ClassManage
