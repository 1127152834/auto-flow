import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { fieldDefinition, fieldFormSchema, emptyFieldForm, type FieldFormValues } from '../field-form-schema'
import { parseScalarDraft, scalarDraft, type ScalarDraft } from '../scalar-draft'
import { FieldEditorFields } from './FieldEditorFields'
import { safeProjectError } from '../../projects/presentation-error'

type Schema = components['schemas']
type Definition = Schema['DataFieldWrite']
type Impact = Schema['FieldImpactReport']
type Scalar = Schema['DataCellWrite']['value']
const impactLabel = (item: { code: string }) => item.code === 'FIELD_RECORD_VALIDATION'
  ? '将检查现有记录是否符合新的字段规则'
  : '字段变更将影响现有数据，请核对后继续'
export type FieldSubmission = { definition: Definition; existingRecordDefault?: Scalar } | { definition: Definition; impactRevision: number }
export type FieldEditorDialogProps = {
  open: boolean; mode: 'create' | 'edit'; sessionKey: string; initialField?: Schema['DataFieldView']; isIdentityField?: boolean
  submissionEpoch?: string | number; saving?: boolean; recoveryPending?: boolean; error?: string | null; errorActions?: ReactNode; readonly?: boolean
  onOpenChange(open: boolean): void; onRequestClose?(): boolean | void | Promise<boolean | void>; onPreview?(definition: Definition): Promise<Impact>; onSubmit(value: FieldSubmission): Promise<unknown>; onRecover?(): Promise<unknown>; onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void
}

const fromField = (field?: Schema['DataFieldView']): FieldFormValues => field ? { key: field.key, name: field.name, type: field.type, required: field.required, minLength: String(field.validation.minLength ?? ''), maxLength: String(field.validation.maxLength ?? ''), pattern: String(field.validation.pattern ?? ''), minimum: String(field.validation.minimum ?? ''), maximum: String(field.validation.maximum ?? '') } : emptyFieldForm
const same = (a: unknown, b: FieldFormValues) => JSON.stringify(a) === JSON.stringify(b)

