import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { components } from '../../../shared/api/generated'
import { emptyStatusForm, statusFormSchema, type StatusFormValues } from '../status-form-schema'

const presets = ['#a86f4c', '#486b52', '#536b8d', '#8a5d83', '#9a783f']
type GeneratedStatusCreate = components['schemas']['DataStatusCreate']
type GeneratedStatusPatch = components['schemas']['DataStatusPatch']
type GeneratedStatusView = components['schemas']['DataStatusView']
export type StatusSubmission = Omit<GeneratedStatusCreate, 'expectedTableRevision'> | Omit<GeneratedStatusPatch, 'expectedTableRevision' | 'expectedStatusRevision'>
export type StatusEditorDialogProps = {
  open: boolean; mode: 'create' | 'edit'; sessionKey: string; initialValues?: Pick<GeneratedStatusView, 'name' | 'color' | 'order'>
  submissionEpoch?: string | number; saving?: boolean; recoveryPending?: boolean; error?: string | null; errorActions?: ReactNode; readonly?: boolean
  onOpenChange(open: boolean): void; onRequestClose?(): boolean | void | Promise<boolean | void>; onSubmit(values: StatusSubmission): Promise<unknown>; onRecover?(): Promise<unknown>; onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void
}
const differs = (value: unknown, baseline: StatusFormValues) => {
  const current = statusFormSchema.safeParse(value); const initial = statusFormSchema.safeParse(baseline)
  if (current.success && initial.success) return (['name', 'color', 'order'] as const).some(key => current.data[key] !== initial.data[key])
  if (!value || typeof value !== 'object') return true
  const raw = value as Partial<StatusFormValues>
  return (['name', 'color', 'order'] as const).some(key => !Object.is(raw[key], baseline[key]))
}

