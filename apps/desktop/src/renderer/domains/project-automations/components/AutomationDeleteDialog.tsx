import { Archive, Trash, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { safeProjectError } from '../../projects/presentation-error'
import type { AutomationImpact } from '../types'

type Operation = components['schemas']['ProjectOperationView']

export type AutomationDeleteSubmit = {
  impactRevision: number
  expectedManagementRevision: number
  /** The frozen contract still carries the field; independent documents are only ever unlinked here. */
  workflowDisposition: 'unlink'
}

export type AutomationDeleteDialogProps = {
  open: boolean
  automation: { automationId: string; name: string; managementRevision: number } | null
  disabled?: boolean
  onOpenChange(open: boolean): void
  onLoadImpact(): Promise<AutomationImpact>
  onSubmit(values: AutomationDeleteSubmit): Promise<Operation>
  onFinished?(operation: Operation): void
}

const kept = (code: string) => code.endsWith('_KEPT')

export function AutomationDeleteDialog({ open, automation, disabled = false, onOpenChange, onLoadImpact, onSubmit, onFinished }: AutomationDeleteDialogProps) {
  const [impact, setImpact] = useState<AutomationImpact | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [name, setName] = useState('')
  const [operation, setOperation] = useState<Operation | null>(null)
  const submitLock = useRef(false)
  const session = useRef('')

  const load = async () => {
    setLoading(true)
    setError(null)
    setStale(false)
    try { setImpact(await onLoadImpact()) } catch (cause) { setError(safeProjectError(cause)) } finally { setLoading(false) }
  }

  useEffect(() => {
    const next = `${automation?.automationId ?? ''}:${open}`
    if (session.current === next) return
    session.current = next
    submitLock.current = false
    setImpact(null)
    setOperation(null)
    setStale(false)
    setName('')
    setError(null)
    if (open) void load()
  }, [automation?.automationId, open])

  const canSubmit = Boolean(impact) && Boolean(automation) && !busy && !loading && !disabled && !stale && name.trim() === automation?.name

  const submit = async () => {
    if (!impact || !automation || submitLock.current) return
    submitLock.current = true
    setBusy(true)
    setError(null)
    try {
      const saved = await onSubmit({ impactRevision: impact.impactRevision, expectedManagementRevision: automation.managementRevision, workflowDisposition: 'unlink' })
      setOperation(saved)
      onFinished?.(saved)
    } catch (cause) {
      if (cause instanceof ApiClientError && (cause.status === 412 || cause.code === 'REVISION_CONFLICT')) {
        setStale(true)
        setName('')
        setError('影响范围可能已变化，请重新核对后再确认。')
      } else setError(safeProjectError(cause))
    } finally {
      submitLock.current = false
      setBusy(false)
    }
  }

  const removed = (impact?.impacts ?? []).filter(item => !kept(item.code))
  const preserved = (impact?.impacts ?? []).filter(item => kept(item.code))

  return <Modal open={open} onOpenChange={onOpenChange} title="删除自动化" description={automation?.name} size="medium" closeDisabled={busy}>
    <div className="grid gap-4">
      <p role="alert" className="m-0 flex items-center gap-2 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm"><WarningCircle aria-hidden="true" className="shrink-0" />此操作无法撤销，请核对影响范围。</p>
      {loading ? <p role="status" className="m-0 text-sm text-muted">正在读取影响范围…</p> : null}
      {error ? <p role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm">{error}</p> : null}
      {stale ? <div className="grid gap-2"><p className="m-0 text-sm text-muted">删除影响待重新读取，重新核对后需再次输入名称。</p><Button variant="secondary" onClick={() => void load()}>重新核对影响</Button></div> : null}
      {impact ? <div className="grid gap-4">
        <section aria-label="将删除" className="grid gap-2 rounded-control border border-line p-4">
          <h3 className="m-0 flex items-center gap-2 text-base font-semibold text-ink"><Trash aria-hidden="true" className="text-danger" />将删除</h3>
          <ul className="m-0 grid list-none gap-1 p-0 text-sm">
            {removed.map(item => <li key={`${item.code}-${item.message}`} className="flex gap-2"><span aria-hidden="true">•</span><span>{item.message}</span></li>)}
          </ul>
        </section>
        <section aria-label="将保留" className="grid gap-2 rounded-control border border-line p-4">
          <h3 className="m-0 flex items-center gap-2 text-base font-semibold text-ink"><Archive aria-hidden="true" className="text-muted" />将保留</h3>
          <ul className="m-0 grid list-none gap-1 p-0 text-sm">
            {preserved.map(item => <li key={`${item.code}-${item.message}`} className="flex gap-2"><span aria-hidden="true">•</span><span>{item.message}</span></li>)}
          </ul>
        </section>
        <section aria-label="阻断项" className="grid gap-2">
          <h3 className="m-0 text-sm font-semibold text-ink">必须先处置</h3>
          {impact.blockers.length ? <ul className="m-0 grid list-none gap-1 p-0 text-sm">{impact.blockers.map(blocker => <li key={`${blocker.code}-${JSON.stringify(blocker.resource)}`} className="flex items-start gap-2 text-clay"><WarningCircle aria-hidden="true" className="mt-0.5 shrink-0" /><span>{blocker.message}（{blocker.state}）</span></li>)}</ul> : <p className="m-0 text-sm text-muted">没有阻断项。</p>}
        </section>
        <label className="grid gap-1 border-t border-line pt-4 text-sm"><span className="font-medium text-ink">输入自动化名称以确认</span><Input aria-label="确认自动化名称" disabled={busy || disabled || stale} placeholder={`请输入“${automation?.name ?? ''}”以确认删除该自动化。`} value={name} onChange={event => setName(event.target.value)} /></label>
        {operation ? <p role="status" className="m-0 text-sm text-muted">{operation.status === 'succeeded' ? '自动化已删除。' : '删除命令已接受，正在处理。'}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" disabled={busy} onClick={() => onOpenChange(false)}>取消</Button>
          <Button variant="danger" disabled={!canSubmit} onClick={() => void submit()}>{busy ? '提交中…' : '删除自动化'}</Button>
        </div>
      </div> : null}
    </div>
  </Modal>
}
