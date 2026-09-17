import { safeProjectError } from '../presentation-error'
import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useForm } from 'react-hook-form'
import { ApiClientError } from '../../../shared/api/client'
import { FormField } from '../../../shared/components/FormField'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'
import { emptyProjectForm, projectFormSchema, projectToForm, type ProjectFormValues } from '../form-schema'
import type { ProjectView } from '../types'

export type ProjectFormDialogProps = { open: boolean; project: ProjectView | null; draftSession: string; submissionEpoch?: string; recoveryPending?: boolean; disabled?: boolean; onOpenChange(open: boolean): void; onSubmit(values: ProjectFormValues, expectedRevision: number | null): Promise<unknown>; onLoadLatest?(): Promise<ProjectView>; onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void; onRequestClose?(): Promise<boolean> }

export function ProjectFormDialog({ open, project, draftSession, submissionEpoch = draftSession, recoveryPending = false, disabled = false, onOpenChange, onSubmit, onLoadLatest, onDirtyChange, onSavingChange, onRequestClose }: ProjectFormDialogProps) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [latest, setLatest] = useState<ProjectView | null>(null)
  const formEpoch = useRef(`${project?.projectId ?? 'create'}:${draftSession}`)
  const baselineRevision = useRef(project?.managementRevision ?? null)
  const sessionNonce = useRef(0)
  const sessionIdentity = useRef(`${draftSession}:${submissionEpoch}`)
  const submitLock = useRef(false)
  if (sessionIdentity.current !== `${draftSession}:${submissionEpoch}`) {
    sessionIdentity.current = `${draftSession}:${submissionEpoch}`
    sessionNonce.current += 1
    submitLock.current = false
  }
  const form = useForm<ProjectFormValues>({ resolver: zodResolver(projectFormSchema), defaultValues: project ? projectToForm(project) : emptyProjectForm })
  const { isDirty } = form.formState
  useEffect(() => { onDirtyChange?.(isDirty) }, [isDirty, onDirtyChange])
  useEffect(() => { onSavingChange?.(saving) }, [saving, onSavingChange])
  useEffect(() => { setSaving(false) }, [submissionEpoch])
  useEffect(() => () => { sessionNonce.current += 1; submitLock.current = false }, [])
  useEffect(() => {
    const next = `${project?.projectId ?? 'create'}:${draftSession}`
    if (formEpoch.current !== next) {
      formEpoch.current = next
      baselineRevision.current = project?.managementRevision ?? null
      form.reset(project ? projectToForm(project) : emptyProjectForm)
      setError(null)
      setLatest(null)
    } else if (!form.formState.isDirty && project) {
      baselineRevision.current = project.managementRevision
      form.reset(projectToForm(project))
    }
  }, [draftSession, form, project])

  const requestClose = async () => {
    if (submitLock.current) return
    const ticket = sessionNonce.current
    if (onRequestClose && !(await onRequestClose())) return
    if (ticket === sessionNonce.current) onOpenChange(false)
  }
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitLock.current || disabled) return

    const ticket = sessionNonce.current
    submitLock.current = true
    setSaving(true)

    const validatedSubmit = form.handleSubmit(async values => {
      if (ticket !== sessionNonce.current) return
      setError(null)
      setLatest(null)
      try {
        const result = await onSubmit(values, baselineRevision.current)
        if (result === false || ticket !== sessionNonce.current) return
        form.reset(values)
        onOpenChange(false)
      } catch (caught) {
        if (ticket !== sessionNonce.current) return
        if (caught instanceof ApiClientError && caught.status === 409 && (caught.code === 'PROJECT_NAME_CONFLICT' || caught.fields?.name)) {
          form.setError('name', { message: caught.code === 'PROJECT_NAME_CONFLICT' ? safeProjectError(caught) : '项目名称填写有误，请检查' })
          form.setFocus('name')
        } else if (caught instanceof ApiClientError && caught.status === 409 && caught.code === 'REVISION_CONFLICT') {
          const current = await onLoadLatest?.().catch(() => undefined)
          if (ticket !== sessionNonce.current) return
          setLatest(current ?? null)
          setError(current ? `项目已被其他操作更新。最新名称：${current.name}` : '项目已被其他操作更新，请刷新后重新编辑。')
        } else {
          setError(safeProjectError(caught))
        }
      } finally {
        if (ticket === sessionNonce.current) {
          submitLock.current = false
          setSaving(false)
        }
      }
    }, () => {
      if (ticket !== sessionNonce.current) return
      submitLock.current = false
      setSaving(false)
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
    })
    void validatedSubmit(event)
  }

  return <Modal open={open} onOpenChange={next => { if (!next) void requestClose() }} title={project ? '编辑项目' : '创建项目'} description="填写项目名称和说明。" variant="form" closeDisabled={saving} footer={<><Button type="button" variant="ghost" disabled={saving} onClick={() => void requestClose()}>取消</Button><Button type="submit" form="project-form" variant="primary" disabled={disabled || saving}>{saving ? '正在保存…' : recoveryPending ? '核对保存结果' : project ? '保存' : '创建项目'}</Button></>}>
    <form id="project-form" className="grid gap-5" onSubmit={submit}>
      {recoveryPending ? <p role="status" className="m-0 rounded-control border border-line bg-surface px-3 py-2 text-sm text-muted">上次保存结果尚未确认，先核对结果后再修改。</p> : null}
      {error ? <div role="alert" className="rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink"><p className="m-0">{error}</p>{latest ? <Button type="button" variant="ghost" className="mt-2" onClick={() => { baselineRevision.current = latest.managementRevision; form.reset(projectToForm(latest)); setLatest(null); setError(null) }}>基于最新内容重新编辑</Button> : null}</div> : null}
      <FormField label="项目名称" htmlFor="project-name" error={form.formState.errors.name?.message} hint="1–36 个字符"><Input autoFocus readOnly={saving || recoveryPending} {...form.register('name')} /></FormField>
      <FormField label="项目描述" htmlFor="project-description" error={form.formState.errors.description?.message} hint="最多 120 个字符"><Textarea rows={4} readOnly={saving || recoveryPending} {...form.register('description')} /></FormField>
    </form>
  </Modal>
}
