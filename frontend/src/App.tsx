import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  UserOutlined,
  ProjectOutlined,
  SettingOutlined,
  SyncOutlined,
  CalendarOutlined,
} from '@ant-design/icons'
import DashboardPage from './pages/DashboardPage'
import UsersPage from './pages/UsersPage'
import UserDetailPage from './pages/UserDetailPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import SyncPage from './pages/SyncPage'
import SettingsPage from './pages/SettingsPage'
import WorkdayStatsPage from './pages/WorkdayStatsPage'

const { Header, Content, Sider } = Layout

/** Пункты бокового меню. */
const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: <Link to="/">Дашборд</Link> },
  { key: '/users', icon: <UserOutlined />, label: <Link to="/users">Пользователи</Link> },
  { key: '/projects', icon: <ProjectOutlined />, label: <Link to="/projects">Проекты</Link> },
  { key: '/workdays', icon: <CalendarOutlined />, label: <Link to="/workdays">Рабочие дни</Link> },
  { key: '/sync', icon: <SyncOutlined />, label: <Link to="/sync">Синхронизация</Link> },
  { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">Настройки</Link> },
]

export default function App() {
  const location = useLocation()

  /* Определяем активный пункт меню по текущему пути */
  const selectedKey = '/' + (location.pathname.split('/')[1] || '')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="80">
        <div style={{ color: '#fff', textAlign: 'center', padding: '16px 0', fontSize: 18, fontWeight: 'bold' }}>
          GL Analyzer
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', fontSize: 18 }}>
          GitLab Analyzer
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff', borderRadius: 8 }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/users/:id" element={<UserDetailPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:id" element={<ProjectDetailPage />} />
            <Route path="/workdays" element={<WorkdayStatsPage />} />
            <Route path="/sync" element={<SyncPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
