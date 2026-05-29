// 应用顶层导航和页面切换入口。
import { Layout, Menu } from 'antd'
import { AppstoreOutlined, BarChartOutlined, ProductOutlined, SettingOutlined } from '@ant-design/icons'
import { useState } from 'react'
import DataAnalysisPage from './pages/DataAnalysisPage'
import DashboardPage from './pages/DashboardPage'
import ExtensionsPage from './pages/ExtensionsPage'
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
            { key: 'analytics', icon: <BarChartOutlined />, label: '数据分析' },
            { key: 'extensions', icon: <SettingOutlined />, label: '系统设置' },
          ]}
        />
      </Header>
      <Content className={`app-content app-content-compact ${active === 'workspace' ? 'workspace-content' : 'page-content'}`}>
        <div style={{ display: active === 'dashboard' ? 'block' : 'none', height: '100%' }}>
          <DashboardPage onStart={openWorkspace} />
        </div>
        <div style={{ display: active === 'workspace' ? 'block' : 'none', height: '100%' }}>
          <WorkspacePage initialScenario={workspaceScenario} />
        </div>
        <div style={{ display: active === 'analytics' ? 'block' : 'none', height: '100%' }}>
          <DataAnalysisPage />
        </div>
        <div style={{ display: active === 'extensions' ? 'block' : 'none', height: '100%' }}>
          <ExtensionsPage />
        </div>
      </Content>
    </Layout>
  )
}
