import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Tree,
  Form,
  Input,
  Button,
  Select,
  Space,
  message,
  Modal,
  Row,
  Col,
  Upload,
  Empty,
  Spin,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  UploadOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import type { TreeDataNode } from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { knowledgeApi } from '@/api/knowledge'
import type { KnowledgeNode, Subject } from '@/types'



interface TreeNodeWithData extends TreeDataNode {
  data?: KnowledgeNode
}

function buildTree(nodes: KnowledgeNode[]): TreeNodeWithData[] {
  const map = new Map<number, TreeNodeWithData>()
  const roots: TreeNodeWithData[] = []

  nodes.forEach((n) => {
    map.set(n.id, {
      key: n.id,
      title: `${n.code} ${n.name}`,
      data: n,
      children: [],
    })
  })

  nodes.forEach((n) => {
    const node = map.get(n.id)!
    if (n.parent_id && map.has(n.parent_id)) {
      const parent = map.get(n.parent_id)!
      if (!parent.children) parent.children = []
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  })

  return roots
}

function generateCode(subject: string, level: number, nodes: KnowledgeNode[]) {
  const prefix = subject.slice(0, 1).toUpperCase()
  const sameLevel = nodes.filter((n) => n.subject === subject && n.level === level)
  const max = sameLevel.reduce((m, n) => {
    const num = parseInt(n.code.replace(/\D/g, ''), 10)
    return Math.max(m, num || 0)
  }, 0)
  return `${prefix}${level}.${String(max + 1).padStart(2, '0')}`
}

const KnowledgeManage: React.FC = () => {
  const [treeData, setTreeData] = useState<TreeNodeWithData[]>([])
  const [allNodes, setAllNodes] = useState<KnowledgeNode[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [form] = Form.useForm()
  const [isEditing, setIsEditing] = useState(false)
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])

  const fetchTree = useCallback(async () => {
    try {
      const res = await knowledgeApi.tree()
      setAllNodes(res)
      setTreeData(buildTree(res))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      try {
        const [subjectsRes, treeRes] = await Promise.all([
          knowledgeApi.subjects(),
          knowledgeApi.tree(),
        ])
        setSubjects(subjectsRes)
        setAllNodes(treeRes)
        setTreeData(buildTree(treeRes))
      } catch (err) {
        message.error(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const handleSelect = (_: React.Key[], info: { selectedNodes: TreeNodeWithData[] }) => {
    const data = info.selectedNodes[0]?.data
    if (data) {
      setSelectedNode(data)
      form.setFieldsValue({
        name: data.name,
        code: data.code,
        subject: data.subject,
        level: data.level,
      })
      setIsEditing(true)
    } else {
      setSelectedNode(null)
      setIsEditing(false)
      form.resetFields()
    }
  }

  const handleAdd = () => {
    setSelectedNode(null)
    setIsEditing(false)
    form.resetFields()
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    try {
      if (isEditing && selectedNode) {
        await knowledgeApi.update(selectedNode.id, {
          name: values.name,
          code: values.code,
        })
        message.success('更新成功')
      } else {
        const code =
          values.code || generateCode(values.subject, values.level, allNodes)
        await knowledgeApi.create({
          name: values.name,
          code,
          level: values.level,
          parent_id: selectedNode?.id || null,
          subject: values.subject,
        })
        message.success('创建成功')
      }
      await fetchTree()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  const handleDelete = () => {
    if (!selectedNode) return
    Modal.confirm({
      title: '确认删除',
      content: `确定删除知识点 "${selectedNode.name}" 吗？`,
      onOk: async () => {
        try {
          await knowledgeApi.delete(selectedNode.id)
          message.success('删除成功')
          setSelectedNode(null)
          setIsEditing(false)
          form.resetFields()
          await fetchTree()
        } catch (err) {
          message.error(err instanceof Error ? err.message : '删除失败')
        }
      },
    })
  }

  const handleImport = async () => {
    if (uploadFileList.length === 0) {
      message.error('请选择文件')
      return
    }
    const fd = new FormData()
    fd.append('file', uploadFileList[0].originFileObj as File)
    try {
      const res = await knowledgeApi.importStandard(fd)
      message.success(`导入成功，共 ${res.count} 条`)
      setUploadFileList([])
      await fetchTree()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导入失败')
    }
  }

  return (
    <Row gutter={24}>
      <Col xs={24} md={10}>
        <Card
          title="知识点树"
          extra={
            <Space>
              <Button icon={<PlusOutlined />} size="small" onClick={handleAdd}>
                新增
              </Button>
              <Upload
                fileList={uploadFileList}
                beforeUpload={() => false}
                onChange={({ fileList }) => setUploadFileList(fileList)}
                accept=".json"
              >
                <Button icon={<UploadOutlined />} size="small">
                  导入课标
                </Button>
              </Upload>
              {uploadFileList.length > 0 && (
                <Button type="primary" size="small" onClick={handleImport}>
                  确认导入
                </Button>
              )}
            </Space>
          }
        >
          {loading ? (
            <Spin tip="加载中..." />
          ) : treeData.length === 0 ? (
            <Empty description="暂无知识点" />
          ) : (
            <Tree
              treeData={treeData}
              onSelect={handleSelect}
              defaultExpandAll
              blockNode
            />
          )}
        </Card>
      </Col>
      <Col xs={24} md={14}>
        <Card title={isEditing ? '编辑知识点' : '新增知识点'}>
          <Form form={form} layout="vertical">
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input placeholder="知识点名称" />
            </Form.Item>
            <Form.Item name="subject" label="学科" rules={[{ required: true }]}>
              <Select placeholder="选择学科" disabled={isEditing}>
                {subjects.map((s) => (
                  <Select.Option key={s.code} value={s.name}>
                    {s.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
            <Form.Item name="level" label="层级" rules={[{ required: true }]}>
              <Select placeholder="选择层级" disabled={isEditing}>
                <Select.Option value={1}>一级（学科）</Select.Option>
                <Select.Option value={2}>二级（章节）</Select.Option>
                <Select.Option value={3}>三级（知识点）</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="code" label="编码">
              <Input
                placeholder="留空则自动生成"
                disabled={isEditing}
                addonAfter={
                  !isEditing && form.getFieldValue('subject') ? (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => {
                        const values = form.getFieldsValue()
                        if (values.subject && values.level) {
                          form.setFieldValue(
                            'code',
                            generateCode(values.subject, values.level, allNodes)
                          )
                        }
                      }}
                    >
                      预览
                    </Button>
                  ) : null
                }
              />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
                  保存
                </Button>
                {isEditing && (
                  <Button danger icon={<DeleteOutlined />} onClick={handleDelete}>
                    删除
                  </Button>
                )}
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Col>
    </Row>
  )
}

export default KnowledgeManage
