import { useCallback, useEffect, useRef, useState } from 'react'
import type { Recording, RecordingApi, RecordingCommand, RecordingStep } from '../recording-api'
import { recordingActive } from '../recording-api'

export function useWorkflowRecording(api: RecordingApi, connected: boolean) {
  const [record, setRecord] = useState<Recording | null>(null)
  const [history, setHistory] = useState<Recording[]>([])
  const [steps, setSteps] = useState<RecordingStep[]>([])
  const [after, setAfter] = useState(0)
  const [next, setNext] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const current = useRef(record); current.current = record
  const selected = useRef<string | null>(null)
  const access = useRef({ api, connected }); access.current = { api, connected }
  const alive = useRef(true)
  const operating = useRef(false)
  const pendingStart = useRef<Parameters<RecordingApi['start']>[0] | null>(null)
  const pendingCommand = useRef<{ id: string; request: RecordingCommand } | null>(null)
  const flushReview = useRef<() => Promise<boolean>>(async () => true)
  const refresh = useCallback(async () => {
    if (!access.current.connected) return undefined
    try {
      const list = await access.current.api.list()
      if (!alive.current) return undefined
      setHistory(list.items)
      const id = selected.current ?? list.items.find(recordingActive)?.recordingId ?? list.items[0]?.recordingId
      const value = id ? await access.current.api.get(id) : null
      if (!alive.current || selected.current && id !== selected.current) return undefined
      current.current = value; setRecord(value)
      return list.items.some(recordingActive)
    } catch (error) { if (alive.current) setMessage(error instanceof Error ? error.message : '无法确认录制状态'); return undefined }
  }, [])
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
  useEffect(() => () => { alive.current = false }, [])
  useEffect(() => {
    if (!connected || !record) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const id = record.recordingId
    const load = async () => {
      try {
        const data = await api.steps(id, after)
        if (!cancelled) { setSteps(data.items); setNext(data.nextAfter) }
      } catch (error) { if (!cancelled) setMessage(error instanceof Error ? error.message : '录制步骤读取失败') }
      if (!cancelled && recordingActive(record)) timer = setTimeout(() => void load(), 500)
    }
    void load()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [api, connected, record?.recordingId, record?.revision, record?.captureState, after]) // eslint-disable-line react-hooks/exhaustive-deps

  const perform = async (action: () => Promise<void>) => {
    if (operating.current || !access.current.connected) return false
    operating.current = true; setBusy(true); setMessage(null)
    try { await action(); await refresh(); return true }
    catch (error) { if (alive.current) setMessage(error instanceof Error ? error.message : '录制操作失败'); return false }
    finally { operating.current = false; if (alive.current) setBusy(false) }
  }
  const command = (action: RecordingCommand['action'], patch: Partial<RecordingCommand> = {}) => perform(async () => {
    const value = current.current
    if (!value) throw new Error('请先打开录制浏览器')
    pendingCommand.current ??= { id: value.recordingId, request: { commandId: crypto.randomUUID(), expectedRevision: value.revision, action, ...patch } }
    const pending = pendingCommand.current
    let result = await access.current.api.command(pending.id, pending.request)
    const deadline = Date.now() + 120000
    while (result.state === 'accepted' && Date.now() < deadline && alive.current) {
      await new Promise(resolve => setTimeout(resolve, 200))
      result = await access.current.api.readCommand(pending.id, pending.request.commandId)
    }
    if (result.state === 'accepted') throw new Error('命令仍待确认，请查询原请求')
    pendingCommand.current = null
    if (result.state !== 'applied') throw new Error(result.error ?? '命令未能确认')
  })
  const start = (profileId: string, documentId: string) => perform(async () => {
    if (!profileId) throw new Error('请选择浏览器配置')
    pendingStart.current ??= { recordingId: crypto.randomUUID(), profileId, sourceDocumentId: documentId }
    const value = await access.current.api.start(pendingStart.current)
    selected.current = value.recordingId; current.current = value; setRecord(value); setAfter(0)
    pendingStart.current = null
  })
  const verifyActive = async (): Promise<boolean | null> => {
    if (operating.current) return null
    const value = await refresh()
    return value === undefined || pendingStart.current ? null : value
  }
  const close = async () => {
    if (!await flushReview.current()) return false
    const active = await verifyActive()
    if (active === null) return false
    if (!active) return true
    const list = await access.current.api.list()
    const live = list.items.find(recordingActive)
    if (!live) return true
    selected.current = live.recordingId; current.current = live; setRecord(live)
    return command('close')
  }
  return { api, record, history, steps, after, next, busy, message, setMessage, active: history.some(recordingActive) || recordingActive(record),
    start, command, refresh, verifyActive, close, perform, flushReview,
    select: async (id: string) => { if (!await flushReview.current()) return; selected.current = id; setAfter(0); await refresh() },
    page: (pageId: string, url?: string) => command('page', { pageId, url, focus: true }),
    nextPage: () => { if (next !== null) setAfter(next) }, firstPage: () => setAfter(0),
  }
}
export type WorkflowRecording = ReturnType<typeof useWorkflowRecording>
