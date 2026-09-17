import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { emptyFieldForm, fieldDefinition, fieldFormSchema, type FieldFormValues } from '../field-form-schema'
import { parseScalarDraft, scalarDraft, ScalarDraftError, type ScalarDraft, type ScalarDraftControl } from '../scalar-draft'
import { FieldEditorFields } from './FieldEditorFields'
import { safeProjectError } from '../../projects/presentation-error'

type Schema = components['schemas']
type Definition = Schema['DataFieldWrite']
type Scalar = Schema['DataCellWrite']['value']
export type SchemaFieldDraft = { definition: Definition; existingRecordDefault?: Scalar }
export type SchemaFieldDrawerProps = {
  open: boolean
  sessionKey: string
  submissionEpoch?: string | number
  initialField?: Schema['DataFieldView']
  initialDefinition?: Definition
  existingRecordDefault?: Scalar
  hasDefault?: boolean
  isIdentityField?: boolean
  readonly?: boolean
  onApply(value: SchemaFieldDraft): void
  onOpenChange(open: boolean): void
  onDirtyChange?(dirty: boolean): void
}

const valuesFrom = (field?: Schema['DataFieldView'], definition?: Definition): FieldFormValues => {
  const source = definition ?? field
  return source ? { key: source.key, name: source.name, type: source.type, required: source.required, minLength: String(source.validation.minLength ?? ''), maxLength: String(source.validation.maxLength ?? ''), pattern: String(source.validation.pattern ?? ''), minimum: String(source.validation.minimum ?? ''), maximum: String(source.validation.maximum ?? '') } : emptyFieldForm
}
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function SchemaFieldDrawer({ open, sessionKey, submissionEpoch = 0, initialField, initialDefinition, existingRecordDefault, hasDefault = false, isIdentityField = false, readonly = false, onApply, onOpenChange, onDirtyChange }: SchemaFieldDrawerProps) {
  const initialValues = valuesFrom(initialField, initialDefinition)
  const initialDefault = scalarDraft(hasDefault ? existingRecordDefault : undefined)
  const form = useForm<FieldFormValues>({ resolver: zodResolver(fieldFormSchema), defaultValues: initialValues })
  const values = useWatch({ control: form.control })
  const [defaultDraft, setDefaultDraft] = useState<ScalarDraft>(initialDefault)
  const [confirmClose, setConfirmClose] = useState(false)
  const [defaultError, setDefaultError] = useState<{ message: string; control: ScalarDraftControl }>()
  const [applyError, setApplyError] = useState<string | null>(null)
  const formElement = useRef<HTMLFormElement>(null)
  const requestEpoch = useRef(0), applying = useRef(false)
  const guard = useRef({ open, readonly, protectedField: false })
  const baselineValues = useRef(initialValues), baselineDefault = useRef(initialDefault), activeSession = useRef(sessionKey), activeEpoch = useRef(submissionEpoch), wasOpen = useRef(open), dirtyCallback = useRef(onDirtyChange)
  const create = !initialField
  const protectedField = Boolean(initialField && (initialField.formula || initialField.writable === false))
  const changed = !equal(values, baselineValues.current) || (create && !equal(defaultDraft, baselineDefault.current))

  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange }, [onDirtyChange])
  useLayoutEffect(() => { guard.current = { open, readonly, protectedField } }, [open, readonly, protectedField])
  useLayoutEffect(() => {
    if (!defaultError) return
    const suffix = defaultError.control === 'offset' ? '-offset' : defaultError.control === 'presence' ? '-presence' : ''
    formElement.current?.querySelector<HTMLElement>(`#field-default${suffix}`)?.focus()
  }, [defaultError])
  useLayoutEffect(() => {
    const starts = activeSession.current !== sessionKey || (open && !wasOpen.current)
    const reconnect = activeEpoch.current !== submissionEpoch
    const closed = !open && wasOpen.current
    activeSession.current = sessionKey; activeEpoch.current = submissionEpoch; wasOpen.current = open
    if (starts || closed || reconnect) { requestEpoch.current += 1; applying.current = false; setApplyError(null); setDefaultError(undefined) }
    if (closed || reconnect) setConfirmClose(false)
    if (closed) dirtyCallback.current?.(false)
    if (!starts) return
    const nextValues = valuesFrom(initialField, initialDefinition), nextDefault = scalarDraft(hasDefault ? existingRecordDefault : undefined)
    baselineValues.current = nextValues; baselineDefault.current = nextDefault
    form.reset(nextValues); setDefaultDraft(nextDefault); setConfirmClose(false)
  }, [existingRecordDefault, form, hasDefault, initialDefinition, initialField, open, sessionKey, submissionEpoch])
  useEffect(() => {
    if (!open || changed) return
    const nextValues = valuesFrom(initialField, initialDefinition), nextDefault = scalarDraft(hasDefault ? existingRecordDefault : undefined)
    if (!equal(nextValues, baselineValues.current) || !equal(nextDefault, baselineDefault.current)) {
      baselineValues.current = nextValues; baselineDefault.current = nextDefault; form.reset(nextValues); setDefaultDraft(nextDefault)
    }
  }, [changed, existingRecordDefault, form, hasDefault, initialDefinition, initialField, open])
  useEffect(() => { if (open) onDirtyChange?.(changed) }, [changed, onDirtyChange, open, sessionKey])
  useEffect(() => () => { requestEpoch.current += 1; dirtyCallback.current?.(false) }, [])

  const requestClose = () => { if (changed) setConfirmClose(true); else onOpenChange(false) }
  const apply = async (event: FormEvent) => {
    event.preventDefault()
    if (!open || readonly || protectedField || applying.current || !changed) return
    applying.current = true
    setApplyError(null); setDefaultError(undefined)
    const ticket = requestEpoch.current
    const current = () => ticket === requestEpoch.current && guard.current.open && !guard.current.readonly && !guard.current.protectedField
    try {
      await form.handleSubmit(raw => {
        if (!current()) return
        const definition = fieldDefinition(raw) as Definition
        if (initialField && definition.key !== initialField.key) { form.setError('key', { message: '已有字段的字段键不可修改。' }); form.setFocus('key'); return }
        if (initialField && isIdentityField && definition.type !== initialField.type) { form.setError('type', { message: '身份字段的类型不可修改。' }); formElement.current?.querySelector<HTMLElement>('#field-type')?.focus(); return }
        if (!create) { onApply({ definition }); return }
        const parsed = parseScalarDraft(definition.type, defaultDraft)
        onApply(parsed === undefined ? { definition } : { definition, existingRecordDefault: parsed })
      }, errors => {
        if (current()) form.setFocus(errors.name ? 'name' : errors.key ? 'key' : errors.type ? 'type' : errors.minLength ? 'minLength' : errors.maxLength ? 'maxLength' : errors.pattern ? 'pattern' : errors.minimum ? 'minimum' : 'maximum')
      })()
    } catch (reason) {
      if (!current()) return
      if (reason instanceof ScalarDraftError) setDefaultError({ message: reason.message, control: reason.control })
      else setApplyError(safeProjectError(reason))
    } finally { if (ticket === requestEpoch.current) applying.current = false }
  }
  const title = initialField ? '编辑字段' : '新增字段'
  const subtitle = initialField ? `${initialField.name} · ${initialField.key}` : '设置字段定义和现有记录默认值。'
  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} placement="drawer" className="w-[min(94vw,32rem)] [&>header]:border-b-0 [&>header_h2]:text-[28px] [&>header_p]:text-base" bodyClassName="bg-surface" variant="form" title={title} description={protectedField ? '公式或只读字段不能编辑。' : isIdentityField ? '身份字段的类型不可修改。' : subtitle} footer={<div className="flex w-full items-center justify-between gap-3"><p className="m-0 text-xs text-muted">修改仅应用到当前字段草稿。</p><div className="flex gap-2"><Button type="button" variant="secondary" className="h-12 px-5 text-base" onClick={requestClose}>取消</Button><Button type="submit" form="schema-field-drawer-form" variant="primary" className="h-12 px-5 text-base" disabled={readonly || protectedField || !changed}>应用到草稿</Button></div></div>}>
      <form ref={formElement} id="schema-field-drawer-form" className="grid gap-7 [&_label]:text-base [&_input[data-af-control]]:h-12 [&_input[data-af-control]]:text-base [&_button[data-af-control]]:h-12 [&_button[data-af-control]]:text-base" noValidate onSubmit={event => { void apply(event) }}>
        {applyError ? <p role="alert" className="text-sm text-danger">{applyError}</p> : null}
        <FieldEditorFields key={sessionKey} form={form} defaultDraft={defaultDraft} defaultError={defaultError} onDefaultDraftChange={draft => { setDefaultDraft(draft); setDefaultError(undefined) }} showDefault={create} readOnly={readonly} protectedField={protectedField} keyLocked={Boolean(initialField)} typeLocked={isIdentityField} presentation="drawer" />
      </form>
    </Modal>
    <AlertDialog open={open && confirmClose} onOpenChange={setConfirmClose}><AlertDialogContent><AlertDialogTitle>放弃未应用的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次字段草稿修改将丢失。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" onClick={() => { setConfirmClose(false); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
