import { WarningCircle } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { ProjectLifecycleAction } from '../api'
import { cleanupResidue } from '../cleanup-residue'
import { safeProjectError } from '../presentation-error'
import type { ProjectLifecycleImpact, ProjectOperationView, ProjectView } from '../types'

export type LifecycleSubmit = { impactRevision: number; expectedManagementRevision: number; confirmationName: string }

export type ProjectLifecycleDialogProps = {
  open: boolean
  action: ProjectLifecycleAction
  project: ProjectView | null
  disabled?: boolean
  onOpenChange(open: boolean): void
  onLoadImpact(): Promise<ProjectLifecycleImpact>
  /** Residue the service already reported for this project, if any. */
  onLoadResidue?(): Promise<string[]>
  onSubmit(values: LifecycleSubmit): Promise<ProjectOperationView>
  onFinished?(operation: ProjectOperationView): void
}

const copy = {
  archive: { title: '归档项目', confirm: '归档项目', lead: '归档后项目变为只读，可随时恢复。' },
  delete: { title: '永久删除项目', confirm: '永久删除', lead: '此操作无法撤销，请核对影响范围。' },
  deleteRetry: { title: '重试清理', confirm: '重试清理', lead: '项目停留在“正在删除”，上次本地文件清理未完成。重试只处理残留文件，不重跑历史任务。' },
}

