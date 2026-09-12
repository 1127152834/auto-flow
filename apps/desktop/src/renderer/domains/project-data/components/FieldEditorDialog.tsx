import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import type { components } from '../../../shared/api/generated'
import { FormField } from '../../../shared/components/FormField'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { fieldDefinition, fieldFormSchema, emptyFieldForm, type FieldFormValues } from '../field-form-schema'
import { parseScalarDraft, scalarDraft, type ScalarDraft } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

type Schema = components['schemas']
type Definition = Schema['DataFieldWrite']
type Impact = Schema['FieldImpactReport']
type Scalar = Schema['DataCellWrite']['value']
export type FieldSubmission = { definition: Definition; existingRecordDefault?: Scalar } | { definition: Definition; impactRevision: number }
export type FieldEditorDialogProps = {
  open: boolean; mode: 'create' | 'edit'; sessionKey: string; initialField?: Schema['DataFieldView']; isIdentityField?: boolean
  saving?: boolean; error?: string | null; readonly?: boolean
  onOpenChange(open: boolean): void; onPreview?(definition: Definition): Promise<Impact>; onSubmit(value: FieldSubmission): Promise<unknown>; onDirtyChange?(dirty: boolean): void
}

const fromField = (field?: Schema['DataFieldView']): FieldFormValues => field ? { key: field.key, name: field.name, type: field.type, required: field.required, minLength: String(field.validation.minLength ?? ''), maxLength: String(field.validation.maxLength ?? ''), pattern: String(field.validation.pattern ?? ''), minimum: String(field.validation.minimum ?? ''), maximum: String(field.validation.maximum ?? '') } : emptyFieldForm
const same = (a: unknown, b: FieldFormValues) => JSON.stringify(a) === JSON.stringify(b)

