import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'

type Schema = components['schemas']
export type RecordStatusDialogProps = {
  presentation?: 'dialog' | 'inline'
  open: boolean; sessionKey: string; submissionEpoch: string | number
  record: Schema['DataRecordView']; statuses: Schema['DataStatusView'][]
  readonly: boolean; saving: boolean; recoveryPending: boolean; error: string | null; errorActions?: ReactNode
  onSubmit(statusId: string | null): Promise<unknown>; onRecover?(): Promise<unknown>
  onDirtyChange(dirty: boolean): void; onSavingChange(saving: boolean): void
  onRequestClose(): boolean | void | Promise<boolean | void>; onOpenChange(open: boolean): void
}

export function RecordStatusDialog(props: RecordStatusDialogProps) {
  const { presentation='dialog', open, sessionKey, submissionEpoch, record, statuses, readonly, saving, recoveryPending, error, errorActions } = props
  const [draft, setDraft] = useState({ selected: record.statusId, baseline: record.statusId }), [working, setWorking] = useState(false), [localError, setLocalError] = useState<string | null>(null)
  const selected = draft.selected
  const live = useRef(props), selection = useRef(selected), baseline = useRef(record.statusId)
  const mounted = useRef(false), epoch = useRef(0), actionLock = useRef(false), closeLock = useRef(false)
  useLayoutEffect(() => {
    const previous = live.current, starts = previous.sessionKey !== sessionKey || (open && !previous.open)
    if (starts || previous.open !== open || previous.submissionEpoch !== submissionEpoch) {
      epoch.current++; actionLock.current = false; closeLock.current = false
      setWorking(false); setLocalError(null); props.onSavingChange(false)
    }
    if (starts || (previous.record !== record && selection.current === baseline.current)) {
      baseline.current = record.statusId; selection.current = record.statusId; setDraft({ selected: record.statusId, baseline: record.statusId })
    }
    live.current = props
  }, [props, open, sessionKey, submissionEpoch, record])
  useEffect(() => { props.onDirtyChange(open && draft.selected !== draft.baseline) }, [props, open, draft])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++; live.current.onDirtyChange(false); live.current.onSavingChange(false) } }, [])
  const busy = saving || working
  const unavailable = draft.baseline !== null && !statuses.some(status => status.statusId === draft.baseline)
  const close = async () => {
    if (!live.current.open || live.current.saving || live.current.recoveryPending || actionLock.current || closeLock.current) return
    closeLock.current = true; const ticket = epoch.current
    try {
      const allow = await live.current.onRequestClose()
      if (allow !== false && mounted.current && ticket === epoch.current && live.current.open && !actionLock.current && !live.current.saving && !live.current.recoveryPending) live.current.onOpenChange(false)
    } catch (caught) { if (mounted.current && ticket === epoch.current) setLocalError(caught instanceof Error ? caught.message : '无法关闭，请重试') }
    finally { if (ticket === epoch.current) closeLock.current = false }
  }
  const run = async (recover: boolean) => {
    const current = live.current
    if (!current.open || current.saving || actionLock.current) return
    if (recover ? !current.recoveryPending || !current.onRecover : current.recoveryPending || current.readonly || (selection.current !== null && selection.current === baseline.current) || (baseline.current !== null && !current.statuses.some(status => status.statusId === baseline.current))) return
    if (!recover && selection.current !== null && !current.statuses.some(status => status.statusId === selection.current)) return
    const ticket = ++epoch.current
    closeLock.current = false; actionLock.current = true; setWorking(true); setLocalError(null); current.onSavingChange(true)
    try { await (recover ? current.onRecover!() : current.onSubmit(selection.current)) }
    catch (caught) { if (mounted.current && ticket === epoch.current) setLocalError(caught instanceof Error ? caught.message : '保存状态失败') }
    finally { if (mounted.current && ticket === epoch.current) { actionLock.current = false; setWorking(false); live.current.onSavingChange(false) } }
  }
  const reset=()=>{selection.current=baseline.current;setDraft({selected:baseline.current,baseline:baseline.current});setLocalError(null);live.current.onDirtyChange(false)}
  const content=<div className="grid gap-3">
      {error || localError ? <div role="alert"><p>{localError ?? error}</p>{errorActions}</div> : null}
      {unavailable ? <p role="alert">原状态已不可用，请载入最新资料。</p> : null}
      <Select className={presentation==='inline'?'h-12 text-base':undefined} aria-label="记录业务状态" value={selected ?? '__unset__'} clearable={false} readOnly={readonly} disabled={busy || recoveryPending || unavailable}
        options={[{ value: '__unset__', label: '未设置' }, ...statuses.map(status => ({ value: status.statusId, label: status.name }))]}
        onValueChange={value => { if (value === null || actionLock.current || live.current.saving || live.current.readonly || live.current.recoveryPending) return; const next = value === '__unset__' ? null : value; selection.current = next; setDraft({ selected: next, baseline: baseline.current }); live.current.onDirtyChange(next !== baseline.current) }} />
    </div>
  const save=recoveryPending?<Button type="button" variant={presentation==='inline'?'primary':undefined} className={presentation==='inline'?'h-12 w-full text-base':undefined} disabled={busy || !props.onRecover} onClick={() => void run(true)}>{working ? '正在核对…' : '核对保存结果'}</Button>
    :<Button type="button" variant="primary" className={presentation==='inline'?'h-12 w-full text-base':undefined} disabled={busy || readonly || unavailable || (selected !== null && selected === draft.baseline)} onClick={() => void run(false)}>{busy ? '正在保存…' : '保存状态'}</Button>
  if(presentation==='inline')return open?<div aria-label="业务状态编辑" className="grid gap-3">{content}<div className="grid gap-2">{save}<div className="flex flex-wrap justify-end gap-2"><Button type="button" size="sm" variant="ghost" disabled={busy||recoveryPending||readonly||unavailable} onClick={()=>{selection.current=null;setDraft({selected:null,baseline:baseline.current});live.current.onDirtyChange(null!==baseline.current);void run(false)}}>清空状态</Button><Button type="button" variant="ghost" disabled={busy||recoveryPending} className="justify-self-end" onClick={reset}>取消</Button></div></div></div>:null
  return <Modal open={open} onOpenChange={next => { if (!next) void close() }} closeDisabled={busy || recoveryPending} size="small" title="修改业务状态" description={`${record.ref.recordKey.type} · ${record.ref.recordKey.value}`}
    footer={<><Button type="button" variant="ghost" disabled={busy || recoveryPending} onClick={() => void close()}>取消</Button>{save}</>}>{content}</Modal>
}
