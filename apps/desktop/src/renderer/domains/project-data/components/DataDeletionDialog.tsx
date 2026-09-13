import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'

export type DataDeletionDialogProps = {
  open: boolean; kind: 'record' | 'status'; targetName: string
  submissionEpoch?: string | number
  impact: components['schemas']['DeletionImpactReport'] | null
  saving: boolean; readonly: boolean; recoveryPending: boolean; error: string | null; errorActions?: ReactNode
  onPreview(): Promise<unknown>; onConfirm(): Promise<unknown>; onRecover(): Promise<unknown>
  onRequestClose(): boolean | void | Promise<boolean | void>; onOpenChange(open: boolean): void
}

/** The owner freezes the target and keys this component by its editing session. */
export function DataDeletionDialog(props: DataDeletionDialogProps) {
  const { open, kind, targetName, submissionEpoch, impact, saving, readonly, recoveryPending, error, errorActions } = props
  const [working, setWorking] = useState(false), [localError, setLocalError] = useState<string | null>(null)
  const live = useRef(props), mounted = useRef(false), actionLock = useRef(false), closeLock = useRef(false), epoch = useRef(0)
  useLayoutEffect(() => {
    if (live.current.open !== open || live.current.kind !== kind || live.current.targetName !== targetName || live.current.submissionEpoch !== submissionEpoch) {
      epoch.current++; actionLock.current = false; closeLock.current = false; setWorking(false); setLocalError(null)
    }
    live.current = props
  }, [props, open, kind, targetName, submissionEpoch])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++ } }, [])
  const busy = saving || working
  const close = async () => {
    if (actionLock.current || closeLock.current || live.current.saving || live.current.recoveryPending || !live.current.open) return
    closeLock.current = true
    const ticket = epoch.current
    try {
      const allowed = await live.current.onRequestClose()
      if (allowed !== false && mounted.current && ticket === epoch.current && live.current.open && !actionLock.current && !live.current.saving && !live.current.recoveryPending) live.current.onOpenChange(false)
    } catch (caught) {
      if (mounted.current && ticket === epoch.current) setLocalError(caught instanceof Error ? caught.message : '无法关闭，请重试')
    } finally { if (ticket === epoch.current) closeLock.current = false }
  }
  const run = async (mode: 'preview' | 'confirm' | 'recover') => {
    const current = live.current
    if (!current.open || current.saving || actionLock.current) return
    if (mode === 'recover' ? !current.recoveryPending : current.recoveryPending) return
    if (mode === 'confirm' && (current.readonly || !current.impact || current.impact.blockers.length)) return
    const ticket = ++epoch.current
    closeLock.current = false; actionLock.current = true; setWorking(true); setLocalError(null)
    try { await (mode === 'recover' ? current.onRecover() : mode === 'confirm' ? current.onConfirm() : current.onPreview()) }
    catch (caught) { if (mounted.current && ticket === epoch.current) setLocalError(caught instanceof Error ? caught.message : '无法完成操作，请重试') }
    finally { if (mounted.current && ticket === epoch.current) { actionLock.current = false; setWorking(false) } }
  }
  return <Modal open={open} onOpenChange={next => { if (!next) void close() }} closeDisabled={busy || recoveryPending} size="small"
    title={kind === 'record' ? '删除记录' : '删除状态'} description="先检查当前引用和影响，再确认删除。已提交的删除不能通过关闭弹窗撤回。"
    footer={<><Button type="button" autoFocus variant="ghost" disabled={busy || recoveryPending} onClick={() => void close()}>取消</Button>
      {recoveryPending ? <Button type="button" disabled={busy} onClick={() => void run('recover')}>{working ? '正在核对…' : '核对删除结果'}</Button>
        : <Button type="button" variant={impact ? 'danger' : 'primary'} disabled={busy || Boolean(impact && (readonly || impact.blockers.length))} onClick={() => void run(impact ? 'confirm' : 'preview')}>{busy ? '正在处理…' : impact ? '确认删除' : '检查删除影响'}</Button>}</>}>
    <div className="grid min-w-0 gap-3 text-sm"><p className="m-0 break-words font-semibold">{targetName}</p>
      {error || localError ? <div role="alert"><p>{localError ?? error}</p>{errorActions}</div> : null}
      {impact?.impacts.map((item, index) => <p className="m-0 break-words" key={`${item.code}:${index}`}>{item.message}</p>)}
      {impact?.blockers.map((blocker, index) => <p role="alert" className="m-0 break-words text-danger" key={`${blocker.code}:${index}`}>{blocker.message}（{blocker.code}）</p>)}
    </div>
  </Modal>
}