export function FieldEditorDialog({ open, mode, sessionKey, initialField, isIdentityField = false, saving = false, error, readonly = false, onOpenChange, onPreview, onSubmit, onDirtyChange }: FieldEditorDialogProps) {
  const initial = fromField(initialField)
  const form = useForm<FieldFormValues>({ resolver: zodResolver(fieldFormSchema), defaultValues: initial })
  const values = useWatch({ control: form.control })
  const [draft, setDraft] = useState<ScalarDraft>(() => scalarDraft(undefined))
  const [impact, setImpact] = useState<Impact | null>(null)
  const [busyLocal, setBusyLocal] = useState(false), [submitError, setSubmitError] = useState<string | null>(null), [confirmClose, setConfirmClose] = useState(false)
  const epoch = useRef(0), active = useRef(sessionKey), wasOpen = useRef(open), baseline = useRef(initial), dirtyCallback = useRef(onDirtyChange), running = useRef<number | null>(null)
  const changed = mode === 'create' ? form.formState.isDirty || draft.presence !== 'missing' : !same(values, baseline.current)
  const parsedValues = fieldFormSchema.safeParse(values)
  const currentDefinition = parsedValues.success ? fieldDefinition(parsedValues.data) as Definition : null
  const baselineValues = fieldFormSchema.safeParse(baseline.current)
  const baselineDefinition = baselineValues.success ? fieldDefinition(baselineValues.data) as Definition : null
  const actionChanged = mode === 'create' || currentDefinition === null ? changed : baselineDefinition !== null && JSON.stringify(currentDefinition) !== JSON.stringify(baselineDefinition)
  const protectedField = mode === 'edit' && Boolean(initialField?.formula || initialField?.writable === false)
  const busy = saving || busyLocal
  const blocked = Boolean(impact?.blockers.length)
  const submitGuard = useRef({ blocked, readonly, protectedField })
  useLayoutEffect(() => {
    const closed = !open && wasOpen.current
    const starts = active.current !== sessionKey || (open && !wasOpen.current); active.current = sessionKey; wasOpen.current = open
    if (closed) { epoch.current += 1; running.current = null; setConfirmClose(false); dirtyCallback.current?.(false) }
    if (!starts) return
    epoch.current += 1; running.current = null; baseline.current = fromField(initialField); form.reset(baseline.current); setDraft(scalarDraft(undefined)); setImpact(null); setBusyLocal(false); setSubmitError(null); setConfirmClose(false)
  }, [form, initialField, open, sessionKey])
  useEffect(() => {
    if (!open || active.current !== sessionKey || changed) return
    const refreshed = fromField(initialField)
    if (!same(refreshed, baseline.current)) {
      baseline.current = refreshed
      form.reset(refreshed)
      setImpact(null)
    }
  }, [changed, form, initialField, open, sessionKey])
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange }, [onDirtyChange])
  useLayoutEffect(() => { submitGuard.current = { blocked, readonly, protectedField } }, [blocked, protectedField, readonly])
  useEffect(() => { if (open) onDirtyChange?.(changed) }, [changed, onDirtyChange, open, sessionKey])
  useEffect(() => () => { epoch.current += 1; dirtyCallback.current?.(false) }, [])
  useEffect(() => { setImpact(null) }, [values])
  const requestClose = () => { if (busy) return; if (changed) setConfirmClose(true); else onOpenChange(false) }
  const run = (event: FormEvent) => {
    event.preventDefault(); if (busy || running.current !== null || readonly || protectedField || blocked || (mode === 'edit' && !actionChanged)) return
    const ticket = epoch.current
    running.current = ticket; setBusyLocal(true); setSubmitError(null)
    void form.handleSubmit(async raw => {
      if (ticket !== epoch.current || running.current !== ticket || submitGuard.current.blocked || submitGuard.current.readonly || submitGuard.current.protectedField) {
        if (running.current === ticket) { running.current = null; setBusyLocal(false) }
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
      } catch (caught) { if (ticket === epoch.current) setSubmitError(caught instanceof Error ? caught.message : '保存字段失败') }
      finally { if (running.current === ticket) running.current = null; if (ticket === epoch.current) setBusyLocal(false) }
    }, errors => {
      if (ticket !== epoch.current || running.current !== ticket) return
      running.current = null; setBusyLocal(false)
      form.setFocus(errors.name ? 'name' : errors.key ? 'key' : errors.type ? 'type' : errors.minLength ? 'minLength' : errors.maxLength ? 'maxLength' : errors.pattern ? 'pattern' : errors.minimum ? 'minimum' : 'maximum')
    })(event)
  }
  const type = (values.type ?? 'string') as Definition['type']
  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="small" title={mode === 'create' ? '新建字段' : '编辑字段'} description={protectedField ? '公式或只读字段不能编辑。' : isIdentityField ? '身份字段的类型不可修改。' : '设置字段定义和验证规则。'} footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button><Button type="submit" form="field-editor-form" variant="primary" disabled={busy || readonly || protectedField || blocked || (mode === 'edit' && !actionChanged)}>{busy ? '处理中…' : mode === 'edit' && !impact ? '预检影响' : mode === 'edit' ? '确认修改' : '创建字段'}</Button></>}>
      <form id="field-editor-form" className="grid gap-4" noValidate onSubmit={run}>
        {error || submitError ? <p role="alert">{submitError ?? error}</p> : null}
        <FormField label="字段名称" htmlFor="field-name" error={form.formState.errors.name?.message}><Input id="field-name" readOnly={busy || readonly || protectedField} {...form.register('name')} /></FormField>
        <FormField label="字段键" htmlFor="field-key" error={form.formState.errors.key?.message}><Input id="field-key" readOnly={busy || readonly || protectedField} {...form.register('key')} /></FormField>
        <FormField label="字段类型" htmlFor="field-type"><Select id="field-type" value={type} options={[{value:'string',label:'文本'},{value:'number',label:'数字'},{value:'boolean',label:'布尔'},{value:'date',label:'日期'}]} clearable={false} disabled={busy} readOnly={readonly || protectedField || isIdentityField} onValueChange={value => { if (value) { form.setValue('type', value as Definition['type'], { shouldDirty: true }); setDraft(scalarDraft(undefined)) } }} /></FormField>
        <label className="flex items-center gap-2"><Checkbox checked={Boolean(values.required)} disabled={busy || readonly || protectedField} onCheckedChange={checked => form.setValue('required', checked === true, { shouldDirty: true })} />必填</label>
        {type === 'string' ? <><FormField label="最小长度" htmlFor="field-min-length" error={form.formState.errors.minLength?.message}><Input id="field-min-length" readOnly={busy || readonly || protectedField} {...form.register('minLength')} /></FormField><FormField label="最大长度" htmlFor="field-max-length" error={form.formState.errors.maxLength?.message}><Input id="field-max-length" readOnly={busy || readonly || protectedField} {...form.register('maxLength')} /></FormField><FormField label="Python 正则表达式" htmlFor="field-pattern" error={form.formState.errors.pattern?.message}><Input id="field-pattern" readOnly={busy || readonly || protectedField} {...form.register('pattern')} /></FormField></> : null}
        {type === 'number' ? <><FormField label="最小值" htmlFor="field-minimum" error={form.formState.errors.minimum?.message}><Input id="field-minimum" readOnly={busy || readonly || protectedField} {...form.register('minimum')} /></FormField><FormField label="最大值" htmlFor="field-maximum" error={form.formState.errors.maximum?.message}><Input id="field-maximum" readOnly={busy || readonly || protectedField} {...form.register('maximum')} /></FormField></> : null}
        {mode === 'create' ? <><ScalarValueEditor id="field-default" label="现有记录默认值" type={type} draft={draft} onChange={setDraft} allowMissing disabled={busy} readOnly={readonly} /><p className="text-xs text-muted">非空表创建必填字段时需要默认值，最终由服务端校验。</p></> : null}
        {impact ? <section aria-label="字段影响预检"><p>{impact.impacts.map(item => item.message).join('；') || '没有记录受到影响'}</p>{impact.blockers.map(item => <p role="alert" key={item.code}>{item.message}</p>)}</section> : null}
      </form>
    </Modal>
    <AlertDialog open={open && confirmClose} onOpenChange={next => { if (!busy || next) setConfirmClose(next) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次字段修改将不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={busy}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={busy} onClick={() => { setConfirmClose(false); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
