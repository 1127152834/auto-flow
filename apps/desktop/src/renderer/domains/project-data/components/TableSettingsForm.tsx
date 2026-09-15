import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'
import { dataTableFormSchema } from '../form-schema'
import { safeProjectError } from '../../projects/presentation-error'

type TablePatch = components['schemas']['DataTablePatch']
export type TableSettingsValues = { name: NonNullable<TablePatch['name']>; description: NonNullable<TablePatch['description']> }
export type TableSettingsFormProps = {
  sessionKey: string
  initialValues: TableSettingsValues
  submissionEpoch?: string | number
  readonly?: boolean
  saving?: boolean
  recoveryPending?: boolean
  error?: string | null
  errorActions?: ReactNode
  onSubmit(values: TableSettingsValues): Promise<unknown>
  onCancel(): void
  onRecover?(): Promise<unknown>
  onDirtyChange?(dirty: boolean): void
  onSavingChange?(saving: boolean): void
}

export function TableSettingsForm({ sessionKey, initialValues, submissionEpoch = 0, readonly = false, saving = false, recoveryPending = false, error, errorActions, onSubmit, onCancel, onRecover, onDirtyChange, onSavingChange }: TableSettingsFormProps) {
  const id = useId()
  const form = useForm<TableSettingsValues>({ resolver: zodResolver(dataTableFormSchema), defaultValues: initialValues })
  const { isDirty, errors } = form.formState
  const [working, setWorking] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const epoch = useRef(0)
  const lock = useRef(false)
  const active = useRef({ sessionKey, submissionEpoch })
  const guard = useRef({ readonly, saving, recoveryPending })
  const callbacks = useRef({ onDirtyChange, onSavingChange })
  const busy = saving || working
  const frozen = busy || recoveryPending

  useLayoutEffect(() => {
    guard.current = { readonly, saving, recoveryPending }
    callbacks.current = { onDirtyChange, onSavingChange }
  }, [readonly, saving, recoveryPending, onDirtyChange, onSavingChange])
  useLayoutEffect(() => {
    const sessionChanged = active.current.sessionKey !== sessionKey
    const reconnected = active.current.submissionEpoch !== submissionEpoch
    active.current = { sessionKey, submissionEpoch }
    if (sessionChanged || reconnected) {
      epoch.current += 1
      lock.current = false
      setWorking(false)
      setLocalError(null)
    }
    // The stable session owns the draft; a new backend instance only invalidates old requests.
    if (sessionChanged) form.reset(initialValues)
    else if (!form.formState.isDirty && !lock.current && !saving && !recoveryPending) form.reset(initialValues)
  }, [form, initialValues, sessionKey, submissionEpoch, saving, recoveryPending])
  useEffect(() => { onDirtyChange?.(isDirty) }, [isDirty, onDirtyChange, sessionKey])
  useEffect(() => { onSavingChange?.(busy) }, [busy, onSavingChange])
  useEffect(() => () => {
    epoch.current += 1
    callbacks.current.onDirtyChange?.(false)
    callbacks.current.onSavingChange?.(false)
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (lock.current || busy || recoveryPending || readonly || !isDirty) return
    lock.current = true
    setWorking(true)
    callbacks.current.onSavingChange?.(true)
    setLocalError(null)
    const ticket = epoch.current
    try {
      await form.handleSubmit(async values => {
        if (ticket !== epoch.current || guard.current.readonly || guard.current.saving || guard.current.recoveryPending) return
        // The parent confirms the command and starts a fresh session; resolution alone is not proof of a saved operation.
        await onSubmit(dataTableFormSchema.parse(values))
      }, fieldErrors => {
        if (ticket === epoch.current) form.setFocus(fieldErrors.name ? 'name' : 'description')
      })()
    } catch (reason) {
      if (ticket === epoch.current) setLocalError(safeProjectError(reason))
    } finally {
      if (ticket === epoch.current) {
        lock.current = false
        setWorking(false)
        callbacks.current.onSavingChange?.(guard.current.saving)
      }
    }
  }

  const recover = async () => {
    if (!onRecover || !recoveryPending || lock.current || busy) return
    lock.current = true
    setWorking(true)
    callbacks.current.onSavingChange?.(true)
    setLocalError(null)
    const ticket = epoch.current
    try { await onRecover() }
    catch (reason) {
      if (ticket === epoch.current) setLocalError(safeProjectError(reason))
    } finally {
      if (ticket === epoch.current) {
        lock.current = false
        setWorking(false)
        callbacks.current.onSavingChange?.(guard.current.saving)
      }
    }
  }

  return <form aria-labelledby={`${id}-title`} noValidate onSubmit={event => { void submit(event) }} className="grid gap-5 rounded-control border border-line bg-surface p-5">
    <header>
      <h3 id={`${id}-title`} className="text-xl font-semibold">基本信息</h3>
      <p className="mt-1 text-base text-muted">修改名称与用途说明，不会改动记录内容。</p>
    </header>
    {localError || error ? <div role="alert" className="text-sm text-danger">{localError || error}{errorActions}</div> : null}
    <div className="grid items-start gap-3 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <label htmlFor={`${id}-name`} className="pt-3 text-base font-medium">数据表名称 <span aria-hidden="true" className="ml-3 text-danger">*</span></label>
      <div className="min-w-0">
        <Input aria-label="数据表名称" id={`${id}-name`} className="h-12 text-base" readOnly={frozen || readonly} aria-required="true" aria-invalid={!!errors.name} aria-describedby={errors.name ? `${id}-name-error` : undefined} {...form.register('name')} />
        {errors.name ? <p id={`${id}-name-error`} role="alert" className="mt-1 text-sm text-danger">{errors.name.message}</p> : null}
      </div>
      <label htmlFor={`${id}-description`} className="pt-3 text-base font-medium">用途说明</label>
      <div className="min-w-0">
        <Textarea id={`${id}-description`} rows={3} className="min-h-24 text-base" readOnly={frozen || readonly} aria-invalid={!!errors.description} aria-describedby={`${id}-description-${errors.description ? 'error' : 'hint'}`} {...form.register('description')} />
        {errors.description ? <p id={`${id}-description-error`} role="alert" className="mt-1 text-sm text-danger">{errors.description.message}</p> : <p id={`${id}-description-hint`} className="mt-1 text-right text-sm text-muted">最多 1000 个字符</p>}
      </div>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted" aria-live="polite">{recoveryPending ? '保存结果尚未确认，请先查询保存结果。' : isDirty ? <span className="text-clay"><span aria-hidden="true" className="mr-2">●</span>有未保存的修改</span> : readonly ? '当前数据表为只读。' : '没有未保存的修改'}</p>
      <div className="flex flex-wrap gap-4">
        {recoveryPending && onRecover ? <Button disabled={busy} onClick={() => { void recover() }}>查询保存结果</Button> : null}
        <Button className="h-12 px-7 text-base" disabled={frozen} onClick={() => { if (!lock.current && !guard.current.saving && !guard.current.recoveryPending) onCancel() }}>取消更改</Button>
        <Button type="submit" variant="primary" className="h-12 px-7 text-base" loading={busy} disabled={frozen || readonly || !isDirty}>保存设置</Button>
      </div>
    </footer>
  </form>
}
