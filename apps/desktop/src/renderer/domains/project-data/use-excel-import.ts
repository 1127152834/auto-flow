import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { components } from '../../shared/api/generated'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import type { ExcelApi, ExcelImportRequest, ExcelReplaceRequest } from './excel-api'

type Operation = components['schemas']['ProjectOperationView']
type Body = { mode: 'create'; request: ExcelImportRequest } | { mode: 'replace'; tableId: string; request: ExcelReplaceRequest }
type Pending = { key: string; body: Body }
type Phase = 'ready' | 'unknown' | 'notAccepted' | 'accepted' | 'complete' | 'failed'
const storageKey = (scope: string) => `autoflow:excel-import:${scope}`
const terminal = (operation: Operation) => operation.status === 'succeeded' || operation.status === 'failed'
const message = (error: unknown) => error instanceof Error ? error.message : '无法提交 Excel 导入'

export function useExcelImport({ api, scopeKey, contextKey, active, disabled = false, onCompleted }: {
  api: Pick<ExcelApi, 'startImport' | 'replace' | 'lookupImport'>; scopeKey: string; contextKey: string; active: boolean; disabled?: boolean
  onCompleted?(operation: Operation): void
}) {
  const [pending, setPending] = useState<Pending | null>(null), [operation, setOperation] = useState<Operation | null>(null)
  const [phase, setPhase] = useState<Phase>('ready'), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false)
  const epoch = useRef(0), lock = useRef(false), available = useRef({ active, disabled }), completed = useRef<string | null>(null)
  useLayoutEffect(() => { available.current = { active, disabled } }, [active, disabled])
  useLayoutEffect(() => {
    epoch.current += 1; lock.current = false; completed.current = null; setBusy(false); setError(null); setOperation(null); setPending(null); setPhase('ready')
    if (active) try {
      const raw = localStorage.getItem(storageKey(scopeKey))
      if (raw) {
        const saved = JSON.parse(raw) as Pending
        if (!saved?.key || !saved.body?.mode || !saved.body.request) throw new Error('导入恢复记录不完整')
        setPending(saved); setPhase('unknown')
      }
    } catch (cause) { setError(message(cause)) }
    return () => { epoch.current += 1; lock.current = false }
  }, [active, contextKey, scopeKey])
  const accept = useCallback((value: Operation) => {
    setOperation(value); setPhase(value.status === 'succeeded' ? 'complete' : value.status === 'failed' ? 'failed' : 'accepted')
    setError(value.error && typeof value.error.message === 'string' ? value.error.message : null)
    if (value.status === 'succeeded' && completed.current !== value.operationId && onCompleted) { completed.current = value.operationId; localStorage.removeItem(storageKey(scopeKey)); setPending(null); onCompleted(value) }
  }, [onCompleted, scopeKey])
  const currentFor = (ticket: number) => () => ticket === epoch.current && available.current.active
  const refresh = useCallback(async () => {
    if (!pending || lock.current || !available.current.active) return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket)
    try { const value = await api.lookupImport(pending.key, current, pending.body.mode === 'replace' ? pending.body.tableId : undefined); if (current()) accept(value) }
    catch (cause) { if (current()) { setPhase(cause instanceof DataCommandNotAccepted ? 'notAccepted' : 'unknown'); setError(message(cause)) } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }, [accept, api, pending])
  useEffect(() => { if (active && pending && phase === 'unknown') void refresh() }, [active, pending, phase, refresh])
  useEffect(() => { if (!active || !operation || terminal(operation) || phase !== 'accepted') return; const timer = setTimeout(() => void refresh(), 750); return () => clearTimeout(timer) }, [active, operation, phase, refresh])
  const submit = async (body: Body) => {
    if (lock.current || !available.current.active || available.current.disabled || !['ready', 'notAccepted'].includes(phase)) return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket)
    const identity = phase === 'notAccepted' && pending ? pending : { key: crypto.randomUUID(), body }
    try {
      localStorage.setItem(storageKey(scopeKey), JSON.stringify(identity)); setPending(identity)
      const value = identity.body.mode === 'create' ? await api.startImport(identity.body.request, identity.key, current) : await api.replace(identity.body.tableId, identity.body.request, identity.key, current)
      if (current()) accept(value)
    } catch (cause) { if (current()) {
      if (cause instanceof DataCommandNotAccepted) setPhase('notAccepted')
      else if (cause instanceof DataCommandUncertain) setPhase('unknown')
      else { localStorage.removeItem(storageKey(scopeKey)); setPending(null); setPhase('ready') }
      setError(message(cause))
    } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const reset = () => { if (pending && (!operation || !terminal(operation))) return; localStorage.removeItem(storageKey(scopeKey)); setPending(null); setOperation(null); setPhase('ready'); setError(null) }
  return { pending, operation, phase, error, busy, submit, refresh, reset }
}
