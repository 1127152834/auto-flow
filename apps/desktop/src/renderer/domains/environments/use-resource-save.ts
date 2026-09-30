import { useEffect, useRef, useState } from 'react'
import { isDefinitiveProjectFailure } from '../projects/api'
import { safeProjectError } from '../projects/presentation-error'

// Browser settings contain references only. Persist the exact command before sending
// so closing a tab or restarting the service cannot turn a retry into a second save.
export function useResourceSave<Body extends object, Result>({ storageKey, submit, onSaved }: {
  storageKey: string; submit(body: Body, key: string, resume: boolean): Promise<Result>; onSaved(result: Result): void
}) {
  type Pending = { key: string; body: Body }
  const [pending, setPending] = useState<Pending | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState<string>()
  const active = useRef(true), lock = useRef(false), brokenStorage = useRef(false)
  useEffect(() => {
    active.current = true
    try {
      const raw = localStorage.getItem(storageKey)
      if (raw) { const value = JSON.parse(raw) as Pending; if (!value.key || !value.body || typeof value.body !== 'object') throw new Error('保存恢复记录无效'); setPending(value) }
    } catch { brokenStorage.current = true; setError('无法读取保存恢复记录，请先恢复本地存储。') }
    return () => { active.current = false }
  }, [storageKey])
  async function save(body: Body) {
    if (lock.current || brokenStorage.current) return
    lock.current = true; setBusy(true); setError(undefined)
    const command = pending ?? { key: crypto.randomUUID(), body: structuredClone(body) }
    try {
      localStorage.setItem(storageKey, JSON.stringify(command)); setPending(command)
      const result = await submit(command.body, command.key, Boolean(pending))
      localStorage.removeItem(storageKey)
      if (active.current) { setPending(null); onSaved(result) }
    } catch (cause) {
      if (isDefinitiveProjectFailure(cause)) { localStorage.removeItem(storageKey); if (active.current) setPending(null) }
      if (active.current) setError(safeProjectError(cause))
    } finally { lock.current = false; if (active.current) setBusy(false) }
  }
  return { save, pending, busy, error }
}