export function ProjectLifecycleDialog({ open, action, project, disabled = false, onOpenChange, onLoadImpact, onLoadResidue, onSubmit, onFinished }: ProjectLifecycleDialogProps) {
  const [impact, setImpact] = useState<ProjectLifecycleImpact | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [name_, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [operation, setOperation] = useState<ProjectOperationView | null>(null)
  const [reportedResidue, setReportedResidue] = useState<string[]>([])
  const submitLock = useRef(false)
  const session = useRef('')
  const retrying = action === 'delete' && project?.lifecycleState === 'deleting'
  const text = retrying ? copy.deleteRetry : copy[action]

  const load = async () => {
    setLoading(true)
    setError(null)
    setStale(false)
    try {
      const [nextImpact, nextResidue] = await Promise.all([
        onLoadImpact(),
        onLoadResidue ? onLoadResidue() : Promise.resolve<string[]>([]),
      ])
      setImpact(nextImpact)
      setReportedResidue(nextResidue)
    } catch (cause) {
      setError(safeProjectError(cause))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const next = `${project?.projectId ?? ''}:${action}:${open}`
    if (session.current === next) return
    session.current = next
    submitLock.current = false
    setImpact(null)
    setOperation(null)
    setReportedResidue([])
    setStale(false)
    setName('')
    setError(null)
    if (open) void load()
  }, [action, open, project?.projectId])

  const blocked = action === 'delete' && Boolean(impact?.blockers.length)
  const residue = operation ? cleanupResidue(operation) : reportedResidue
  const needsName = action === 'delete' && Boolean(project)
  const nameMatches = !needsName || name_.trim() === project?.name
  // Already-reported residue is the reason to retry, so it must not block the
  // command. Only a residue this session just produced forces a re-check.
  const settled = Boolean(operation) && residue.length > 0
  const canSubmit = Boolean(impact) && !busy && !loading && !disabled && !blocked && !stale && nameMatches && !settled

  const submit = async () => {
    if (!impact || !project || submitLock.current) return
    submitLock.current = true
    setBusy(true)
    setError(null)
    try {
      const saved = await onSubmit({ impactRevision: impact.impactRevision, expectedManagementRevision: project.managementRevision, confirmationName: name_.trim() })
      setOperation(saved)
      onFinished?.(saved)
    } catch (cause) {
      if (cause instanceof ApiClientError && (cause.status === 412 || cause.code === 'REVISION_CONFLICT' || cause.code === 'LIFECYCLE_CONFLICT')) {
        setStale(true)
        setName('')
        setError('影响范围可能已变化，请重新核对后再确认。')
      } else setError(safeProjectError(cause))
    } finally {
      submitLock.current = false
      setBusy(false)
    }
  }

  return <Modal open={open} onOpenChange={onOpenChange} title={text.title} description={text.lead} size="medium" closeDisabled={busy}>
    <div className="grid gap-4">
      <p className="m-0 text-sm text-muted">{text.lead}</p>
      {loading ? <p role="status" className="m-0 text-sm text-muted">正在读取影响范围…</p> : null}
      {error ? <p role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm">{error}</p> : null}
      {stale ? <div className="grid gap-2"><p className="m-0 text-sm text-muted">重新核对后需再次输入名称。</p><Button variant="secondary" onClick={() => void load()}>重新核对影响</Button></div> : null}
      {impact ? <div className="grid gap-4">
        {stale ? <p role="status" className="m-0 text-sm text-muted">删除影响待重新读取。</p> : null}
        <section aria-label="影响范围" className="grid gap-2">
          <h3 className="m-0 text-sm font-semibold text-ink">{action === 'delete' ? '将删除' : '归档影响'}</h3>
          <ul className="m-0 grid list-none gap-1 p-0 text-sm">
            {impact.impacts.map(item => <li key={`${item.code}-${item.message}`} className="flex gap-2"><span aria-hidden="true">•</span><span>{item.message}</span></li>)}
          </ul>
          {action === 'delete' ? <p className="m-0 text-sm text-muted">将保留：外部 Excel 原文件、远端 Sheets 与全局资源、其它项目的对象。</p> : null}
        </section>
        <section aria-label="阻断项" className="grid gap-2">
          <h3 className="m-0 text-sm font-semibold text-ink">{action === 'delete' ? '必须先处置' : '过程阻断'}</h3>
          {impact.blockers.length ? <ul className="m-0 grid list-none gap-1 p-0 text-sm">
            {impact.blockers.map(blocker => <li key={`${blocker.code}-${JSON.stringify(blocker.resource)}`} className="flex items-start gap-2 text-clay"><WarningCircle aria-hidden="true" className="mt-0.5 shrink-0" /><span>{blocker.message}（{blocker.state}）</span></li>)}
          </ul> : <p className="m-0 text-sm text-muted">{action === 'delete' ? '没有阻断项。' : '没有阻断项，将立即归档。'}</p>}
        </section>
        {impact.unsyncedCount > 0 ? <p className="m-0 text-sm text-muted">未推送变化 {impact.unsyncedCount} 条：{action === 'delete' ? '删除后不会补发。' : '归档后保留，不会自动推送。'}</p> : null}
        {needsName ? <label className="grid gap-1 text-sm"><span className="font-medium text-ink">输入项目名称以确认</span><Input aria-label="确认项目名称" disabled={busy || disabled} placeholder={`请输入“${project?.name ?? ''}”以确认删除该项目。`} value={name_} onChange={event => setName(event.target.value)} /></label> : null}
        {residue.length ? <section aria-label="清理残留" className="grid gap-1 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm"><h3 className="m-0 font-semibold text-ink">本地文件未能完全清理</h3><p className="m-0">{operation ? '项目停留在“正在删除”，可重新发起删除重试。' : '这是服务已经确认的残留清单，重试只处理这些文件。'}</p><ul className="m-0 grid list-none gap-1 p-0">{residue.map(item => <li key={item} className="break-all">{item}</li>)}</ul></section> : null}
        {operation && !residue.length ? <p role="status" className="m-0 text-sm text-muted">{operation.status === 'succeeded' ? (action === 'delete' ? '项目已删除。' : '归档命令已接受，正在收尾。') : '命令已接受，正在处理。'}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" disabled={busy} onClick={() => onOpenChange(false)}>取消</Button>
          <Button variant={action === 'delete' ? 'danger' : 'primary'} disabled={!canSubmit} onClick={() => void submit()}>{busy ? '提交中…' : text.confirm}</Button>
        </div>
      </div> : null}
    </div>
  </Modal>
}
