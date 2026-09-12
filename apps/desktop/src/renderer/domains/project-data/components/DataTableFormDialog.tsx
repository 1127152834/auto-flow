import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { useForm } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'
import { dataTableFormSchema, emptyDataTableForm, type DataTableFormValues } from '../form-schema'

export type DataTableFormDialogProps = {
  open: boolean
  mode: 'create' | 'edit'
  sessionKey: string
  initialValues?: DataTableFormValues
  saving?: boolean
  error?: string | null
  readonly?: boolean
  onOpenChange(open: boolean): void
  onSubmit(values: DataTableFormValues): Promise<unknown>
}

export function DataTableFormDialog({ open, mode, sessionKey, initialValues, saving = false, error, readonly = false, onOpenChange, onSubmit }: DataTableFormDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const busy = saving || submitting
  const form = useForm<DataTableFormValues>({ resolver: zodResolver(dataTableFormSchema), defaultValues: initialValues ?? emptyDataTableForm })
  const requestEpoch = useRef(0)
  const activeSession = useRef(sessionKey)
  const wasOpen = useRef(open)
  useLayoutEffect(() => {
    const startsSession = activeSession.current !== sessionKey || (open && !wasOpen.current)
    activeSession.current = sessionKey
    wasOpen.current = open
    if (!startsSession) return
    requestEpoch.current += 1
    if (open) {
      setSubmitting(false)
      setSubmitError(null)
      setConfirmClose(false)
      form.reset(initialValues ?? emptyDataTableForm)
    }
  }, [form, initialValues, open, sessionKey])
  useEffect(() => {
    if (open && activeSession.current === sessionKey && !form.formState.isDirty) form.reset(initialValues ?? emptyDataTableForm)
  }, [form, initialValues, open])
  useEffect(() => () => { requestEpoch.current += 1 }, [])

  const requestClose = () => {
    if (busy) return
    if (form.formState.isDirty) setConfirmClose(true)
    else onOpenChange(false)
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy || readonly) return
    const ticket = requestEpoch.current
    setSubmitting(true)
    void form.handleSubmit(async values => {
      if (ticket !== requestEpoch.current) return
      setSubmitError(null)
      try {
        const parsed = dataTableFormSchema.parse(values)
        await onSubmit(parsed)
      } catch (caught) {
        if (ticket !== requestEpoch.current) return
        setSubmitError(caught instanceof Error ? caught.message : '保存数据表失败')
      } finally {
        if (ticket === requestEpoch.current) setSubmitting(false)
      }
    }, errors => {
      if (ticket !== requestEpoch.current) return
      setSubmitting(false)
      form.setFocus(errors.name ? 'name' : 'description')
    })(event)
  }

  return <>
    <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} closeDisabled={busy} variant="form" size="small" title={mode === 'create' ? '新建数据表' : '编辑数据表'} description="填写数据表名称和说明。" footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button><Button type="submit" form="data-table-form" variant="primary" disabled={busy || readonly}>{busy ? '正在保存…' : mode === 'create' ? '创建数据表' : '保存修改'}</Button></>}>
      <form id="data-table-form" className="grid gap-5" onSubmit={submit}>
        {error || submitError ? <p role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink">{submitError ?? error}</p> : null}
        <FormField label="数据表名称" htmlFor="data-table-name" error={form.formState.errors.name?.message} hint="1–120 个字符">
          <Input autoFocus readOnly={busy || readonly} {...form.register('name')} />
        </FormField>
        <FormField label="数据表描述" htmlFor="data-table-description" error={form.formState.errors.description?.message} hint="最多 1000 个字符">
          <Textarea rows={5} readOnly={busy || readonly} {...form.register('description')} />
        </FormField>
      </form>
    </Modal>
    <AlertDialog open={confirmClose} onOpenChange={next => { if (!busy || next) setConfirmClose(next) }}>
      <AlertDialogContent>
        <AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle>
        <AlertDialogDescription>关闭后，本次对数据表的修改将不会保存。</AlertDialogDescription>
        <div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={busy}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={busy} onClick={() => { if (busy) return; setConfirmClose(false); form.reset(initialValues ?? emptyDataTableForm); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction></div>
      </AlertDialogContent>
    </AlertDialog>
  </>
}
