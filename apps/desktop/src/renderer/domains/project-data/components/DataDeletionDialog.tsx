import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Trash, WarningCircle } from '@phosphor-icons/react'
import { safeProjectError } from '../../projects/presentation-error'

function deletionImpactLabel(item: components['schemas']['DeletionImpactReport']['impacts'][number], kind: 'record' | 'status') {
  if (kind === 'record' && item.code === 'RECORD_DELETE' && item.resource.type === 'record') return '影响范围：1 条本地记录'
  if (kind === 'status' && item.code === 'STATUS_DELETE') return '删除后将移除这个状态，请核对受影响的记录。'
  return '请核对本次变更的影响范围。'
}

export type DataDeletionDialogProps = {
  open: boolean; kind: 'record' | 'status'; targetName: string
  tableName?: string; sourceKind?: string
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
      if (mounted.current && ticket === epoch.current) setLocalError(safeProjectError(caught))
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
    catch (caught) { if (mounted.current && ticket === epoch.current) setLocalError(safeProjectError(caught)) }
    finally { if (mounted.current && ticket === epoch.current) { actionLock.current = false; setWorking(false) } }
  }
  return <Modal open={open} onOpenChange={next => { if (!next) void close() }} closeDisabled={busy || recoveryPending} size="small"
    bodyClassName={kind === 'record' ? 'pt-0' : undefined}
    className={kind === 'record' ? 'max-w-[30rem] [&>header]:border-0 [&>header]:pb-0 [&>footer]:border-0 [&>footer]:pt-0' : undefined}
    title={kind === 'record' ? <span className="flex items-center gap-5 text-2xl"><span aria-hidden className="grid size-16 shrink-0 place-items-center rounded-card border border-danger/10 bg-danger/5 text-danger"><Trash size={32} /></span>删除这条记录？</span> : '删除状态'} description={kind === 'record' ? undefined : '先检查当前引用和影响，再确认删除。已提交的删除不能通过关闭弹窗撤回。'}
    footer={<><Button type="button" autoFocus variant={kind === 'record' ? 'secondary' : 'ghost'} className={kind === 'record' ? 'h-12 min-w-32 text-base' : undefined} disabled={busy || recoveryPending} onClick={() => void close()}>取消</Button>
      {recoveryPending ? <Button type="button" disabled={busy} onClick={() => void run('recover')}>{working ? '正在核对…' : '核对删除结果'}</Button>
        : <Button type="button" className={kind === 'record' ? 'h-12 min-w-40 text-base' : undefined} variant={impact ? 'danger' : 'primary'} disabled={busy || Boolean(impact && (readonly || impact.blockers.length))} onClick={() => void run(impact ? 'confirm' : 'preview')}>{busy ? '正在处理…' : impact ? kind === 'record' ? '删除记录' : '确认删除' : '检查删除影响'}</Button>}</>}>
    <div className={`grid min-w-0 gap-4 ${kind === 'record' ? 'text-base' : 'text-sm'}`}>
      <p className="m-0 break-words">{kind === 'record' && props.tableName ? <span className="mb-1 block text-muted">你将删除「{props.tableName}」中的</span> : null}<strong>{targetName}</strong></p>
      {kind === 'record' ? <><ul className="m-0 grid list-disc gap-2 rounded-control border border-warning/20 bg-warning/5 py-4 pl-10 pr-4"><li>仅删除本地数据表中的这条记录</li>{props.sourceKind === 'excel' ? <li>不会修改原始 Excel 文件</li> : null}</ul><p className="m-0 flex items-start gap-2 text-sm text-warning"><WarningCircle size={24} weight="fill" className="shrink-0" />删除后无法在本页面撤销，请先确认是否需要保留副本。</p></> : null}
      {error || localError ? <div role="alert"><p>{localError ?? error}</p>{errorActions}</div> : null}
      {impact?.impacts.map((item, index) => <p className="m-0 break-words" key={`${item.code}:${index}`}>{deletionImpactLabel(item, kind)}</p>)}
      {impact?.blockers.map((blocker, index) => <p role="alert" className="m-0 break-words text-danger" key={`${blocker.code}:${index}`}>{safeProjectError(blocker)}</p>)}
    </div>
  </Modal>
}
