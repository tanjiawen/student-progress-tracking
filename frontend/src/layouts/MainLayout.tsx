import { Layout, Menu, Avatar, Dropdown, theme } from 'antd'
import {
  DashboardOutlined,
  FileTextOutlined,
  TeamOutlined,
  BookOutlined,
  LogoutOutlined,
  UserOutlined,
  BarChartOutlined,
  CheckSquareOutlined,
  BranchesOutlined,
  EditOutlined,
  IdcardOutlined,
} from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const { Header, Sider, Content } = Layout

const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken()

  const isStudent = user?.role === 'student'

  const studentMenuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '学习概览' },
    { key: '/students/1', icon: <IdcardOutlined />, label: '个人档案' },
    { key: '/exercise', icon: <EditOutlined />, label: '练习' },
    { key: '/error-book', icon: <BookOutlined />, label: '错题本' },
    { key: '/reports', icon: <BarChartOutlined />, label: '学情报告' },
  ]

  const teacherMenuItems = [
    { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
    { key: '/exams', icon: <FileTextOutlined />, label: '考试管理' },
    { key: '/classes', icon: <TeamOutlined />, label: '班级管理' },
    { key: '/knowledge', icon: <BranchesOutlined />, label: '知识点' },
    { key: '/grading', icon: <CheckSquareOutlined />, label: '判卷审核' },
    { key: '/reports', icon: <BarChartOutlined />, label: '学情报告' },
    { key: '/error-book', icon: <BookOutlined />, label: '错题本' },
  ]

  const menuItems = isStudent ? studentMenuItems : teacherMenuItems

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const userMenuItems = [
    { key: 'profile', icon: <UserOutlined />, label: '个人中心' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" breakpoint="lg" collapsedWidth="0">
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: 18,
          }}
        >
          学情系统
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
          }}
        >
          <Dropdown
            menu={{
              items: userMenuItems,
              onClick: ({ key }) => {
                if (key === 'logout') handleLogout()
              },
            }}
            placement="bottomRight"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <span style={{ fontSize: 14 }}>{user?.name || user?.username || '用户'}</span>
              <Avatar icon={<UserOutlined />} />
            </div>
          </Dropdown>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
            minHeight: 280,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
