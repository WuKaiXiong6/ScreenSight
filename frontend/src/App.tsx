// 文件路径：frontend/src/App.tsx
// 文件作用：应用主布局，侧边导航 + 内容区，顶部状态栏
// 最后更新时间：2026-07-02-1209
import { useEffect, useState } from 'react'
import { Layout, Menu, theme, Badge, Tooltip, Button, Tag } from 'antd'
import {
  ClockCircleOutlined, FileTextOutlined, SearchOutlined,
  SettingOutlined, PauseCircleOutlined, PlayCircleOutlined,
  FieldTimeOutlined, CameraOutlined, CheckCircleOutlined, WarningOutlined,
  EyeInvisibleOutlined, EyeOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import dayjs from 'dayjs'
import { api } from './api'
import type { StatusInfo } from './api'
import { PrivacyContext } from './privacy'
import { parseHash, updateHash } from './hashState'
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
  // 初始状态从 URL hash 恢复（支持刷新恢复与深链）
  const initial = parseHash()
  const validPages: PageKey[] = ['timeline', 'reports', 'search', 'settings']
  const [page, setPage] = useState<PageKey>(
    validPages.includes(initial._page as PageKey) ? initial._page as PageKey : 'timeline'
  )
  const [status, setStatus] = useState<StatusInfo | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  // 隐私展示模式：演示/截图/分享时开启，对象名打码、截图模糊
  const [privacyMode, setPrivacyMode] = useState(initial.privacy === '1')
  const { token } = theme.useToken()

  // 轮询状态（含最近活动信息）
  useEffect(() => {
    let timer: number
    const poll = async () => {
      try {
        const r = await api.getStatus()
        setStatus(r)
      } catch { /* 后端未就绪 */ }
    }
    poll()
    timer = window.setInterval(poll, 5000)
    return () => clearInterval(timer)
  }, [])

  // page / privacy 变化时同步到 hash
  useEffect(() => {
    updateHash({ _page: page, privacy: privacyMode ? '1' : undefined })
  }, [page, privacyMode])

  // 监听浏览器前进/后退恢复状态
  useEffect(() => {
    const onHashChange = () => {
      const h = parseHash()
      if (validPages.includes(h._page as PageKey) && h._page !== page) {
        setPage(h._page as PageKey)
      }
      const isPrivacy = h.privacy === '1'
      if (isPrivacy !== privacyMode) {
        setPrivacyMode(isPrivacy)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [page, privacyMode])

  const state = status?.state ?? 'ACTIVE'

  const togglePause = async () => {
    try {
      if (state === 'PAUSED') {
        const r = await api.resume()
        setStatus({ ...status, state: r.state } as StatusInfo)
      } else {
        const r = await api.pause()
        setStatus({ ...status, state: r.state } as StatusInfo)
      }
    } catch (e) { console.error(e) }
  }

  // 状态栏可运维信息：最近截屏/识别/今日费用/异常
  const fmtTime = (iso: string | null) => iso ? dayjs(iso).format('HH:mm') : '-'

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="light"
        breakpoint="lg"
        collapsedWidth={0}
        zeroWidthTriggerStyle={{ top: 8 }}
      >
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
          <div className="header-status-group">
            <Badge status={STATE_COLOR[state] as any} text={STATE_LABEL[state]} />
            {status && (
              <>
                <Tooltip title="最近一次截屏时间">
                  <span className="header-metric">
                    <CameraOutlined /> {fmtTime(status.last_capture_at)}
                  </span>
                </Tooltip>
                <Tooltip title="最近一次识别成功时间">
                  <span className="header-metric">
                    <CheckCircleOutlined /> {fmtTime(status.last_recognition_at)}
                  </span>
                </Tooltip>
                <Tooltip title="今日预估费用">
                  <span className="header-metric">¥{status.today_cost.toFixed(4)}</span>
                </Tooltip>
                {status.recent_error_count > 0 && (
                  <Tooltip title={`最近 30 分钟内 ${status.recent_error_count} 次识别失败`}>
                    <Tag color="red" icon={<WarningOutlined />} className="header-metric">
                      {status.recent_error_count}
                    </Tag>
                  </Tooltip>
                )}
              </>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tooltip title={privacyMode ? '关闭隐私模式（恢复显示对象名与清晰截图）' : '开启隐私模式（对象名打码、截图模糊，适合演示/分享）'}>
              <Button
                type="text"
                icon={privacyMode ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                onClick={() => setPrivacyMode(!privacyMode)}
                style={{ color: privacyMode ? '#fa8c16' : undefined }}
              />
            </Tooltip>
            <Tooltip title={state === 'PAUSED' ? '恢复记录' : '暂停记录'}>
              <Button
                type="text"
                icon={state === 'PAUSED' ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                onClick={togglePause}
              />
            </Tooltip>
          </div>
        </Header>
        <Content className="app-content">
          <PrivacyContext.Provider value={privacyMode}>
            {page === 'timeline' && <TimelinePage />}
            {page === 'reports' && <ReportsPage />}
            {page === 'search' && <SearchPage />}
            {page === 'settings' && <SettingsPage />}
          </PrivacyContext.Provider>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
