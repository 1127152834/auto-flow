import { useCallback, useEffect, useRef, useState } from 'react'
import { initialAppState, type AppState } from './app-state'
import { ApiClientError, createApiClient, type ApiRequestInit } from '../shared/api/client'
import { State } from '../shared/components/State'
import type { HealthResponse, SidecarStatus } from '../shared/api/types'
import { createModelApi } from '../domains/models/api'
import { ModelManagementPage } from '../domains/models/pages/ModelManagementPage'
import { QueryProvider } from './query-provider'

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
  const connectionEpoch = useRef(0)
  const authRecoveryAttempted = useRef(false)

  const connect = useCallback(async (restart: boolean) => {
    const epoch = ++connectionEpoch.current
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
      const modelApi = createModelApi({ ...client, async request<T>(path: string, init?: ApiRequestInit) {
        try { return await client.request<T>(path, init) }
        catch (error) {
          if (error instanceof ApiClientError && error.code === 'SIDECAR_UNAUTHORIZED' && epoch === connectionEpoch.current) {
            if (authRecoveryAttempted.current) setState({ status: 'offline', message: '本地服务认证失效，请重新连接' })
            else { authRecoveryAttempted.current = true; void connect(false) }
          }
          throw error
        }
      } })

      setState({
        status: 'connected',
        instanceId: health.instanceId,
        apiVersion: health.apiVersion,
        modelApi,
        generation: epoch,
      })
    } catch (error) {
      if (epoch === connectionEpoch.current) setState({ status: 'offline', message: offlineMessage(error) })
    }
  }, [])

  useEffect(() => {
    void connect(false)
  }, [connect])

  if (state.status === 'loading') {
    return <State title="正在连接服务..." description="正在检查本地服务状态" />
  }

  if (state.status === 'offline') {
    return (
      <State
        title="服务未连接"
        description={state.message}
        action={<button type="button" onClick={() => void connect(true)}>重新连接</button>}
      />
    )
  }

  return (
    <QueryProvider key={`${state.instanceId}-${state.generation}`}>
      <div className="min-h-screen bg-canvas text-ink">
        <header className="flex h-20 items-center gap-12 border-b border-line bg-surface px-8 max-[640px]:gap-6 max-[640px]:px-4">
          <span className="flex items-center gap-3 text-xl font-semibold"><span aria-hidden="true" className="grid h-9 w-9 place-items-center rounded-lg bg-clay text-white">A</span>AutoFlow</span>
          <nav aria-label="全局导航" className="flex h-full items-stretch"><span aria-current="page" className="flex items-center border-b-2 border-clay text-sm font-semibold text-clay">模型管理</span></nav>
          <span role="status" className="ml-auto flex items-center gap-2 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-sage" />本地服务正常</span>
        </header>
        <ModelManagementPage api={state.modelApi} instanceId={state.instanceId} />
      </div>
    </QueryProvider>
  )
}
