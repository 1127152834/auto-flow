import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { WorkflowRunApi } from '../run-api'
import { isRunActive, type RunEvent, type RunRead, type RunStart, type RunSummary } from '../run-types'
import type { WorkflowContent, WorkflowDocument, WorkflowIssue } from '../types'

const errorMessage = (error: unknown) => error instanceof Error ? error.message : '无法读取运行状态，请恢复连接后核实'

export function mergeRunEvents(current: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  return [...new Map([...current, ...incoming].map(event => [event.seq, event])).values()].sort((a, b) => a.seq - b.seq)
}

function mergeHistory(current: RunSummary[], incoming: RunSummary[]): RunSummary[] {
  const items = new Map(current.map(item => [item.runId, item]))
  for (const item of incoming) {
    const previous = items.get(item.runId)
    if (!previous || (previous.latestSeq <= item.latestSeq && (isRunActive(previous) || !isRunActive(item)))) items.set(item.runId, item)
  }
  return [...items.values()].sort((a, b) => b.startedAt.localeCompare(a.startedAt))
}

/** Independent of editor undo and query caches: reconnecting never creates a new run. */
export function useWorkflowRun(api: WorkflowRunApi, connected: boolean) {
  const [records, setRecords] = useState<Record<string, RunRead>>({})
  const recordsRef = useRef(records)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selectedRef = useRef(selectedId)
  const [activeId, setActiveId] = useState<string | null>(null)
  const activeRef = useRef<string | null>(null)
  const [events, setEvents] = useState<Record<string, RunEvent[]>>({})
  const eventsRef = useRef(events)
  const eventCursors = useRef<Record<string, number>>({})
  const [history, setHistory] = useState<RunSummary[]>([])
  const [nextOffset, setNextOffset] = useState<number | null>(null)
  const olderPagesLoaded = useRef(false)
  const [uncertain, setUncertain] = useState(true)
  const verified = useRef(false)
  const knownIdle = useRef(false)
  const pendingStart = useRef<RunStart | null>(null)
  const commandEpoch = useRef(0)
  const [canRetryStart, setCanRetryStart] = useState(false)
  const [validation, setValidation] = useState<{ document: WorkflowDocument; issues: WorkflowIssue[] } | null>(null)
  const busyRef = useRef(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const currentApi = useRef(api)
  currentApi.current = api
  const online = useRef(connected)
  online.current = connected
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const select = useCallback((id: string) => { selectedRef.current = id; setSelectedId(id) }, [])
  const markActive = useCallback((id: string | null) => { activeRef.current = id; setActiveId(id) }, [])
  const accept = useCallback((record: RunRead) => {
    if (!alive.current) return record
    const previous = recordsRef.current[record.runId]
    if (previous && (previous.latestSeq > record.latestSeq || (!isRunActive(previous) && isRunActive(record)))) return previous
    recordsRef.current = { ...recordsRef.current, [record.runId]: record }
    setRecords(recordsRef.current)
    setHistory(items => mergeHistory(items, [record]))
    if (!isRunActive(record) && activeRef.current === record.runId) { markActive(null); knownIdle.current = !pendingStart.current }
    return record
  }, [markActive])
  const append = useCallback((id: string, incoming: RunEvent[]) => {
    if (!alive.current) return
    const merged = mergeRunEvents(eventsRef.current[id] ?? [], incoming.filter(event => event.runId === id))
    let cursor = eventCursors.current[id] ?? 0
    for (const event of merged) { if (event.seq <= cursor) continue; if (event.seq !== cursor + 1) break; cursor = event.seq }
    eventCursors.current[id] = cursor
    eventsRef.current = { ...eventsRef.current, [id]: merged.slice(-1000) }
    setEvents(eventsRef.current)
  }, [])

  const verifyActive = useCallback(async (): Promise<boolean | null> => {
    if (!online.current) {
      if (knownIdle.current && !pendingStart.current && !activeRef.current) return false
      setUncertain(true); verified.current = false; setMessage('连接中断，无法确认运行已停止，请先恢复连接'); return null
    }
    const source = currentApi.current
    const epoch = commandEpoch.current
    const isCurrent = () => source === currentApi.current && alive.current && online.current && epoch === commandEpoch.current
    try {
      if (pendingStart.current) {
        const record = await source.get(pendingStart.current.runId)
        if (!isCurrent()) return null
        const confirmed = accept(record)
        pendingStart.current = null
        setCanRetryStart(false)
        select(record.runId)
        if (isRunActive(confirmed)) markActive(record.runId)
      }
      const list = await source.list()
      if (!isCurrent()) return null
      setHistory(items => mergeHistory(items, list.items))
      if (!olderPagesLoaded.current) setNextOffset(list.nextOffset)
      const id = list.activeRunId ?? activeRef.current
      if (id) {
        const record = await source.get(id)
        if (!isCurrent()) return null
        const confirmed = accept(record)
        markActive(isRunActive(confirmed) ? id : null)
        if (!selectedRef.current) select(id)
      } else markActive(null)
      if (pendingStart.current) { setUncertain(true); return null }
      if (!selectedRef.current && list.items[0]) select(list.items[0].runId)
      verified.current = true
      knownIdle.current = !activeRef.current
      setUncertain(false)
      setMessage(null)
      return Boolean(activeRef.current)
    } catch (error) {
      if (isCurrent()) {
        verified.current = false
        setUncertain(true)
        setMessage(pendingStart.current ? '启动结果尚未确认，正在按原运行编号核实；不会自动重新运行。' : errorMessage(error))
      }
      return null
    }
  }, [accept, markActive, select])

  const submit = useCallback(async (request: RunStart) => {
    commandEpoch.current += 1
    pendingStart.current = request
    knownIdle.current = false
    busyRef.current = true
    setBusy(true)
    setUncertain(true)
    setMessage(null)
    setValidation(null)
    setCanRetryStart(false)
    try {
      const record = await currentApi.current.start(request)
      if (!alive.current) return
      const confirmed = accept(record)
      pendingStart.current = null
      select(record.runId)
      markActive(isRunActive(confirmed) ? record.runId : null)
      knownIdle.current = !isRunActive(confirmed)
      setUncertain(false)
    } catch (error) {
      if (!alive.current) return
      if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) {
        pendingStart.current = null
        await verifyActive()
        setMessage(errorMessage(error))
        const issues = Array.isArray(error.details.issues) ? error.details.issues.filter((value): value is WorkflowIssue => {
          if (!value || typeof value !== 'object') return false
          const issue = value as Record<string, unknown>
          return typeof issue.code === 'string' && typeof issue.message === 'string' && (issue.nodeId === null || typeof issue.nodeId === 'string') && Array.isArray(issue.path) && issue.path.every(part => typeof part === 'string')
        }) : []
        setValidation({ document: request.document, issues })
      } else { await verifyActive(); setCanRetryStart(Boolean(pendingStart.current)) }
    } finally {
      busyRef.current = false
      if (alive.current) setBusy(false)
    }
  }, [accept, markActive, select, verifyActive])

  const start = useCallback(async (content: WorkflowContent, resource: string | NonNullable<RunStart['target']>, debug?: RunStart['debug']) => {
    if (!online.current || busyRef.current || activeRef.current || pendingStart.current || !verified.current) return
    await submit({ ...structuredClone(content), ...(typeof resource === 'string' ? { profileId: resource } : { target: resource }), runId: crypto.randomUUID(), mode: 'run', ...(debug ? { mode: 'debug' as const, debug } : {}) })
  }, [submit])
  const retryStart = useCallback(async () => {
    if (!online.current || busyRef.current || !pendingStart.current) return
    await submit(pendingStart.current)
  }, [submit])

  const stop = useCallback(async (): Promise<boolean> => {
    if (busyRef.current) return false
    commandEpoch.current += 1
    busyRef.current = true
    setBusy(true)
    try {
      const active = await verifyActive()
      if (active === null) return false
      if (!active) return true
      const id = activeRef.current!
      let record: RunRead
      try { record = await currentApi.current.stop(id) }
      catch { record = await currentApi.current.get(id) }
      const confirmed = accept(record)
      if (isRunActive(confirmed)) { setUncertain(true); setMessage('运行仍在停止或清理中，请确认结束后再离开'); return false }
      markActive(null)
      knownIdle.current = true
      setUncertain(false)
      setMessage(null)
      return true
    } catch (error) {
      setUncertain(true)
      setMessage(errorMessage(error))
      return false
    } finally { busyRef.current = false; if (alive.current) setBusy(false) }
  }, [accept, markActive, verifyActive])

  useEffect(() => {
    verified.current = false
    setUncertain(connected || !knownIdle.current || Boolean(pendingStart.current))
    if (!connected) return
    void verifyActive()
    const timer = window.setInterval(() => { if (!busyRef.current) void verifyActive() }, 5_000)
    return () => window.clearInterval(timer)
  }, [api, connected, verifyActive])

  useEffect(() => {
    if (!connected || !selectedId) return
    const controller = new AbortController()
    let retry: number | undefined
    let refreshTimer: number | undefined
    let eventTimer: number | undefined
    let buffered: RunEvent[] = []
    const flushEvents = () => {
      if (eventTimer !== undefined) window.clearTimeout(eventTimer)
      eventTimer = undefined
      if (buffered.length) { append(selectedId, buffered); buffered = [] }
    }
    const refreshState = () => {
      if (refreshTimer !== undefined) return
      refreshTimer = window.setTimeout(() => {
        refreshTimer = undefined
        void api.get(selectedId).then(value => { if (!controller.signal.aborted) accept(value) }).catch(() => undefined)
      }, 200)
    }
    const cursor = () => eventCursors.current[selectedId] ?? 0
    const read = async () => {
      try {
        const record = await api.get(selectedId)
        if (controller.signal.aborted) return
        accept(record)
        let more = true
        while (more && !controller.signal.aborted) {
          const before = cursor()
          const page = await api.events(selectedId, before)
          if (controller.signal.aborted) return
          append(selectedId, page.items)
          if (page.hasMore && cursor() <= before) throw new Error('日志序号不连续，正在重新补读')
          more = page.hasMore
        }
        if (!isRunActive(record) || controller.signal.aborted) return
        await api.watch(selectedId, cursor(), controller.signal, event => {
          buffered.push(event)
          if (eventTimer === undefined) eventTimer = window.setTimeout(flushEvents, 50)
          if (event.type !== 'log') refreshState()
        })
      } catch (error) { if (!controller.signal.aborted) setMessage(errorMessage(error)) }
      flushEvents()
      if (!controller.signal.aborted) retry = window.setTimeout(() => void read(), 1_000)
    }
    void read()
    return () => { controller.abort(); flushEvents(); if (refreshTimer !== undefined) window.clearTimeout(refreshTimer); if (retry !== undefined) window.clearTimeout(retry) }
  }, [accept, api, append, connected, selectedId])

  const more = async () => {
    if (nextOffset === null || !online.current) return
    try {
      const list = await currentApi.current.list(nextOffset)
      olderPagesLoaded.current = true
      setHistory(items => mergeHistory(items, list.items))
      setNextOffset(list.nextOffset)
    } catch (error) { setMessage(errorMessage(error)) }
  }
  return {
    run: selectedId ? records[selectedId] ?? null : null, active: activeId ? records[activeId] ?? null : null,
    events: selectedId ? events[selectedId] ?? [] : [], history, nextOffset, uncertain, busy, message, validation, canRetryStart,
    start, retryStart, stop, select, more, refresh: verifyActive, verifyActive,
  }
}
