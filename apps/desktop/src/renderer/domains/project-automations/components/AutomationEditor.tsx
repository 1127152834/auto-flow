import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { FileText, FlowArrow, SlidersHorizontal, Browser, Lightning, Info, Clock } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { Textarea } from '../../../shared/components/ui/textarea'
import { automationToForm, normalizeAutomation, validateAutomationForm, type AutomationFormErrors } from '../form-schema'
import type { AutomationWrite } from '../types'
import { EnvironmentPolicyEditor, type EnvironmentPolicyEditorProps } from './EnvironmentPolicyEditor'
import { ParameterEditor } from './ParameterEditor'
import type { DraftState } from './policy-types'
import { RunPolicyEditor } from './RunPolicyEditor'

type Tab = 'overview' | 'inputs' | 'resources' | 'run'
type ResourceOption = { id: string; name: string }
export type WorkflowOption = ResourceOption & { revision?: number; updatedAt?: string; runnable?: boolean; validationMessage?: string }

export type AutomationEditorProps = {
  initialValue: AutomationWrite
  resetKey: string
  workflowOptions: WorkflowOption[]
  isNew?: boolean
  disabled?: boolean
  saving?: boolean
  recovering?: boolean
  error?: string
  serverErrors?: Record<string, string | undefined>
  validationNotice?: ReactNode
  environmentOptions: Pick<EnvironmentPolicyEditorProps, 'profiles' | 'proxies' | 'pools' | 'modelProviders' | 'projectDefaults' | 'environments'>
  renderInputPlan(value: AutomationWrite['inputPlan'], onChange: (value: AutomationWrite['inputPlan']) => void, disabled: boolean, draft: { resetKey: string; errors: Record<string, string | undefined>; onDraftStateChange(state: DraftState): void }): ReactNode
  onSubmit(value: AutomationWrite): void | Promise<void>
  onCancel(): void
  onDraftStateChange?(state: DraftState): void
  onOpenStudio?(workflowId: string): void
  onStartRun?(): void
}

const tabs: { value: Tab; label: string }[] = [
  { value: 'overview', label: '基本信息' },
  { value: 'inputs', label: '输入与参数' },
  { value: 'resources', label: '资源与环境' },
  { value: 'run', label: '运行设置' },
]

const tabFor = (field: string): Tab => field.startsWith('inputPlan') || field.startsWith('parameterSchema') ? 'inputs' : field.startsWith('environmentPolicy') ? 'resources' : field.startsWith('runPolicy') ? 'run' : 'overview'
const valueAt = (value: unknown, path: string) => path.split('.').reduce<unknown>((current, part) => current && typeof current === 'object' ? (current as Record<string, unknown>)[part] : undefined, value)
const typedSnapshot = (value: unknown) => JSON.stringify([value])

