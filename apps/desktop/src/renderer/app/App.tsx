import { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { State } from '../shared/components/State'
import { createModelApi } from '../domains/models/api'
import { ModelManagementPage } from '../domains/models/pages/ModelManagementPage'
import { ApiProvider } from './ApiProvider'
import { ApplicationHeader } from './ApplicationHeader'
import { parseAppLocation, projectHash, useGuardedHashNavigation, type AppRoute } from './navigation'
import { ProjectsWorkspace } from '../domains/projects/pages/ProjectsWorkspace'
import type { ProjectRoute } from '../domains/projects/types'
import { Button } from '../shared/components/ui/button'
import { DashboardPage } from '../domains/dashboard/pages/DashboardPage'
import { SettingsPage } from '../domains/settings/pages/SettingsPage'
import { ProxyManagementPage } from '../domains/proxies/pages/ProxyManagementPage'
import { BrowserManagementPage } from '../domains/profiles/pages/BrowserManagementPage'
import type { SettingsBridge } from '../../shared/settings'
import { useDesktopSession } from './useDesktopSession'

export function App() {
  const { session, status, message, reconnect, workspaceChanging } = useDesktopSession()
  const { hash, navigate: navigateHash, replace, registerLeaveGuard } = useGuardedHashNavigation()
  const previousWorkspace = useRef<string | null>(null)
  const changedWorkspace = session && previousWorkspace.current !== null && previousWorkspace.current !== session.workspaceKey
  const location = parseAppLocation(changedWorkspace && hash.startsWith('#/projects') ? '#/projects' : hash)
  const route = location.section
  const navigate = useCallback((target: AppRoute) => { void navigateHash(`#/${target}`) }, [navigateHash])
  const navigateProject = useCallback((target: ProjectRoute, options?: { replace?: boolean }) => { if (options?.replace) replace(projectHash(target), { preserveGuard: true }); else void navigateHash(projectHash(target)) }, [navigateHash, replace])
  const modelApi = useMemo(() => session ? createModelApi(session.client) : null, [session])

  useEffect(() => {
    void window.autoflow.getSettings?.().then(result => {
      if (result.ok && result.value.workspace.needsSelection) replace('#/settings')
    }).catch(() => undefined)
  }, [replace])

  useLayoutEffect(() => {
    if (!session) return
    if (previousWorkspace.current !== null && previousWorkspace.current !== session.workspaceKey) {
      if (hash.startsWith('#/projects')) replace('#/projects')
    }
    previousWorkspace.current = session.workspaceKey
  }, [hash, replace, session])

  const settingsAvailable = typeof window.autoflow.getSettings === 'function'
  return <div className="min-h-screen bg-canvas text-ink">
    <ApplicationHeader route={route} onNavigate={navigate} status={status} />
    {route === 'settings' ? settingsAvailable
      ? <SettingsPage bridge={window.autoflow as SettingsBridge} restartService={() => window.autoflow.restartSidecar()} onServiceChanged={() => void reconnect(false)} />
      : <State title="桌面设置不可用" description="请使用 AutoFlow 桌面应用打开设置。" />
    : <>
      {status === 'loading' ? <div role="status" className="border-b border-line bg-surface-subtle px-8 py-3 text-sm">正在连接服务…</div> : status === 'offline' ? <div role="alert" className="flex items-center justify-between gap-4 border-b border-red-200 bg-red-50 px-8 py-3 text-sm text-red-900"><span>{message}</span><button type="button" onClick={() => void reconnect()}>重新连接</button></div> : null}
      {session ? <ApiProvider key={session.workspaceKey} baseUrl={session.baseUrl} token={session.token} instanceId={session.instanceId} client={session.client}>
        <div inert={status !== 'connected' || workspaceChanging} aria-busy={status !== 'connected' || workspaceChanging} className={status !== 'connected' ? 'opacity-60' : undefined}>
          {route === 'dashboard' ? <DashboardPage client={session.client} onNavigate={navigate} />
            : route === 'projects' ? location.error
              ? <main className="mx-auto max-w-4xl p-6"><State title="无法打开项目" description={location.error} /><Button onClick={() => navigate('projects')}>返回项目目录</Button></main>
              : <ProjectsWorkspace route={location.project!} workspaceKey={session.workspaceKey} instanceId={session.instanceId} client={session.client} disabled={status !== 'connected' || workspaceChanging} onNavigate={navigateProject} registerLeaveGuard={registerLeaveGuard} />
            : route === 'proxies' ? <ProxyManagementPage api={session.client} />
            : route === 'models' && modelApi ? <ModelManagementPage api={modelApi} instanceId={session.instanceId} />
            : <BrowserManagementPage disabled={status !== 'connected'} onReconnect={() => void reconnect()} />}
        </div>
      </ApiProvider> : null}
    </>}
  </div>
}
