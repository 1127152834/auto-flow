import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ProjectFileSelection } from '../../../shared/project-files'
import type { components } from '../../shared/api/generated'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import type { ExcelApi, ExcelInspection } from './excel-api'

type Operation = components['schemas']['ProjectOperationView']
type Pending = { key: string; selection: ProjectFileSelection }
type Phase = 'ready' | 'unknown' | 'notAccepted' | 'accepted' | 'complete' | 'failed'
const storageKey = (scope: string) => `autoflow:excel-inspection:${scope}`
const message = (error: unknown) => error instanceof Error ? error.message : '无法检查文件'
const terminal = (operation: Operation) => operation.status === 'succeeded' || operation.status === 'failed'

export function useExcelInspection({ api, chooseInput, scopeKey, contextKey, active, disabled = false }: {
  api: Pick<ExcelApi, 'inspect' | 'lookupInspection'>; chooseInput(): Promise<ProjectFileSelection | null>
  /** Stable workspace/project scope, excluding the service instance. */
  scopeKey: string; contextKey: string; active: boolean; disabled?: boolean
}) {
  const [selection, setSelection] = useState<ProjectFileSelection | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [operation, setOperation] = useState<Operation | null>(null)
  const [phase, setPhase] = useState<Phase>('ready')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const epoch = useRef(0), lock = useRef(false), available = useRef({ active, disabled })
  useLayoutEffect(() => { available.current = { active, disabled } }, [active, disabled])
  useLayoutEffect(() => {
    epoch.current += 1; lock.current = false
    setBusy(false); setError(null); setSelection(null); setPending(null); setOperation(null); setPhase('ready')
    if (active) {
      try {
        const saved = window.localStorage.getItem(storageKey(scopeKey))
        if (saved) {
          const value: unknown = JSON.parse(saved)
          if (!value || typeof value !== 'object' || !('key' in value) || typeof value.key !== 'string' || !('selection' in value)) throw new Error('文件检查记录不完整')
          const record = value as Pending
          if (typeof record.selection?.selectionToken !== 'string' || typeof record.selection.expiresAt !== 'string') throw new Error('文件检查记录不完整')
          setPending(record); setSelection(record.selection); setPhase('unknown')
        }
      } catch (cause) { setError(message(cause)) }
    }
    return () => { epoch.current += 1; lock.current = false }
  }, [scopeKey, contextKey, active])
  const accept = useCallback((value: Operation) => {
    setOperation(value)
    setPhase(value.status === 'succeeded' ? 'complete' : value.status === 'failed' ? 'failed' : 'accepted')
    setError(value.error && typeof value.error.message === 'string' ? value.error.message : null)
  }, [])
  const refresh = useCallback(async () => {
    if (!pending || lock.current || !available.current.active) return
    lock.current = true; setBusy(true); setError(null)
    const ticket = epoch.current, current = () => ticket === epoch.current && available.current.active
    try { const value = await api.lookupInspection(pending.key, current); if (current()) accept(value) }
    catch (cause) { if (current()) { setPhase(cause instanceof DataCommandNotAccepted ? 'notAccepted' : 'unknown'); setError(message(cause)) } }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }, [accept, api, pending])
  useEffect(() => { if (active && pending && phase === 'unknown') void refresh() }, [active, pending, refresh])
  useEffect(() => {
    if (!active || !operation || terminal(operation) || phase !== 'accepted') return
    const timer = window.setTimeout(() => { void refresh() }, 750)
    return () => window.clearTimeout(timer)
  }, [active, operation, phase, refresh])
  const choose = async () => {
    if (lock.current || !available.current.active || available.current.disabled || (pending && phase !== 'complete' && phase !== 'failed' && phase !== 'notAccepted')) return
    lock.current = true; setBusy(true); setError(null)
    const ticket = epoch.current, current = () => ticket === epoch.current && available.current.active
    try {
      const value = await chooseInput()
      if (!current() || !value) return
      window.localStorage.removeItem(storageKey(scopeKey))
      setSelection(value); setPending(null); setOperation(null); setPhase('ready')
    } catch (cause) { if (current()) setError(message(cause)) }
    finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const submit = async () => {
    if (!selection || lock.current || !available.current.active || available.current.disabled || (phase !== 'ready' && phase !== 'notAccepted')) return
    if (Date.parse(selection.expiresAt) <= Date.now()) { setError('文件授权已过期，请重新选择文件'); return }
    lock.current = true; setBusy(true); setError(null)
    const ticket = epoch.current, current = () => ticket === epoch.current && available.current.active
    const identity = pending ?? { key: crypto.randomUUID(), selection }
    try {
      // Persist before sending so closing the view or losing the response never creates a new identity.
      window.localStorage.setItem(storageKey(scopeKey), JSON.stringify(identity)); setPending(identity)
      const value = await api.inspect(selection.selectionToken, identity.key, current)
      if (current()) accept(value)
    } catch (cause) {
      if (current()) {
        if (cause instanceof DataCommandNotAccepted) setPhase('notAccepted')
        else if (cause instanceof DataCommandUncertain) setPhase('unknown')
        else { setPhase('failed'); setError(message(cause)); return }
        setError(message(cause))
      }
    } finally { if (current()) { lock.current = false; setBusy(false) } }
  }
  const result = operation?.result
  const inspection: ExcelInspection | null = operation?.status === 'succeeded' && result && 'inspectionId' in result ? result : null
  return { selection, inspection, operation, phase, busy, error, choose, submit, refresh }
}
