// 文件路径：frontend/src/App.tsx
// 文件作用：应用主布局，侧边导航 + 内容区，顶部状态栏
// 最后更新时间：2026-06-28-2016
import { useEffect, useState } from 'react'
import { Layout, Menu, theme, Badge, Tooltip, Button } from 'antd'
import {
  ClockCircleOutlined, FileTextOutlined, SearchOutlined,
  SettingOutlined, PauseCircleOutlined, PlayCircleOutlined,
  FieldTimeOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { api } from './api'
import TimelinePage from './pages/Timeline'
import ReportsPage from './pages/Reports'
import SearchPage from './pages/Search'
import SettingsPage from './pages/Settings'
import './App.css'

const { Header, Sider, Content } = Layout

type PageKey = 'timeline' | 'reports' | 'search' | 'settings'

const items: MenuProps['items'] = [
  { key: 'timeline', icon: <ClockCircleOutlined />, label: '时间线' },
  { key: 'reports', icon: <FileTextOutlined />, label: '报告' },
  { key: 'search', icon: <SearchOutlined />, label: '搜索' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置' },
]

const STATE_COLOR: Record<string, string> = {
  ACTIVE: 'green', IDLE: 'gold', LOCKED: 'red', PAUSED: 'default',
}
const STATE_LABEL: Record<string, string> = {
  ACTIVE: '活跃记录中', IDLE: '空闲', LOCKED: '已锁屏', PAUSED: '已暂停',
}

function App() {
  const [page, setPage] = useState<PageKey>('timeline')
  const [state, setState] = useState('ACTIVE')
  const [collapsed, setCollapsed] = useState(false)
  const { token } = theme.useToken()

  // 轮询状态
  useEffect(() => {
    let timer: number
    const poll = async () => {
      try {
        const r = await api.getStatus()
        setState(r.state)
      } catch { /* 后端未就绪 */ }
    }
    poll()
    timer = window.setInterval(poll, 5000)
    return () => clearInterval(timer)
  }, [])

  const togglePause = async () => {
    try {
      if (state === 'PAUSED') {
        const r = await api.resume()
        setState(r.state)
      } else {
        const r = await api.pause()
        setState(r.state)
      }
    } catch (e) { console.error(e) }
  }

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="light">
        <div className="logo">
          <FieldTimeOutlined style={{ fontSize: 20, color: token.colorPrimary }} />
          {!collapsed && <span>ScreenSight</span>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[page]}
          items={items}
          onClick={(e) => setPage(e.key as PageKey)}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Badge status={STATE_COLOR[state] as any} text={STATE_LABEL[state]} />
          <Tooltip title={state === 'PAUSED' ? '恢复记录' : '暂停记录'}>
            <Button
              type="text"
              icon={state === 'PAUSED' ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={togglePause}
            />
          </Tooltip>
        </Header>
        <Content className="app-content">
          {page === 'timeline' && <TimelinePage />}
          {page === 'reports' && <ReportsPage />}
          {page === 'search' && <SearchPage />}
          {page === 'settings' && <SettingsPage />}
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