export function StatusEditorDialog({ open, mode, sessionKey, initialValues, submissionEpoch = 0, saving = false, recoveryPending = false, error, errorActions, readonly = false, onOpenChange, onRequestClose, onSubmit, onRecover, onDirtyChange, onSavingChange }: StatusEditorDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [recovering,setRecovering]=useState(false), [submitError, setSubmitError] = useState<string | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const busy = saving || submitting || recovering, frozen=busy||recoveryPending
  const form = useForm<StatusFormValues>({ resolver: zodResolver(statusFormSchema), defaultValues: initialValues ?? emptyStatusForm })
  const currentValues = useWatch({ control: form.control })
  const requestEpoch = useRef(0), submitLock=useRef(false), recoverLock=useRef(false), closeLock=useRef(false); const activeSession = useRef(sessionKey), activeSubmission=useRef(submissionEpoch); const wasOpen = useRef(open)
  const baseline = useRef<StatusFormValues>(initialValues ?? emptyStatusForm)
  const lastInitial = useRef(initialValues)
  const dirtyCallback = useRef(onDirtyChange), savingCallback=useRef(onSavingChange), guard=useRef({open,readonly,saving,recoveryPending})
  const hasChanges = mode === 'create' ? form.formState.isDirty : differs(currentValues, baseline.current)
  useLayoutEffect(() => {
    const startsSession = activeSession.current !== sessionKey || (open && !wasOpen.current), closed=wasOpen.current&&!open, reconnect=activeSubmission.current!==submissionEpoch
    activeSession.current = sessionKey; activeSubmission.current=submissionEpoch; wasOpen.current = open
    const refreshed = lastInitial.current !== initialValues
    lastInitial.current = initialValues
    if(closed||reconnect){requestEpoch.current+=1;submitLock.current=false;recoverLock.current=false;closeLock.current=false;setSubmitting(false);setRecovering(false);setSubmitError(null);setConfirmClose(false)}
    if (!startsSession && refreshed && open && !differs(form.getValues(), baseline.current)) {
      baseline.current = initialValues ?? emptyStatusForm
      form.reset(baseline.current)
      return
    }
    if (!startsSession) return
    requestEpoch.current += 1
    submitLock.current=false;recoverLock.current=false;closeLock.current=false;setSubmitting(false);setRecovering(false);setConfirmClose(false)
    if (open) { baseline.current = initialValues ?? emptyStatusForm; setSubmitError(null); form.reset(baseline.current) }
  }, [form, initialValues, open, sessionKey, submissionEpoch])
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange; savingCallback.current=onSavingChange }, [onDirtyChange,onSavingChange])
  useLayoutEffect(()=>{guard.current={open,readonly,saving,recoveryPending}},[open,readonly,recoveryPending,saving])
  useEffect(() => { onDirtyChange?.(open && hasChanges) }, [hasChanges, onDirtyChange, open, sessionKey])
  useEffect(()=>{onSavingChange?.(busy)},[busy,onSavingChange])
  useEffect(() => () => { requestEpoch.current += 1; dirtyCallback.current?.(false); savingCallback.current?.(false) }, [])
  const requestClose=()=>{if(busy||submitLock.current||recoverLock.current||closeLock.current)return;if(onRequestClose){const ticket=requestEpoch.current;closeLock.current=true;void Promise.resolve().then(onRequestClose).then(approved=>{const current=guard.current;if(approved===true&&ticket===requestEpoch.current&&current.open&&!current.saving&&!current.recoveryPending&&!submitLock.current&&!recoverLock.current)onOpenChange(false)}).catch(()=>undefined).finally(()=>{if(ticket===requestEpoch.current)closeLock.current=false});return}if(form.formState.isDirty||recoveryPending){if(!recoveryPending)setConfirmClose(true);return}onOpenChange(false)}
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (submitLock.current || busy || recoveryPending || readonly || (mode === 'edit' && !hasChanges)) return
    requestEpoch.current+=1;closeLock.current=false
    submitLock.current=true; savingCallback.current?.(true); const ticket = requestEpoch.current; setSubmitting(true)
    void form.handleSubmit(async () => {
      const current=guard.current;if (ticket !== requestEpoch.current||!current.open||current.readonly||current.saving||current.recoveryPending) {if(ticket===requestEpoch.current){submitLock.current=false;setSubmitting(false);savingCallback.current?.(current.saving)}return}
      setSubmitError(null)
      try {
        const parsed = statusFormSchema.parse(form.getValues())
        const submission: StatusSubmission = mode === 'create' ? parsed : (() => {
          const initial = statusFormSchema.parse(baseline.current)
          return Object.fromEntries((['name', 'color', 'order'] as const).filter(key => parsed[key] !== initial[key]).map(key => [key, parsed[key]]))
        })()
        await onSubmit(submission)
      } catch (caught) {
        if (ticket !== requestEpoch.current) return
        setSubmitError(caught instanceof Error ? caught.message : '保存状态失败')
      } finally { if (ticket === requestEpoch.current) {submitLock.current=false;setSubmitting(false);savingCallback.current?.(guard.current.saving)} }
    }, errors => { if (ticket !== requestEpoch.current) return; submitLock.current=false;setSubmitting(false);savingCallback.current?.(guard.current.saving);form.setFocus(errors.name ? 'name' : errors.color ? 'color' : 'order') })(event)
  }
  const recover=()=>{if(!onRecover||recoverLock.current||busy)return;requestEpoch.current+=1;closeLock.current=false;recoverLock.current=true;savingCallback.current?.(true);setRecovering(true);setSubmitError(null);const ticket=requestEpoch.current;void onRecover().catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'核对保存结果失败')}).finally(()=>{if(ticket===requestEpoch.current){recoverLock.current=false;setRecovering(false);savingCallback.current?.(guard.current.saving)}})}
  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="small" title={mode === 'create' ? '新建状态' : '编辑状态'} description="设置状态名称、颜色和显示顺序。" footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button>{recoveryPending?<Button type="button" variant="primary" disabled={busy||!onRecover} onClick={recover}>{recovering?'正在核对…':'核对保存结果'}</Button>:<Button type="submit" form="status-editor-form" variant="primary" disabled={busy || readonly || (mode === 'edit' && !hasChanges)}>{busy ? '正在保存…' : mode === 'create' ? '创建状态' : '保存修改'}</Button>}</>}>
      <form id="status-editor-form" className="grid gap-5" noValidate onSubmit={submit}>
        {error || submitError ? <div role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink"><p className="m-0">{submitError ?? error}</p>{errorActions?<div className="mt-3">{errorActions}</div>:null}</div> : null}
        <FormField label="状态名称" htmlFor="status-name" error={form.formState.errors.name?.message} hint="1–120 个字符"><Input autoFocus readOnly={frozen || readonly} {...form.register('name')} /></FormField>
        <FormField label="状态颜色" htmlFor="status-color" error={form.formState.errors.color?.message} hint="使用 #RRGGBB 格式"><Input readOnly={frozen || readonly} {...form.register('color')} /></FormField>
        <div className="flex flex-wrap gap-2" aria-label="颜色预设">{presets.map(color => <Button key={color} type="button" variant="ghost" disabled={frozen || readonly} aria-label={`选择颜色 ${color}`} onClick={() => form.setValue('color', color, { shouldDirty: true, shouldValidate: true })}><span className="h-4 w-4 rounded-full" style={{ backgroundColor: color }} />{color}</Button>)}</div>
        <FormField label="显示顺序" htmlFor="status-order" error={form.formState.errors.order?.message} hint="非负整数"><Input type="number" min={0} step={1} readOnly={frozen || readonly} {...form.register('order', { valueAsNumber: true })} /></FormField>
      </form>
    </Modal>
    <AlertDialog open={confirmClose} onOpenChange={next => { if (!frozen || next) setConfirmClose(next) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次对状态的修改将不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={frozen}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={frozen} onClick={() => { if (frozen) return; setConfirmClose(false); form.reset(initialValues ?? emptyStatusForm); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
