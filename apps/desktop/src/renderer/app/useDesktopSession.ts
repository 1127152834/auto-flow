import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError, createApiClient, type ApiRequestInit, type StreamingApiClient } from '../shared/api/client'
import type { DesktopRuntimeContext } from '../../shared/runtime'

export type DesktopSession = {
  workspaceKey: string
  instanceId: string
  apiVersion: string
  baseUrl: string
  token: string
  client: StreamingApiClient
}

const runtimeKey = (runtime: DesktopRuntimeContext) => runtime.sidecar.state === 'ready'
  ? `${runtime.workspaceKey}:${runtime.sidecar.instanceId}:${runtime.sidecar.baseUrl}:${runtime.sidecar.token}` : null

/** Keeps the main application connected to its current workspace service. */
export function useDesktopSession() {
  const [session, setSession] = useState<DesktopSession | null>(null)
  const [status, setStatus] = useState<'loading' | 'connected' | 'offline'>('loading')
  const [message, setMessage] = useState<string | null>(null)
  const [workspaceChanging, setWorkspaceChanging] = useState(false)
  const connectionEpoch = useRef(0)
  const connectionKey = useRef<string | null>(null)
  const connecting = useRef(false)
  const authRecoveryAttempted = useRef(false)
  const workspaceKey = useRef<string | null>(null)

  const connect = useCallback(async (restart: boolean, initial?: DesktopRuntimeContext) => {
    const epoch = ++connectionEpoch.current
    connecting.current = true
    if (restart) authRecoveryAttempted.current = false
    setStatus('loading'); setMessage(null)
    try {
      if (restart) await window.autoflow.restartSidecar()
      const deadline = Date.now() + 10_000
      let runtime = initial ?? await window.autoflow.getRuntimeContext()
      while (runtime.sidecar.state !== 'ready') {
        if (epoch !== connectionEpoch.current) return
        setWorkspaceChanging(runtime.operation === 'switching')
        if (runtime.sidecar.state === 'failed') throw new Error(runtime.sidecar.message)
        if (Date.now() >= deadline) throw new Error('等待本地服务就绪超时')
        await new Promise(resolve => window.setTimeout(resolve, 50))
        runtime = await window.autoflow.getRuntimeContext()
      }
      if (epoch !== connectionEpoch.current) return
      setWorkspaceChanging(workspaceKey.current !== null && workspaceKey.current !== runtime.workspaceKey)
      const sidecar = runtime.sidecar
      const client = createApiClient({ baseUrl: sidecar.baseUrl, token: sidecar.token })
      const health = await client.health()
      if (epoch !== connectionEpoch.current) return
      if (health.instanceId !== sidecar.instanceId || health.apiVersion !== sidecar.apiVersion) throw new Error('本地服务身份已变化，请重新连接')
      const recoverAuth = (error: unknown) => {
        if (error instanceof ApiClientError && (error.code === 'SIDECAR_UNAUTHORIZED' || (error.status === 401 && !error.code)) && epoch === connectionEpoch.current) {
          if (authRecoveryAttempted.current) { setStatus('offline'); setMessage('本地服务认证失效，请重新连接') }
          else { authRecoveryAttempted.current = true; void connect(false) }
        }
        throw error
      }
      const authenticatedClient: StreamingApiClient = {
        ...client,
        async request<T>(path: string, init?: ApiRequestInit) {
          try { return await client.request<T>(path, init) } catch (error) { return recoverAuth(error) }
        },
        async stream(path, init) {
          try { return await client.stream(path, init) } catch (error) { return recoverAuth(error) }
        },
      }
      connectionKey.current = runtimeKey(runtime)
      workspaceKey.current = runtime.workspaceKey
      setWorkspaceChanging(false)
      setSession({ workspaceKey: runtime.workspaceKey, instanceId: health.instanceId, apiVersion: health.apiVersion, baseUrl: sidecar.baseUrl, token: sidecar.token, client: authenticatedClient })
      setStatus('connected')
    } catch (error) {
      if (epoch === connectionEpoch.current) { setStatus('offline'); setMessage(error instanceof Error ? error.message : '无法连接到本地服务') }
    } finally { if (epoch === connectionEpoch.current) connecting.current = false }
  }, [])

  useEffect(() => {
    void connect(false)
    const unsubscribe = window.autoflow.onRuntimeContextChanged?.(runtime => {
      setWorkspaceChanging(runtime.operation === 'switching' || (workspaceKey.current !== null && workspaceKey.current !== runtime.workspaceKey))
      void connect(false, runtime)
    })
    let disposed = false
    let timer: number | undefined
    const poll = async () => {
      const epoch = connectionEpoch.current
      try {
        const runtime = await window.autoflow.getRuntimeContext()
        if (!disposed && !connecting.current && epoch === connectionEpoch.current) {
          setWorkspaceChanging(runtime.operation === 'switching')
          if (runtime.sidecar.state === 'ready') {
            if (connectionKey.current !== runtimeKey(runtime)) void connect(false, runtime)
          } else {
            connectionKey.current = null
            setStatus('offline')
            setMessage(runtime.sidecar.state === 'starting' ? '本地服务正在重新连接' : '本地服务已停止，可在设置中恢复')
          }
        }
      } catch {
        if (!disposed && !connecting.current && epoch === connectionEpoch.current) { connectionKey.current = null; setStatus('offline'); setMessage('无法读取本地服务状态，请重新连接') }
      }
      if (!disposed) timer = window.setTimeout(poll, 1000)
    }
    timer = window.setTimeout(poll, 1000)
    return () => {
      disposed = true
      connectionEpoch.current += 1
      connecting.current = false
      if (timer) window.clearTimeout(timer)
      unsubscribe?.()
    }
  }, [connect])

  const reconnect = useCallback((restart = false) => { authRecoveryAttempted.current = false; return connect(restart) }, [connect])
  return { session, status, message, reconnect, workspaceChanging }
}