export function FieldEditorDialog({ open, mode, sessionKey, initialField, isIdentityField = false, submissionEpoch = 0, saving = false, recoveryPending = false, error, errorActions, readonly = false, onOpenChange, onRequestClose, onPreview, onSubmit, onRecover, onDirtyChange, onSavingChange }: FieldEditorDialogProps) {
  const initial = fromField(initialField)
  const form = useForm<FieldFormValues>({ resolver: zodResolver(fieldFormSchema), defaultValues: initial })
  const values = useWatch({ control: form.control })
  const [draft, setDraft] = useState<ScalarDraft>(() => scalarDraft(undefined))
  const [impact, setImpact] = useState<Impact | null>(null)
  const [busyLocal, setBusyLocal] = useState(false), [recovering,setRecovering]=useState(false), [submitError, setSubmitError] = useState<string | null>(null), [confirmClose, setConfirmClose] = useState(false)
  const epoch = useRef(0), active = useRef(sessionKey), activeSubmission=useRef(submissionEpoch), wasOpen = useRef(open), baseline = useRef(initial), dirtyCallback = useRef(onDirtyChange), savingCallback=useRef(onSavingChange), running = useRef<number | null>(null), recoverLock=useRef(false), closeLock=useRef(false)
  const changed = mode === 'create' ? form.formState.isDirty || draft.presence !== 'missing' : !same(values, baseline.current)
  const parsedValues = fieldFormSchema.safeParse(values)
  const currentDefinition = parsedValues.success ? fieldDefinition(parsedValues.data) as Definition : null
  const baselineValues = fieldFormSchema.safeParse(baseline.current)
  const baselineDefinition = baselineValues.success ? fieldDefinition(baselineValues.data) as Definition : null
  const actionChanged = mode === 'create' || currentDefinition === null ? changed : baselineDefinition !== null && JSON.stringify(currentDefinition) !== JSON.stringify(baselineDefinition)
  const protectedField = mode === 'edit' && Boolean(initialField?.formula || initialField?.writable === false)
  const busy = saving || busyLocal || recovering, frozen=busy||recoveryPending
  const blocked = Boolean(impact?.blockers.length)
  const submitGuard = useRef({ blocked, readonly, protectedField, open, saving, recoveryPending })
  useLayoutEffect(() => {
    const closed = !open && wasOpen.current, reconnect=activeSubmission.current!==submissionEpoch
    const starts = active.current !== sessionKey || (open && !wasOpen.current); active.current = sessionKey; wasOpen.current = open
    activeSubmission.current=submissionEpoch
    if (closed||reconnect) { epoch.current += 1; running.current = null; recoverLock.current=false; closeLock.current=false; setBusyLocal(false); setRecovering(false); setImpact(null); setSubmitError(null); setConfirmClose(false); if(closed)dirtyCallback.current?.(false) }
    if (!starts) return
    epoch.current += 1; running.current = null; recoverLock.current=false; closeLock.current=false; baseline.current = fromField(initialField); form.reset(baseline.current); setDraft(scalarDraft(undefined)); setImpact(null); setBusyLocal(false); setRecovering(false); setSubmitError(null); setConfirmClose(false)
  }, [form, initialField, open, sessionKey, submissionEpoch])
  useEffect(() => {
    if (!open || active.current !== sessionKey || changed) return
    const refreshed = fromField(initialField)
    if (!same(refreshed, baseline.current)) {
      baseline.current = refreshed
      form.reset(refreshed)
      setImpact(null)
    }
  }, [changed, form, initialField, open, sessionKey])
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange; savingCallback.current=onSavingChange }, [onDirtyChange,onSavingChange])
  useLayoutEffect(() => { submitGuard.current = { blocked, readonly, protectedField, open, saving, recoveryPending } }, [blocked,open, protectedField,recoveryPending, readonly,saving])
  useEffect(() => { if (open) onDirtyChange?.(changed) }, [changed, onDirtyChange, open, sessionKey])
  useEffect(()=>{onSavingChange?.(busy)},[busy,onSavingChange])
  useEffect(() => () => { epoch.current += 1; dirtyCallback.current?.(false); savingCallback.current?.(false) }, [])
  useEffect(() => { setImpact(null) }, [values])
  const requestClose=()=>{if(busy||running.current!==null||recoverLock.current||closeLock.current)return;if(onRequestClose){const ticket=epoch.current;closeLock.current=true;void Promise.resolve().then(onRequestClose).then(approved=>{const guard=submitGuard.current;if(approved===true&&ticket===epoch.current&&guard.open&&!guard.saving&&!guard.recoveryPending&&running.current===null&&!recoverLock.current)onOpenChange(false)}).catch(()=>undefined).finally(()=>{if(ticket===epoch.current)closeLock.current=false});return}if(changed||recoveryPending){if(!recoveryPending)setConfirmClose(true);return}onOpenChange(false)}
  const run = (event: FormEvent) => {
    event.preventDefault(); if (busy || recoveryPending || running.current !== null || readonly || protectedField || blocked || (mode === 'edit' && !actionChanged)) return
    epoch.current += 1; closeLock.current=false
    const ticket = epoch.current
    running.current = ticket; savingCallback.current?.(true); setBusyLocal(true); setSubmitError(null)
    void form.handleSubmit(async raw => {
      if (ticket !== epoch.current || running.current !== ticket || !submitGuard.current.open || submitGuard.current.saving || submitGuard.current.recoveryPending || submitGuard.current.blocked || submitGuard.current.readonly || submitGuard.current.protectedField) {
        if (running.current === ticket) { running.current = null; setBusyLocal(false); savingCallback.current?.(submitGuard.current.saving) }
        return
      }
      const definition = fieldDefinition(raw) as Definition
      try {
        if (mode === 'edit' && !impact) {
          if (!onPreview) throw new Error('无法预检字段修改')
          const report = await onPreview(definition)
          if (ticket === epoch.current) setImpact(report)
        } else if (mode === 'edit' && impact) {
          await onSubmit({ definition, impactRevision: impact.impactRevision })
        } else {
          const parsed = parseScalarDraft(definition.type, draft)
          await onSubmit(parsed === undefined ? { definition } : { definition, existingRecordDefault: parsed })
        }
      } catch (caught) { if (ticket === epoch.current) setSubmitError(safeProjectError(caught)) }
      finally { if (running.current === ticket) running.current = null; if (ticket === epoch.current) {setBusyLocal(false);savingCallback.current?.(submitGuard.current.saving)} }
    }, errors => {
      if (ticket !== epoch.current || running.current !== ticket) return
      running.current = null; setBusyLocal(false); savingCallback.current?.(submitGuard.current.saving)
      form.setFocus(errors.name ? 'name' : errors.key ? 'key' : errors.type ? 'type' : errors.minLength ? 'minLength' : errors.maxLength ? 'maxLength' : errors.pattern ? 'pattern' : errors.minimum ? 'minimum' : 'maximum')
    })(event)
  }
  const recover=()=>{if(!onRecover||recoverLock.current||busy)return;epoch.current+=1;closeLock.current=false;recoverLock.current=true;savingCallback.current?.(true);setRecovering(true);setSubmitError(null);const ticket=epoch.current;void onRecover().catch(caught=>{if(ticket===epoch.current)setSubmitError(safeProjectError(caught))}).finally(()=>{if(ticket===epoch.current){recoverLock.current=false;setRecovering(false);savingCallback.current?.(submitGuard.current.saving)}})}
  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="small" title={mode === 'create' ? '新建字段' : '编辑字段'} description={protectedField ? '公式或只读字段不能编辑。' : isIdentityField ? '身份字段的类型不可修改。' : '设置字段定义和验证规则。'} footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button>{recoveryPending?<Button type="button" variant="primary" disabled={busy||!onRecover} onClick={recover}>{recovering?'正在核对…':'核对保存结果'}</Button>:<Button type="submit" form="field-editor-form" variant="primary" disabled={busy || readonly || protectedField || blocked || (mode === 'edit' && !actionChanged)}>{busy ? '处理中…' : mode === 'edit' && !impact ? '预检影响' : mode === 'edit' ? '确认修改' : '创建字段'}</Button>}</>}>
      <form id="field-editor-form" className="grid gap-4" noValidate onSubmit={run}>
        {error || submitError ? <div role="alert"><p>{submitError ?? error}</p>{errorActions?<div>{errorActions}</div>:null}</div> : null}
        <FieldEditorFields form={form} defaultDraft={draft} onDefaultDraftChange={setDraft} showDefault={mode === 'create'} disabled={frozen} readOnly={readonly} protectedField={protectedField} typeLocked={isIdentityField} />
        {impact ? <section aria-label="字段影响预检"><p>{impact.impacts.map(impactLabel).join('；') || '没有记录受到影响'}</p>{impact.blockers.map(item => <p role="alert" key={item.code}>{safeProjectError(item)}</p>)}</section> : null}
      </form>
    </Modal>
    <AlertDialog open={open && confirmClose} onOpenChange={next => { if (!frozen || next) setConfirmClose(next) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次字段修改将不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={frozen}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={frozen} onClick={() => { if(frozen)return;setConfirmClose(false); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