export function AutomationEditor({ initialValue, resetKey, workflowOptions, isNew = false, disabled = false, saving = false, recovering = false, error, serverErrors = {}, validationNotice, environmentOptions, renderInputPlan, onSubmit, onCancel, onDraftStateChange, onOpenStudio, onStartRun }: AutomationEditorProps) {
  const locked = disabled || saving || recovering
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [inputDraft, setInputDraft] = useState<DraftState>({ dirty: false, valid: true })
  const [parameterDraft, setParameterDraft] = useState<DraftState>({ dirty: false, valid: true })
  const [runDraft, setRunDraft] = useState<DraftState>({ dirty: false, valid: true })
  const { register, watch, setValue, reset, formState } = useForm<AutomationWrite>({ defaultValues: automationToForm(initialValue), mode: 'onChange' })
  const value = watch()
  useEffect(() => {
    reset(automationToForm(initialValue))
    setInputDraft({ dirty: false, valid: true })
    setParameterDraft({ dirty: false, valid: true })
    setRunDraft({ dirty: false, valid: true })
  }, [resetKey, reset]) // resetKey is the only parent-controlled reset boundary.

  const serverErrorRef = useRef<{ signature: string; entries: Record<string, { message: string; value: string }> }>({ signature: '', entries: {} })
  const serverErrorSignature = JSON.stringify(Object.entries(serverErrors).filter((entry): entry is [string, string] => Boolean(entry[1])).sort(([left], [right]) => left.localeCompare(right)))
  if (serverErrorRef.current.signature !== serverErrorSignature) serverErrorRef.current = {
    signature: serverErrorSignature,
    entries: Object.fromEntries(Object.entries(serverErrors).filter((entry): entry is [string, string] => Boolean(entry[1])).map(([path, message]) => [path, { message, value: typedSnapshot(valueAt(value, path)) }])),
  }
  for (const [path, entry] of Object.entries(serverErrorRef.current.entries)) if (entry.value !== typedSnapshot(valueAt(value, path))) delete serverErrorRef.current.entries[path]
  const retainedServerErrors = Object.fromEntries(Object.entries(serverErrorRef.current.entries).map(([path, entry]) => [path, entry.message]))
  const clientErrors = validateAutomationForm(value)
  const errors = useMemo(() => Object.fromEntries(Object.entries({ ...clientErrors, ...retainedServerErrors }).filter(([, message]) => Boolean(message))) as AutomationFormErrors, [clientErrors, retainedServerErrors])
  const counts = useMemo(() => {
    const result = Object.keys(errors).reduce<Record<Tab, number>>((totals, field) => { totals[tabFor(field)] += 1; return totals }, { overview: 0, inputs: 0, resources: 0, run: 0 })
    if ((!parameterDraft.valid || !inputDraft.valid) && result.inputs === 0) result.inputs = 1
    if (!runDraft.valid && result.run === 0) result.run = 1
    return result
  }, [errors, parameterDraft.valid, inputDraft.valid, runDraft.valid])
  const dirty = formState.isDirty || inputDraft.dirty || parameterDraft.dirty || runDraft.dirty
  const valid = !Object.keys(errors).length && parameterDraft.valid && inputDraft.valid && runDraft.valid
  const lastDraft = useRef<DraftState | undefined>(undefined)
  const draftCallback = useRef(onDraftStateChange)
  useEffect(() => { draftCallback.current = onDraftStateChange }, [onDraftStateChange])
  useEffect(() => {
    if (lastDraft.current?.dirty === dirty && lastDraft.current.valid === valid) return
    lastDraft.current = { dirty, valid }
    draftCallback.current?.({ dirty, valid })
  }, [dirty, valid])

  const change = <Key extends keyof AutomationWrite>(field: Key, next: AutomationWrite[Key]) => setValue(field, next as never, { shouldDirty: true })
  const focusFirstError = () => {
    const first = Object.keys(errors)[0]
    const tab = first ? tabFor(first) : !parameterDraft.valid || !inputDraft.valid ? 'inputs' : !runDraft.valid ? 'run' : undefined
    if (!tab) return false
    setActiveTab(tab)
    requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-tab-panel="${tab}"] [aria-invalid="true"]`)?.focus())
    return true
  }
  const submit = async () => {
    if (locked || !dirty) return
    if (!valid) { focusFirstError(); return }
    await onSubmit(normalizeAutomation(value))
  }
  const workflow = workflowOptions.find(option => option.id === value.workflowId)
  const workflowSelectOptions = [
    ...(value.workflowId && !workflow ? [{ value: value.workflowId, label: '关联工作流暂不可用', disabled: true }] : []),
    ...workflowOptions.map(option => ({ value: option.id, label: option.name })),
  ]
  const fieldErrors = (prefix: string): AutomationFormErrors => Object.fromEntries(Object.entries(errors).filter(([key]) => key.startsWith(prefix)).map(([key, message]) => [key.slice(prefix.length), message]))
  const parameterErrors = Object.fromEntries(Object.entries(errors).flatMap(([key, message]) => {
    const match = /^parameterSchema\.(\d+)\.(.+)$/.exec(key)
    const parameter = match ? value.parameterSchema[Number(match[1])] : undefined
    return parameter ? [[`${parameter.parameterId}.${match?.[2]}`, message]] : []
  }))
  const nameMessageId = 'automation-editor-name-message'
  const descriptionMessageId = 'automation-editor-description-message'
  const saveState = isNew ? dirty ? '新增草稿' : '尚未创建' : dirty ? '有未保存修改' : '配置已保存'

  return <section className="rounded-card border border-line bg-surface" aria-label="自动化配置编辑器">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-5 py-4">
      <div className="flex min-w-0 flex-1 items-center gap-4"><span className="grid size-16 shrink-0 place-items-center rounded-control border border-line bg-surface-subtle text-clay" aria-hidden="true"><FileText size={32}/></span><div className="min-w-0"><div className="flex flex-wrap items-center gap-3"><h2 className="m-0 break-words text-2xl font-semibold">{value.name || '新建自动化'}</h2><span className={`rounded-control px-2 py-1 text-xs ${dirty || isNew ? 'bg-clay-soft text-clay' : 'bg-success/10 text-success'}`}>{saveState}</span></div><p className="mb-0 mt-1 break-words text-sm text-muted">{value.description || '配置工作流、输入、资源和运行设置'}</p></div></div>
      <div className="flex gap-2">{onOpenStudio ? <Button disabled={locked || !value.workflowId} onClick={() => onOpenStudio(value.workflowId)}>打开 Studio</Button> : null}{onStartRun ? <Button variant="primary" disabled={locked || dirty} onClick={onStartRun}>启动运行</Button> : null}</div>
    </header>
    {validationNotice}
    {error ? <p role="alert" className="m-4 border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{error}</p> : null}
    <Tabs value={activeTab} onValueChange={tab => setActiveTab(tab as Tab)} className="px-5 pt-2">
      <TabsList aria-label="自动化配置页签" className="w-full justify-start gap-5">{tabs.map(tab => <TabsTrigger key={tab.value} value={tab.value}>{tab.label}{counts[tab.value] ? <span aria-label={`${counts[tab.value]} 个错误`} className="ml-2 text-danger">{counts[tab.value]}</span> : null}</TabsTrigger>)}</TabsList>
      <TabsContent forceMount value="overview" hidden={activeTab !== 'overview'} data-tab-panel="overview" className="min-h-[22rem] py-5">
        <div className="grid gap-6">
          <label className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start"><span className="pt-2 text-sm font-medium">自动化名称 <span className="text-danger">*</span></span><span><Input aria-label="自动化名称" disabled={locked} aria-invalid={Boolean(errors.name)} aria-describedby={nameMessageId} {...register('name', { onChange: event => change('name', event.target.value) })}/>{errors.name ? <span id={nameMessageId} role="alert" className="mt-1 block text-xs text-danger">{errors.name}</span> : <span id={nameMessageId} className="mt-1 block text-xs text-muted">1–80 个字符</span>}</span></label>
          <label className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start"><span className="pt-2 text-sm font-medium">用途说明</span><span><Textarea aria-label="用途说明" disabled={locked} aria-invalid={Boolean(errors.description)} aria-describedby={descriptionMessageId} className="resize-y" {...register('description', { onChange: event => change('description', event.target.value) })}/>{errors.description ? <span id={descriptionMessageId} role="alert" className="mt-1 block text-xs text-danger">{errors.description}</span> : <span id={descriptionMessageId} className="mt-1 block text-xs text-muted">最多 1000 个字符</span>}</span></label>
          <div className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start"><span className="pt-2 text-sm font-medium">关联工作流</span><div>{isNew ? <Select aria-label="关联工作流" value={value.workflowId || null} options={workflowSelectOptions} clearable={false} disabled={locked} errorMessage={errors.workflowId} onValueChange={workflowId => workflowId && change('workflowId', workflowId)}/> : <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-line bg-surface-subtle p-3"><span className="flex min-w-0 flex-wrap items-center gap-3"><FlowArrow size={28} className="shrink-0 text-clay" aria-hidden/><strong className="break-words">{workflow?.name ?? '关联工作流暂不可用'}</strong><small className="text-muted">{workflow?.runnable === true ? '可以运行' : workflow?.runnable === false ? '不可运行' : '未能读取校验状态'}</small>{workflow?.updatedAt && Number.isFinite(Date.parse(workflow.updatedAt)) ? <small className="flex items-center gap-1 text-muted"><Clock aria-hidden/>最近保存 {new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(workflow.updatedAt))}</small> : null}</span>{onOpenStudio ? <Button size="sm" disabled={locked} onClick={() => onOpenStudio(value.workflowId)}>打开 Studio</Button> : null}</div>}<p className="mb-0 mt-2 text-xs text-muted">关联建立后不能通过普通编辑替换工作流</p></div></div>

        </div>
      </TabsContent>
      <TabsContent forceMount value="inputs" hidden={activeTab !== 'inputs'} data-tab-panel="inputs" className="min-h-[22rem] py-5"><div className="grid gap-7">{renderInputPlan(value.inputPlan, next => { change('inputPlan', next); if (!next.inputs.length) change('runPolicy', { ...value.runPolicy, concurrency: 1, maxLiveInstances: 1 }) }, locked, { resetKey, onDraftStateChange: setInputDraft, errors: Object.fromEntries(Object.entries(errors).flatMap(([path, message]) => { const match = /^inputPlan\.inputs\.(\d+)(?:\.(.*))?$/.exec(path); const item = match ? value.inputPlan.inputs[Number(match[1])] : undefined; return item ? [[`${item.inputId}.${match?.[2] ?? 'configuration'}`, message]] : [] })) })}<ParameterEditor value={value.parameterSchema} onChange={next => change('parameterSchema', next)} disabled={locked} errors={parameterErrors} resetKey={resetKey} onDraftStateChange={setParameterDraft}/></div></TabsContent>
      <TabsContent forceMount value="resources" hidden={activeTab !== 'resources'} data-tab-panel="resources" className="min-h-[22rem] py-5"><EnvironmentPolicyEditor value={value.environmentPolicy} inputs={value.inputPlan.inputs} onChange={next => change('environmentPolicy', next)} disabled={locked} errors={fieldErrors('environmentPolicy.')} {...environmentOptions}/></TabsContent>
      <TabsContent forceMount value="run" hidden={activeTab !== 'run'} data-tab-panel="run" className="min-h-[22rem] py-5"><RunPolicyEditor dataBatch={value.inputPlan.inputs.length > 0} value={value.runPolicy} onChange={next => change('runPolicy', { ...next, maxTasks: next.maxTasks ?? value.runPolicy.maxTasks })} disabled={locked} errors={fieldErrors('runPolicy.')} resetKey={resetKey} onDraftStateChange={setRunDraft}/></TabsContent>
    </Tabs>
    {activeTab !== 'resources' ? <aside aria-label="配置摘要" className="mx-5 flex flex-wrap items-center gap-4 border-t border-line py-4 text-sm"><strong className="mr-4">配置摘要</strong><span className="flex items-center gap-2 border-l border-line pl-4"><SlidersHorizontal size={21} aria-hidden/>{value.parameterSchema.length} 个参数</span><span className="flex items-center gap-2 border-l border-line pl-4"><Browser size={21} aria-hidden/>{value.environmentPolicy.source === 'newFromProfile' ? '临时浏览器环境' : '已保存的环境策略'}</span><span className="flex items-center gap-2 border-l border-line pl-4"><FileText size={21} aria-hidden/>最多 {value.runPolicy.maxTasks} 个任务</span><span className="flex items-center gap-2 border-l border-line pl-4"><Lightning size={21} aria-hidden/>{value.inputPlan.inputs.length ? `配置并发上限 ${Math.min(value.runPolicy.concurrency, value.runPolicy.maxLiveInstances)}` : '并发 1'}</span></aside> : null}
    <footer className="sticky bottom-0 z-10 rounded-b-card bg-surface flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4"><span className="flex items-center gap-2 text-sm text-muted"><Info size={18} aria-hidden/>{recovering ? '正在核对保存结果…' : saving ? '正在保存配置…' : dirty ? '有未保存的修改' : '没有未保存的修改'}</span><div className="flex gap-2"><Button disabled={locked || !dirty} onClick={onCancel}>取消修改</Button><Button variant="primary" loading={saving || recovering} loadingText={recovering ? '正在核对…' : '正在保存…'} disabled={locked || !dirty} onClick={() => void submit()}>保存配置</Button></div></footer>
  </section>
}
