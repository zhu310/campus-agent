// 应用顶层导航和页面切换入口。
import { Layout, Menu } from 'antd'
import { AppstoreOutlined, HistoryOutlined, NodeIndexOutlined, ProductOutlined } from '@ant-design/icons'
import { useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import ExtensionsPage from './pages/ExtensionsPage'
import RecordsPage from './pages/RecordsPage'
import WorkspacePage from './pages/WorkspacePage'

const { Content, Header } = Layout

export default function App() {
  const [active, setActive] = useState('dashboard')
  const [workspaceScenario, setWorkspaceScenario] = useState('比赛报名')

  const openWorkspace = (scenario = '比赛报名') => {
    setWorkspaceScenario(scenario)
    setActive('workspace')
  }

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <div className="app-brand">智审通 Campus Copilot</div>
        <Menu
          mode="horizontal"
          selectedKeys={[active]}
          onClick={({ key }) => setActive(key)}
          items={[
            { key: 'dashboard', icon: <ProductOutlined />, label: 'Dashboard' },
            { key: 'workspace', icon: <AppstoreOutlined />, label: '智能办理' },
            { key: 'records', icon: <HistoryOutlined />, label: '记录留痕' },
            { key: 'extensions', icon: <NodeIndexOutlined />, label: '拓展中心' },
          ]}
        />
      </Header>
      <Content className={`app-content app-content-compact ${active === 'workspace' ? 'workspace-content' : 'page-content'}`}>
        {active === 'dashboard' ? <DashboardPage onStart={openWorkspace} /> : null}
        {active === 'workspace' ? <WorkspacePage initialScenario={workspaceScenario} /> : null}
        {active === 'records' ? <RecordsPage /> : null}
        {active === 'extensions' ? <ExtensionsPage /> : null}
      </Content>
    </Layout>
  )
}
