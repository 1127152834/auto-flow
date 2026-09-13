import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { components } from '../../shared/api/generated'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import type { ExcelApi, ExcelExportRequest } from './excel-api'

type Operation = components['schemas']['ProjectOperationView']
type Pending = { export: { key: string; tableId: string; body: ExcelExportRequest }; reconciliation?: { key: string; targetOperationId: string; expectedStatusRevision: number } }
type Phase = 'ready' | 'unknown' | 'notAccepted' | 'accepted' | 'complete' | 'failed'
const keyFor = (scope: string) => `autoflow:excel-export:${scope}`
const terminal = (value: Operation) => value.status === 'succeeded' || value.status === 'failed'
const message = (error: unknown) => error instanceof Error ? error.message : '无法导出 Excel 文件'

export function useExcelExport({ api, tableId, scopeKey, contextKey, active, disabled = false, onCompleted }: {
  api: Pick<ExcelApi, 'startExport' | 'lookupExport' | 'reconcileExport' | 'lookupReconcile'>; tableId: string; scopeKey: string; contextKey: string; active: boolean; disabled?: boolean; onCompleted?(operation: Operation): void
}) {
  const [pending, setPending] = useState<Pending | null>(null), [operation, setOperation] = useState<Operation | null>(null), [reconciliation, setReconciliation] = useState<Operation | null>(null)
  const [phase, setPhase] = useState<Phase>('ready'), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false)
  const epoch = useRef(0), lock = useRef(false), available = useRef({ active, disabled }), completed = useRef<string | null>(null)
  useLayoutEffect(() => { available.current = { active, disabled }; return () => { available.current = { active: false, disabled: true } } }, [active, disabled])
  useLayoutEffect(() => {
    epoch.current += 1; lock.current = false; completed.current = null; setPending(null); setOperation(null); setReconciliation(null); setPhase('ready'); setError(null); setBusy(false)
    if (active) try { const raw = localStorage.getItem(keyFor(scopeKey)); if (raw) { const saved = JSON.parse(raw) as Pending; if (!saved?.export?.key || saved.export.tableId !== tableId || !saved.export.body) throw new Error('导出恢复记录不完整'); setPending(saved); setPhase('unknown') } } catch (cause) { setError(message(cause)) }
    return () => { epoch.current += 1; lock.current = false }
  }, [active, contextKey, scopeKey, tableId])
  const currentFor = (ticket: number) => () => ticket === epoch.current && available.current.active
  const accept = useCallback((value: Operation) => {
    setOperation(value); setPhase(value.status === 'succeeded' ? 'complete' : value.status === 'failed' ? 'failed' : 'accepted'); setError(value.error && typeof value.error.message === 'string' ? value.error.message : null)
    if (value.status === 'succeeded' && completed.current !== value.operationId && onCompleted) { completed.current = value.operationId; localStorage.removeItem(keyFor(scopeKey)); setPending(null); onCompleted(value) }
  }, [onCompleted, scopeKey])
  const verifyOriginal = useCallback(async (saved: Pending, current: () => boolean) => { const value = await api.lookupExport(tableId, saved.export.key, current); if (current()) accept(value) }, [accept, api, tableId])
  const refresh = useCallback(async () => {
    if (!pending || lock.current || !available.current.active) return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket)
    try {
      if (pending.reconciliation) {
        const proof = await api.lookupReconcile(tableId, pending.reconciliation.targetOperationId, pending.reconciliation.expectedStatusRevision, pending.reconciliation.key, current)
        if (!current()) return
        setReconciliation(proof)
        if (proof.status === 'succeeded') { const next = { export: pending.export }; localStorage.setItem(keyFor(scopeKey), JSON.stringify(next)); setPending(next); await verifyOriginal(next, current) }
        else if (proof.status === 'failed') setError(proof.error && typeof proof.error.message === 'string' ? proof.error.message : '无法核验原导出结果')
      } else await verifyOriginal(pending, current)
    } catch (cause) { if (current()) { setPhase(cause instanceof DataCommandNotAccepted ? 'notAccepted' : 'unknown'); setError(message(cause)) } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }, [api, pending, scopeKey, verifyOriginal])
  useEffect(() => { if (active && pending && phase === 'unknown') void refresh() }, [active, pending, phase, refresh])
  useEffect(() => { const watched = reconciliation ?? operation; if (!active || !watched || terminal(watched)) return; const timer = setTimeout(() => void refresh(), 750); return () => clearTimeout(timer) }, [active, operation, reconciliation, refresh])
  const submit = async (body: ExcelExportRequest) => {
    if (lock.current || !available.current.active || available.current.disabled || phase !== 'ready') return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket), saved: Pending = { export: { key: crypto.randomUUID(), tableId, body } }
    try { localStorage.setItem(keyFor(scopeKey), JSON.stringify(saved)); setPending(saved); const value = await api.startExport(tableId, body, saved.export.key, current); if (current()) accept(value) }
    catch (cause) { if (current()) { if (cause instanceof DataCommandNotAccepted) setPhase('notAccepted'); else if (cause instanceof DataCommandUncertain) setPhase('unknown'); else { localStorage.removeItem(keyFor(scopeKey)); setPending(null); setPhase('ready') }; setError(message(cause)) } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const retry = async () => {
    if (!pending || pending.reconciliation || phase !== 'notAccepted' || lock.current || available.current.disabled || !available.current.active) return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket), frozen = pending.export
    try { const value = await api.startExport(tableId, frozen.body, frozen.key, current); if (current()) accept(value) }
    catch (cause) { if (current()) { setPhase(cause instanceof DataCommandNotAccepted ? 'notAccepted' : cause instanceof DataCommandUncertain ? 'unknown' : 'ready'); if (!(cause instanceof DataCommandNotAccepted) && !(cause instanceof DataCommandUncertain)) { localStorage.removeItem(keyFor(scopeKey)); setPending(null) }; setError(message(cause)) } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const reconcile = async () => {
    if (!pending || !operation || operation.status !== 'reconciling' || lock.current || available.current.disabled || !available.current.active) return
    lock.current = true; setBusy(true); setError(null); const ticket = epoch.current, current = currentFor(ticket), proof = { key: crypto.randomUUID(), targetOperationId: operation.operationId, expectedStatusRevision: operation.statusRevision }, saved = { ...pending, reconciliation: proof }
    try { localStorage.setItem(keyFor(scopeKey), JSON.stringify(saved)); setPending(saved); const value = await api.reconcileExport(tableId, proof.targetOperationId, proof.expectedStatusRevision, proof.key, current); if (current()) { setReconciliation(value); if (value.status === 'succeeded') { const next = { export: pending.export }; localStorage.setItem(keyFor(scopeKey), JSON.stringify(next)); setPending(next); await verifyOriginal(next, current) } } }
    catch (cause) { if (current()) setError(message(cause)) }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const reset = () => { if (pending && (!operation || !terminal(operation))) return; localStorage.removeItem(keyFor(scopeKey)); setPending(null); setOperation(null); setReconciliation(null); setPhase('ready'); setError(null) }
  return { pending, operation, reconciliation, phase, error, busy, submit, retry, refresh, reconcile, reset }
}
