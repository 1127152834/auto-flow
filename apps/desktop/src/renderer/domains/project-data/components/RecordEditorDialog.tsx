import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { createRecordDraft, recordValues, RecordDraftError, type RecordDraft } from '../record-draft'
import type { ScalarDraftControl } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

type Field = components['schemas']['DataFieldView']
type RecordView = components['schemas']['DataRecordView']
type CellWrite = components['schemas']['DataCellWrite']
export type RecordEditorDialogProps = {
  open: boolean; mode: 'create' | 'edit'; sessionKey: string; fields: Field[]
  initialRecord?: RecordView; identityFieldId?: string; submissionEpoch?: string | number; saving?: boolean; recoveryPending?: boolean; readonly?: boolean; error?: string | null; errorActions?: ReactNode
  onOpenChange(open: boolean): void; onRequestClose?(): boolean | void | Promise<boolean | void>; onSubmit(values: CellWrite[]): Promise<unknown>; onRecover?(): Promise<unknown>; onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void
}

const equalDraft = (left: RecordDraft, right: RecordDraft) => JSON.stringify(left) === JSON.stringify(right)
type FormContext = { fields: Field[]; initialRecord?: RecordView; identityFieldId?: string }

export function RecordEditorDialog({ open, mode, sessionKey, fields, initialRecord, identityFieldId, submissionEpoch = 0, saving = false, recoveryPending = false, readonly = false, error, errorActions, onOpenChange, onRequestClose, onSubmit, onRecover, onDirtyChange, onSavingChange }: RecordEditorDialogProps) {
  const initial = () => createRecordDraft(fields, initialRecord)
  const [drafts, setDrafts] = useState<RecordDraft>(initial)
  const [context, setContext] = useState<FormContext>(() => ({ fields, initialRecord, identityFieldId }))
  const [fieldErrors, setFieldErrors] = useState<Record<string, { message: string; control: ScalarDraftControl }>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false), [recovering, setRecovering] = useState(false)
  const [confirmClose, setConfirmClose] = useState(false)
  const baseline = useRef(drafts), activeSession = useRef(sessionKey), activeSubmission = useRef(submissionEpoch), wasOpen = useRef(open), requestEpoch = useRef(0), openRef = useRef(open)
  const submitLock = useRef(false), recoverLock = useRef(false), closeLock = useRef(false)
  const externalGuard = useRef({ open, readonly, saving, recoveryPending })
  const lastInitial = useRef(initialRecord), lastFields = useRef(fields), dirtyCallback = useRef(onDirtyChange), savingCallback = useRef(onSavingChange)
  const fieldContainers = useRef(new Map<string, HTMLDivElement>())
  const hasChanges = mode === 'create' ? !equalDraft(drafts, baseline.current) : (() => {
    try { return recordValues(context.fields, drafts, context.initialRecord, context.identityFieldId).length > 0 } catch { return true }
  })()
  const busy = saving || submitting || recovering, frozen = busy || recoveryPending

  useLayoutEffect(() => {
    const startsSession = activeSession.current !== sessionKey || (open && !wasOpen.current)
    const closed = wasOpen.current && !open, reconnect = activeSubmission.current !== submissionEpoch
    activeSession.current = sessionKey; activeSubmission.current = submissionEpoch; wasOpen.current = open; openRef.current = open
    const refreshed = lastInitial.current !== initialRecord || lastFields.current !== fields
    lastInitial.current = initialRecord; lastFields.current = fields
    if (closed || reconnect) {
      requestEpoch.current += 1; submitLock.current = false; recoverLock.current = false; closeLock.current = false; setSubmitting(false); setRecovering(false); setConfirmClose(false); setFieldErrors({}); setSubmitError(null)
    }
    if (!startsSession && refreshed && open && !hasChanges) {
      const next = createRecordDraft(fields, initialRecord); baseline.current = next; setContext({ fields, initialRecord, identityFieldId }); setDrafts(next); setFieldErrors({}); return
    }
    if (!startsSession) return
    requestEpoch.current += 1
    submitLock.current = false; recoverLock.current = false; closeLock.current = false
    setSubmitting(false); setRecovering(false); setConfirmClose(false)
    if (open) {
      const next = createRecordDraft(fields, initialRecord); baseline.current = next; setDrafts(next)
      setContext({ fields, initialRecord, identityFieldId })
      setFieldErrors({}); setSubmitError(null)
    }
  }, [fields, hasChanges, identityFieldId, initialRecord, open, sessionKey, submissionEpoch])
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange; savingCallback.current = onSavingChange }, [onDirtyChange, onSavingChange])
  useLayoutEffect(() => { externalGuard.current = { open, readonly, saving, recoveryPending } }, [open, readonly, recoveryPending, saving])
  useEffect(() => { onDirtyChange?.(open && hasChanges) }, [hasChanges, onDirtyChange, open, sessionKey])
  useEffect(() => { onSavingChange?.(busy) }, [busy, onSavingChange])
  useEffect(() => () => { requestEpoch.current += 1; dirtyCallback.current?.(false); savingCallback.current?.(false) }, [])

  const requestClose = () => {
    if (busy || submitLock.current || recoverLock.current || closeLock.current) return
    if (onRequestClose) { const ticket=requestEpoch.current; closeLock.current=true; void Promise.resolve().then(onRequestClose).then(approved=>{const guard=externalGuard.current;if(approved===true&&ticket===requestEpoch.current&&guard.open&&!guard.saving&&!guard.recoveryPending&&!submitLock.current&&!recoverLock.current)onOpenChange(false)}).catch(()=>undefined).finally(()=>{if(ticket===requestEpoch.current)closeLock.current=false}); return }
    if (hasChanges || recoveryPending) { if (!recoveryPending) setConfirmClose(true); return }
    onOpenChange(false)
  }
  const focusField = (fieldId: string, control: ScalarDraftControl) => {
    const suffix = control === 'presence' ? '-presence' : control === 'offset' ? '-offset' : ''
    fieldContainers.current.get(fieldId)?.querySelector<HTMLElement>(`#record-${fieldId}${suffix}`)?.focus()
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (submitLock.current || busy || recoveryPending || readonly || (mode === 'edit' && !hasChanges)) return
    requestEpoch.current += 1; closeLock.current = false
    submitLock.current = true
    const ticket = requestEpoch.current; const target = context
    let values: CellWrite[]
    try {
      values = recordValues(target.fields, drafts, target.initialRecord, target.identityFieldId)
    } catch (caught) {
      if (caught instanceof RecordDraftError) {
        submitLock.current = false; setFieldErrors({ [caught.fieldId]: { message: caught.message, control: caught.control } }); focusField(caught.fieldId, caught.control); return
      }
      submitLock.current = false; setSubmitError(caught instanceof Error ? caught.message : '记录值无效'); return
    }
    if (mode === 'edit' && values.length === 0) { submitLock.current = false; return }
    savingCallback.current?.(true)
    setFieldErrors({}); setSubmitError(null); setSubmitting(true)
    const snapshot = values.map(value => ({ ...value }))
    void Promise.resolve().then(() => {
      const guard = externalGuard.current
      if (ticket !== requestEpoch.current || !openRef.current || !guard.open || guard.readonly || guard.saving || guard.recoveryPending) return
      return onSubmit(snapshot)
    }).catch(caught => {
      if (ticket === requestEpoch.current) setSubmitError(caught instanceof Error ? caught.message : '保存记录失败')
    }).finally(() => { if (ticket === requestEpoch.current) { submitLock.current = false; setSubmitting(false); savingCallback.current?.(externalGuard.current.saving) } })
  }
  const recover = () => { if (!onRecover || recoverLock.current || busy) return; requestEpoch.current+=1; closeLock.current=false; recoverLock.current=true; savingCallback.current?.(true); setRecovering(true); setSubmitError(null); const ticket=requestEpoch.current; void onRecover().catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'核对保存结果失败')}).finally(()=>{if(ticket===requestEpoch.current){recoverLock.current=false;setRecovering(false);savingCallback.current?.(externalGuard.current.saving)}}) }

  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="large" title={mode === 'create' ? '新建记录' : '编辑记录'} description="填写记录的业务字段值。" bodyClassName="grid gap-5" footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button>{recoveryPending?<Button type="button" variant="primary" disabled={busy||!onRecover} onClick={recover}>{recovering?'正在核对…':'核对保存结果'}</Button>:<Button type="submit" form="record-editor-form" variant="primary" disabled={busy || readonly || (mode === 'edit' && !hasChanges)}>{busy ? '正在保存…' : mode === 'create' ? '创建记录' : '保存修改'}</Button>}</>}>
      {context.initialRecord ? <p className="m-0 break-all rounded-control border border-line bg-surface px-3 py-2 text-sm text-muted">记录身份：{context.initialRecord.ref.recordKey.type} · {context.initialRecord.ref.recordKey.value}</p> : null}
      {error || submitError ? <div role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink"><p className="m-0">{submitError ?? error}</p>{errorActions?<div className="mt-3">{errorActions}</div>:null}</div> : null}
      {!context.fields.length ? <p className="text-sm text-muted">当前表没有业务字段，将创建一条系统身份记录。</p> : null}
      <form id="record-editor-form" className="grid min-w-0 gap-5" noValidate onSubmit={submit}>
        {context.fields.map(field => {
          const fieldId = field.ref.fieldId, cell = context.initialRecord?.values.find(value => value.fieldId === fieldId)
          const protectedReason = field.formula ? '公式字段由系统计算' : !field.writable ? '此字段只读' : cell?.readable === false ? '此值不可读取，因此不能编辑' : mode === 'edit' && fieldId === context.identityFieldId ? '记录身份字段不能在编辑时修改' : null
          return <div key={fieldId} ref={node => { if (node) fieldContainers.current.set(fieldId, node); else fieldContainers.current.delete(fieldId) }} className="grid min-w-0 gap-2">
            <ScalarValueEditor id={`record-${fieldId}`} label={field.name} type={field.type} draft={drafts[fieldId] ?? createRecordDraft([field])[fieldId]} allowMissing={!field.required}
              disabled={frozen} readOnly={readonly || Boolean(protectedReason)} error={fieldErrors[fieldId]?.message} errorTarget={fieldErrors[fieldId]?.control} onChange={draft => { setDrafts(current => ({ ...current, [fieldId]: draft })); setFieldErrors(current => { const next={...current}; delete next[fieldId]; return next }) }} />
            {protectedReason ? <p className="text-xs text-muted">{protectedReason}</p> : null}
          </div>
        })}
      </form>
    </Modal>
    <AlertDialog open={confirmClose} onOpenChange={next => { if (!frozen || next) setConfirmClose(next) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次记录修改不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={frozen}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={frozen} onClick={() => { if (frozen) return; setConfirmClose(false); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
