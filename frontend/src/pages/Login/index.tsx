import { useState } from 'react'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'

const { Title } = Typography

function Login() {
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('username', values.username)
      formData.append('password', values.password)

      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (res.ok) {
        localStorage.setItem('token', data.access_token)
        message.success('登录成功')
        // TODO: navigate to dashboard
      } else {
        message.error(data.detail || '登录失败')
      }
    } catch {
      message.error('网络错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f0f2f5'
    }}>
      <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>学生学情跟踪系统</Title>
          <Typography.Text type="secondary">v0.0.1</Typography.Text>
        </div>
        <Form onFinish={onFinish}>
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Login
