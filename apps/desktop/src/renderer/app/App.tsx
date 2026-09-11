import { useCallback, useEffect, useState } from 'react'
import { initialAppState, type AppState } from './app-state'
import { createApiClient } from '../shared/api/client'
import { State } from '../shared/components/State'
import type { HealthResponse, SidecarStatus } from '../shared/api/types'

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

  const connect = useCallback(async (restart: boolean) => {
    setState({ status: 'loading' })
    try {
      const sidecar = restart
        ? await window.autoflow.restartSidecar()
        : await getReadySidecarStatus()
      if (sidecar.state !== 'ready') throw new Error('本地服务尚未就绪')

      const health: HealthResponse = await createApiClient({
        baseUrl: sidecar.baseUrl,
        token: sidecar.token,
      }).health()

      setState({
        status: 'connected',
        instanceId: health.instanceId,
        apiVersion: health.apiVersion,
      })
    } catch (error) {
      setState({ status: 'offline', message: offlineMessage(error) })
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
    <State
      title="服务已连接"
      description={`API ${state.apiVersion} · ${state.instanceId}`}
    />
  )
}
