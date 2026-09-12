import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
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
  saving?: boolean; error?: string | null; readonly?: boolean
  onOpenChange(open: boolean): void; onSubmit(values: StatusSubmission): Promise<unknown>; onDirtyChange?(dirty: boolean): void
}
const differs = (value: unknown, baseline: StatusFormValues) => {
  const current = statusFormSchema.safeParse(value); const initial = statusFormSchema.safeParse(baseline)
  if (current.success && initial.success) return (['name', 'color', 'order'] as const).some(key => current.data[key] !== initial.data[key])
  if (!value || typeof value !== 'object') return true
  const raw = value as Partial<StatusFormValues>
  return (['name', 'color', 'order'] as const).some(key => !Object.is(raw[key], baseline[key]))
}

export function StatusEditorDialog({ open, mode, sessionKey, initialValues, saving = false, error, readonly = false, onOpenChange, onSubmit, onDirtyChange }: StatusEditorDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const busy = saving || submitting
  const form = useForm<StatusFormValues>({ resolver: zodResolver(statusFormSchema), defaultValues: initialValues ?? emptyStatusForm })
  const currentValues = useWatch({ control: form.control })
  const requestEpoch = useRef(0); const activeSession = useRef(sessionKey); const wasOpen = useRef(open)
  const baseline = useRef<StatusFormValues>(initialValues ?? emptyStatusForm)
  const lastInitial = useRef(initialValues)
  const dirtyCallback = useRef(onDirtyChange)
  const hasChanges = mode === 'create' ? form.formState.isDirty : differs(currentValues, baseline.current)
  useLayoutEffect(() => {
    const startsSession = activeSession.current !== sessionKey || (open && !wasOpen.current)
    activeSession.current = sessionKey; wasOpen.current = open
    const refreshed = lastInitial.current !== initialValues
    lastInitial.current = initialValues
    if (!startsSession && refreshed && open && !differs(form.getValues(), baseline.current)) {
      baseline.current = initialValues ?? emptyStatusForm
      form.reset(baseline.current)
      return
    }
    if (!startsSession) return
    requestEpoch.current += 1
    if (open) { baseline.current = initialValues ?? emptyStatusForm; setSubmitting(false); setSubmitError(null); setConfirmClose(false); form.reset(baseline.current) }
  }, [form, initialValues, open, sessionKey])
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange }, [onDirtyChange])
  useEffect(() => () => { requestEpoch.current += 1 }, [])
  useEffect(() => { onDirtyChange?.(open && hasChanges) }, [hasChanges, onDirtyChange, open, sessionKey])
  useEffect(() => () => { dirtyCallback.current?.(false) }, [])
  const requestClose = () => { if (busy) return; if (form.formState.isDirty) setConfirmClose(true); else onOpenChange(false) }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy || readonly || (mode === 'edit' && !hasChanges)) return
    const ticket = requestEpoch.current; setSubmitting(true)
    void form.handleSubmit(async () => {
      if (ticket !== requestEpoch.current) return
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
      } finally { if (ticket === requestEpoch.current) setSubmitting(false) }
    }, errors => { if (ticket !== requestEpoch.current) return; setSubmitting(false); form.setFocus(errors.name ? 'name' : errors.color ? 'color' : 'order') })(event)
  }
  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="small" title={mode === 'create' ? '新建状态' : '编辑状态'} description="设置状态名称、颜色和显示顺序。" footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button><Button type="submit" form="status-editor-form" variant="primary" disabled={busy || readonly || (mode === 'edit' && !hasChanges)}>{busy ? '正在保存…' : mode === 'create' ? '创建状态' : '保存修改'}</Button></>}>
      <form id="status-editor-form" className="grid gap-5" noValidate onSubmit={submit}>
        {error || submitError ? <p role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink">{submitError ?? error}</p> : null}
        <FormField label="状态名称" htmlFor="status-name" error={form.formState.errors.name?.message} hint="1–120 个字符"><Input autoFocus readOnly={busy || readonly} {...form.register('name')} /></FormField>
        <FormField label="状态颜色" htmlFor="status-color" error={form.formState.errors.color?.message} hint="使用 #RRGGBB 格式"><Input readOnly={busy || readonly} {...form.register('color')} /></FormField>
        <div className="flex flex-wrap gap-2" aria-label="颜色预设">{presets.map(color => <Button key={color} type="button" variant="ghost" disabled={busy || readonly} aria-label={`选择颜色 ${color}`} onClick={() => form.setValue('color', color, { shouldDirty: true, shouldValidate: true })}><span className="h-4 w-4 rounded-full" style={{ backgroundColor: color }} />{color}</Button>)}</div>
        <FormField label="显示顺序" htmlFor="status-order" error={form.formState.errors.order?.message} hint="非负整数"><Input type="number" min={0} step={1} readOnly={busy || readonly} {...form.register('order', { valueAsNumber: true })} /></FormField>
      </form>
    </Modal>
    <AlertDialog open={confirmClose} onOpenChange={next => { if (!busy || next) setConfirmClose(next) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次对状态的修改将不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={busy}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={busy} onClick={() => { if (busy) return; setConfirmClose(false); form.reset(initialValues ?? emptyStatusForm); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
