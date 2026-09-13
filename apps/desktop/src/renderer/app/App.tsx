import { useEffect, useMemo, useState } from 'react'
import { State } from '../shared/components/State'
import { createModelApi } from '../domains/models/api'
import { ModelManagementPage } from '../domains/models/pages/ModelManagementPage'
import { AndroidPage } from '../domains/android/pages/AndroidPage'
import { ApiProvider } from './ApiProvider'
import { ApplicationHeader, routeFromHash, type AppRoute } from './ApplicationHeader'
import { DashboardPage } from '../domains/dashboard/pages/DashboardPage'
import { SettingsPage } from '../domains/settings/pages/SettingsPage'
import { ProxyManagementPage } from '../domains/proxies/pages/ProxyManagementPage'
import { BrowserManagementPage } from '../domains/profiles/pages/BrowserManagementPage'
import type { SettingsBridge } from '../../shared/settings'
import { useDesktopSession } from './useDesktopSession'

export function App() {
  const { session, status, message, reconnect } = useDesktopSession()
  const [route, setRoute] = useState<AppRoute>(routeFromHash)
  const modelApi = useMemo(() => session ? createModelApi(session.client) : null, [session])

  useEffect(() => {
    void window.autoflow.getSettings?.().then(result => {
      if (result.ok && result.value.workspace.needsSelection) { setRoute('settings'); window.location.hash = '/settings' }
    }).catch(() => undefined)
  }, [])

  useEffect(() => {
    const changed = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])

  const navigate = (target: AppRoute) => { setRoute(target); window.location.hash = `/${target}` }
  const settingsAvailable = typeof window.autoflow.getSettings === 'function'
  return <div className="min-h-screen bg-canvas text-ink">
    <ApplicationHeader route={route} onNavigate={navigate} status={status} />
    {route === 'settings' ? settingsAvailable
      ? <SettingsPage bridge={window.autoflow as SettingsBridge} restartService={() => window.autoflow.restartSidecar()} onServiceChanged={() => void reconnect(false)} />
      : <State title="桌面设置不可用" description="请使用 AutoFlow 桌面应用打开设置。" />
    : <>
      {status === 'loading' ? <div role="status" className="border-b border-line bg-surface-subtle px-8 py-3 text-sm">正在连接服务…</div> : status === 'offline' ? <div role="alert" className="flex items-center justify-between gap-4 border-b border-red-200 bg-red-50 px-8 py-3 text-sm text-red-900"><span>{message}</span><button type="button" onClick={() => void reconnect()}>重新连接</button></div> : null}
      {session ? <ApiProvider key={session.workspaceKey} baseUrl={session.baseUrl} token={session.token} instanceId={session.instanceId} client={session.client}>
        <div inert={status !== 'connected'} aria-busy={status !== 'connected'} className={status !== 'connected' ? 'opacity-60' : undefined}>
          {route === 'dashboard' ? <DashboardPage client={session.client} onNavigate={navigate} />
            : route === 'android' ? <AndroidPage connected={status === 'connected'} />
            : route === 'proxies' ? <ProxyManagementPage api={session.client} />
            : route === 'models' && modelApi ? <ModelManagementPage api={modelApi} instanceId={session.instanceId} />
            : <BrowserManagementPage disabled={status !== 'connected'} onReconnect={() => void reconnect()} />}
        </div>
      </ApiProvider> : null}
    </>}
  </div>
}
