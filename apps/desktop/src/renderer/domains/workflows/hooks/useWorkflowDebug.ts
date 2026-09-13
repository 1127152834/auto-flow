import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { WorkflowRunApi } from '../run-api'
import type { DebugCommand, DebugCommandRead, RunRead } from '../run-types'

export function useWorkflowDebug(api: WorkflowRunApi, run: RunRead, connected: boolean, refresh: () => void) {
  const [pending, setPending] = useState<DebugCommand | null>(null)
  const [error, setError] = useState('')
  const [response, setResponse] = useState<DebugCommandRead | null>(null)
  const busy = useRef(false)
  const requestRef = useRef<DebugCommand | null>(null)
  const [appliedAction, setAppliedAction] = useState<DebugCommand['action'] | null>(null)
  const current = useRef(run)
  current.current = run
  const accept = useCallback((value: DebugCommandRead) => {
    if (value.state === 'accepted' || value.commandId !== requestRef.current?.commandId) return
    setAppliedAction(value.state === 'applied' ? requestRef.current?.action ?? null : null)
    requestRef.current = null; busy.current = false; setPending(null); setResponse(value)
    setError(value.error?.message ?? (value.state === 'interrupted' ? '命令随服务中断，未自动重放' : ''))
    refresh()
  }, [refresh])
  useEffect(() => {
    if (!pending || !connected) return
    let alive = true
    const poll = () => void api.debugCommandStatus(run.runId, pending.commandId).then(value => { if (alive) accept(value) }).catch(() => { if (alive) setError('命令结果尚未确认，正在按原编号查询') })
    poll(); const timer = window.setInterval(poll, 500)
    return () => { alive = false; window.clearInterval(timer) }
  }, [accept, api, connected, pending, run.runId])
  const send = async (action: DebugCommand['action'], values: Partial<DebugCommand> = {}) => {
    if (busy.current || !connected) return
    busy.current = true; setError('')
    const state = current.current.debug
    const request: DebugCommand = { focus: false, ...values, action, commandId: crypto.randomUUID(), expectedRevision: Number(state?.controlRevision ?? 0), pauseId: typeof state?.pauseId === 'string' ? state.pauseId : null }
    requestRef.current = request; setPending(request)
    try { accept(await api.debugCommand(run.runId, request)) }
    catch (e) { if (e instanceof ApiClientError && e.status >= 400 && e.status < 500) { requestRef.current = null; busy.current = false; setPending(null); setError(e.message) } else setError('命令结果尚未确认，正在查询；不会重复执行') }
  }
  return { send, pending, response, appliedAction, error }
}
