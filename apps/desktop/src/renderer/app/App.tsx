import { Button } from '../shared/components/ui/button'
import { useCallback, useEffect, useRef, useState } from 'react'
import { initialAppState, type AppState } from './app-state'
import { ApiClientError, createApiClient, type ApiRequestInit } from '../shared/api/client'
import { State } from '../shared/components/State'
import type { HealthResponse, SidecarStatus } from '../shared/api/types'
import { createModelApi } from '../domains/models/api'
import { ModelManagementPage } from '../domains/models/pages/ModelManagementPage'
import { ApiProvider } from './ApiProvider'
import { ApplicationHeader, routeFromHash, type AppRoute } from './ApplicationHeader'
import { DashboardPage } from '../domains/dashboard/pages/DashboardPage'
import { SettingsPage } from '../domains/settings/pages/SettingsPage'
import { ProxyManagementPage } from '../domains/proxies/pages/ProxyManagementPage'
import { BrowserManagementPage } from '../domains/profiles/pages/BrowserManagementPage'
import type { SettingsBridge } from '../../shared/settings'

const SIDECAR_READY_TIMEOUT_MS = 10_000
const SIDECAR_POLL_INTERVAL_MS = 50

function offlineMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return '无法连接到本地服务'
}

function wait(delay: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, delay))
}

async function getReadySidecarStatus(): Promise<Extract<SidecarStatus, { state: 'ready' }>> {
  const deadline = Date.now() + SIDECAR_READY_TIMEOUT_MS

  while (Date.now() <= deadline) {
    const sidecar = await window.autoflow.getSidecarStatus()
    if (sidecar.state === 'ready') return sidecar
    if (sidecar.state === 'failed') throw new Error(sidecar.message)
    await wait(SIDECAR_POLL_INTERVAL_MS)
  }

  throw new Error('等待本地服务就绪超时')
}

export function App() {
  const [state, setState] = useState<AppState>(initialAppState)
  const [route, setRoute] = useState<AppRoute>(routeFromHash)
  const [session, setSession] = useState<Extract<AppState, { status: 'connected' }> | null>(null)
  const connectionEpoch = useRef(0)
  const connectionKey = useRef<string | null>(null)
  const connecting = useRef(false)
  const authRecoveryAttempted = useRef(false)

  const connect = useCallback(async (restart: boolean) => {
    const epoch = ++connectionEpoch.current
    connecting.current = true
    if (restart) authRecoveryAttempted.current = false
    setState({ status: 'loading' })
    try {
      const sidecar = restart
        ? await window.autoflow.restartSidecar()
        : await getReadySidecarStatus()
      if (sidecar.state !== 'ready') throw new Error('本地服务尚未就绪')

      const client = createApiClient({
        baseUrl: sidecar.baseUrl,
        token: sidecar.token,
      })
      const health: HealthResponse = await client.health()
      if (epoch !== connectionEpoch.current) return
      const authenticatedClient = { ...client, async request<T>(path: string, init?: ApiRequestInit) {
        try { return await client.request<T>(path, init) }
        catch (error) {
          if (error instanceof ApiClientError && (error.code === 'SIDECAR_UNAUTHORIZED' || (error.status === 401 && !error.code)) && epoch === connectionEpoch.current) {
            if (authRecoveryAttempted.current) setState({ status: 'offline', message: '本地服务认证失效，请重新连接' })
            else { authRecoveryAttempted.current = true; void connect(false) }
          }
          throw error
        }
      } }
      const modelApi = createModelApi(authenticatedClient)
      connectionKey.current = `${sidecar.instanceId}:${sidecar.baseUrl}:${sidecar.token}`

      const desktop = await window.autoflow.getSettings?.().catch(() => undefined)
      if (epoch !== connectionEpoch.current) return
      const connected: Extract<AppState, { status: 'connected' }> = {
        status: 'connected',
        instanceId: health.instanceId,
        apiVersion: health.apiVersion,
        modelApi,
        client: authenticatedClient,
        baseUrl: sidecar.baseUrl,
        token: sidecar.token,
        workspaceKey: desktop?.ok ? desktop.value.workspace.path : 'current',
        generation: epoch,
      }
      setSession(connected)
      setState(connected)
    } catch (error) {
      if (epoch === connectionEpoch.current) setState({ status: 'offline', message: offlineMessage(error) })
    } finally { if (epoch === connectionEpoch.current) connecting.current = false }
  }, [])

  useEffect(() => {
    void connect(false)
    void window.autoflow.getSettings?.().then(result => {
      if (result.ok && result.value.workspace.needsSelection) { setRoute('settings'); window.location.hash = '/settings' }
    }).catch(() => undefined)
  }, [connect])

  useEffect(() => {
    const changed = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])

  useEffect(() => {
    let disposed = false
    let timer: number | undefined
    const poll = async () => {
      try {
        const sidecar = await window.autoflow.getSidecarStatus()
        if (!disposed && !connecting.current) {
          if (sidecar.state === 'ready') {
            const key = `${sidecar.instanceId}:${sidecar.baseUrl}:${sidecar.token}`
            if (connectionKey.current !== key) void connect(false)
          } else {
            connectionKey.current = null
            setState(previous => previous.status !== 'connected' ? previous : { status: 'offline', message: sidecar.state === 'starting' ? '本地服务正在重新连接' : '本地服务已停止，可在设置中恢复' })
          }
        }
      } catch { /* Connection/recovery panel reports unavailable bridge state. */ }
      if (!disposed) timer = window.setTimeout(poll, 1000)
    }
    timer = window.setTimeout(poll, 1000)
    return () => { disposed = true; if (timer) window.clearTimeout(timer) }
  }, [connect])

  const navigate = (target: AppRoute) => { setRoute(target); window.location.hash = `/${target}` }
  const settingsAvailable = typeof window.autoflow.getSettings === 'function'
  return <div className="min-h-screen bg-canvas text-ink">
    <ApplicationHeader route={route} onNavigate={navigate} status={state.status} />
    {route === 'settings' ? settingsAvailable
      ? <SettingsPage bridge={window.autoflow as SettingsBridge} restartService={() => window.autoflow.restartSidecar()} onServiceChanged={() => void connect(false)} />
      : <State title="桌面设置不可用" description="请使用 AutoFlow 桌面应用打开设置。" />
    : <>
      {state.status === 'loading' ? <div role="status" className="border-b border-line bg-surface-subtle px-8 py-3 text-sm">正在连接服务…</div> : state.status === 'offline' ? <div role="alert" className="flex items-center justify-between gap-4 border-b border-danger/30 bg-danger-soft px-8 py-3 text-sm text-danger"><span>{state.message}</span><Button type="button" onClick={() => void connect(true)}>重新连接</Button></div> : null}
      {session ? <ApiProvider key={session.workspaceKey} baseUrl={session.baseUrl} token={session.token} instanceId={session.instanceId} client={session.client}>
        <div inert={state.status !== 'connected'} aria-busy={state.status !== 'connected'} className={state.status !== 'connected' ? 'opacity-60' : undefined}>
          {route === 'dashboard' ? <DashboardPage client={session.client} onNavigate={navigate} />
            : route === 'proxies' ? <ProxyManagementPage api={session.client} />
            : route === 'models' ? <ModelManagementPage api={session.modelApi} instanceId={session.instanceId} />
            : <BrowserManagementPage disabled={state.status !== 'connected'} onReconnect={() => void connect(true)} />}
        </div>
      </ApiProvider> : null}
    </>}
  </div>
}
