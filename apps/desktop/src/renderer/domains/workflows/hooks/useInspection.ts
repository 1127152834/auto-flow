import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import { inspectionActive, type InspectionApi, type InspectionSession } from '../inspection-api'

export function useInspection(api: InspectionApi, connected: boolean) {
  const [session, setSession] = useState<InspectionSession | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const current = useRef(session)
  const alive = useRef(true)
  const known = useRef(false)
  const generation = useRef(0)
  const operating = useRef(false)
  const pendingStart = useRef<{ sessionId: string; profileId: string } | null>(null)
  const access = useRef({ api, connected }); access.current = { api, connected }
  const accept = useCallback((value: InspectionSession | null) => {
    current.current = value
    known.current = true
    if (alive.current) setSession(value)
  }, [])
  const refresh = useCallback(async (): Promise<InspectionSession | null | undefined> => {
    if (!access.current.connected) return undefined
    const token = generation.current
    try {
      const value = await access.current.api.current() ?? null
      if (!alive.current || token !== generation.current) return undefined
      accept(value)
      if (value?.sessionId === pendingStart.current?.sessionId) pendingStart.current = null
      return value
    } catch (error) {
      if (alive.current) setMessage(error instanceof Error ? error.message : '无法确认拾取会话状态')
      return undefined
    }
  }, [accept])
  useEffect(() => {
    alive.current = true
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      if (!operating.current) await refresh()
      if (!cancelled) timer = setTimeout(() => void poll(), 1000)
    }
    if (connected) void poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [api, connected, refresh])
  useEffect(() => () => { alive.current = false; generation.current++ }, [])
  const perform = async (action: () => Promise<void>) => {
    if (operating.current) return false
    operating.current = true; generation.current++; setBusy(true); setMessage(null)
    try { await action(); return true }
    catch (error) { if (alive.current) setMessage(error instanceof Error ? error.message : '拾取浏览器操作失败'); return false }
    finally { operating.current = false; if (alive.current) setBusy(false) }
  }
  const verifyActive = async (): Promise<boolean | null> => {
    if (!access.current.connected) {
      if (known.current && !inspectionActive(current.current) && !pendingStart.current) return false
      setMessage('请恢复连接后确认拾取浏览器已关闭'); return null
    }
    const value = await refresh()
    if (value === undefined || operating.current) return null
    if (pendingStart.current && value?.sessionId !== pendingStart.current.sessionId) { setMessage('启动结果尚未确认，请重试打开拾取浏览器以核实原请求'); return null }
    return inspectionActive(value)
  }
  const start = (profileId: string) => perform(async () => {
    if (!profileId) throw new Error('请选择浏览器配置')
    pendingStart.current ??= { sessionId: crypto.randomUUID(), profileId }
    const request = pendingStart.current
    try {
      accept(await access.current.api.start(request.sessionId, request.profileId))
      pendingStart.current = null
    } catch (error) {
      if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) pendingStart.current = null
      throw error
    }
  })
  const close = async () => {
    const active = await verifyActive()
    if (active === false) return true
    if (active === null || !current.current) return false
    return perform(async () => {
      const value = await access.current.api.close(current.current!.sessionId)
      accept(value)
      if (inspectionActive(value)) throw new Error('浏览器清理尚未完成，请重试关闭')
    })
  }
  const page = (pageId: string, url?: string, focus = true) => perform(async () => {
    if (!current.current) throw new Error('请先打开拾取浏览器')
    await access.current.api.page(current.current.sessionId, { pageId, url, focus })
    accept(await access.current.api.current())
  })
  return { session, active: inspectionActive(session), busy, message, setMessage, start, close, page, refresh, verifyActive }
}
