import { Button } from '../../../shared/components/ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { Input } from '../../../shared/components/ui/input'
import { RadioGroup } from '../../../shared/components/ui/radio-group'
import { Select } from '../../../shared/components/ui/select'
import { TableStatus } from '../../../shared/components/ui/table-status'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { BatchStartDraft, BatchStartRequest, ParameterDefinition, StartErrors } from '../start-schema'
import { toBatchStartRequest, validateBatchStartDraft } from '../start-schema'

type Check = { label: string; value: string; accepted: boolean; status: string }
type Resource = { label: string; value: string }
export type BatchStartDialogProps = {
  open: boolean; formSessionKey: string; automationName: string; expectedAutomationRevision: number; parameters: ParameterDefinition[]
  value: BatchStartDraft; onChange(value: BatchStartDraft): void; onOpenChange(open: boolean): void; onSubmit(request: BatchStartRequest): void | Promise<void>
  checks: Check[]; resources: Resource[]; submitting?: boolean; recovering?: boolean; errors?: StartErrors; errorMessage?: string
  allowUnlimited?: boolean; continueAfterFailure?: boolean; dataBatch?: boolean
  onConfigure?(): void
  recoveryActions?: ReactNode
  inputPreview?: ReactNode
  temporaryEnvironmentOverride?: BatchStartRequest['environmentOverride']
}
const booleanOptions = [{ value: 'omitted', label: '不提供' }, { value: 'null', label: '空值' }, { value: 'true', label: '是' }, { value: 'false', label: '否' }]

export function BatchStartDialog({ open, formSessionKey, automationName, expectedAutomationRevision, parameters, value, onChange, onOpenChange, onSubmit, checks, resources, submitting = false, recovering = false, errors: serverErrors = {}, errorMessage, onConfigure, recoveryActions, inputPreview, allowUnlimited = false, continueAfterFailure = false, dataBatch = false, temporaryEnvironmentOverride = { source: 'newFromProfile' } }: BatchStartDialogProps) {
  const [localSubmitting, setLocalSubmitting] = useState(false)
  const submitLatch = useRef(false), session = useRef(0)
  useEffect(() => { session.current += 1; submitLatch.current = false; setLocalSubmitting(false) }, [formSessionKey])
  const busy = submitting || recovering || localSubmitting
  const errors = { ...validateBatchStartDraft(value, parameters, { allowUnlimited, dataBatch }), ...serverErrors }
  const parameterIds = new Set(parameters.map(parameter => parameter.parameterId))
  const staleParameterErrors = Object.entries(errors).filter(([path]) => path.startsWith('parameters.') && !parameterIds.has(path.slice('parameters.'.length)))
  const needsConfigure = checks.some(check => !check.accepted) || staleParameterErrors.length > 0
  const setParameter = (id: string, next: BatchStartDraft['parameters'][string] | undefined) => { const nextParameters = { ...value.parameters }; if (next === undefined) delete nextParameters[id]; else nextParameters[id] = next; onChange({ ...value, parameters: nextParameters }) }
  const submit = () => {
    const request = toBatchStartRequest(value, parameters, expectedAutomationRevision, { allowUnlimited, dataBatch })
    if (!request || !checks.every(check => check.accepted) || busy || submitLatch.current) return
    submitLatch.current = true; setLocalSubmitting(true)
    const currentSession = session.current
    const finish = () => { if (session.current === currentSession) { submitLatch.current = false; setLocalSubmitting(false) } }
    void Promise.resolve().then(() => onSubmit(request)).then(finish, finish)
  }
  return <Dialog open={open} onOpenChange={onOpenChange} busy={busy}><DialogContent className="max-h-[88vh] w-[min(92vw,43rem)] overflow-y-auto" aria-describedby="batch-start-description">
    <DialogClose aria-label="关闭启动弹窗" className="absolute right-4 top-4 text-xl text-muted" disabled={busy}>×</DialogClose>
    <div><DialogTitle className="text-2xl">启动自动化</DialogTitle><DialogDescription id="batch-start-description">{automationName}</DialogDescription></div>
    <p className="m-0 rounded-control border border-line bg-surface-subtle p-3 text-sm">启动后会冻结当前配置、工作流和参数，后续修改不会影响本批次。</p>
    {errorMessage ? <p role="alert" className="m-0 rounded-control border border-danger/30 p-3 text-sm text-danger">{errorMessage}</p> : null}
    {recoveryActions}
    {staleParameterErrors.length ? <p role="alert" className="m-0 rounded-control border border-warning/30 p-3 text-sm text-warning">启动参数已变化：{staleParameterErrors.map(([, message]) => message).join('；')}</p> : null}
    <section className="grid gap-2"><div className="flex items-center justify-between gap-3"><h3 className="m-0 text-sm font-semibold">运行检查</h3>{needsConfigure && onConfigure ? <Button size="sm" disabled={busy} onClick={onConfigure}>返回配置修复</Button> : null}</div><div className="overflow-hidden rounded-control border border-line">{checks.map(check => <div className="grid grid-cols-[9rem_minmax(0,1fr)_auto] gap-3 border-b border-line px-3 py-2 last:border-0" key={check.label}><span>{check.label}</span><span className="min-w-0 truncate">{check.value}</span><TableStatus tone={check.accepted ? 'success' : 'warning'}>{check.status}</TableStatus></div>)}</div></section>
    {inputPreview}
    <section className="grid gap-3"><h3 className="m-0 text-sm font-semibold">本次参数</h3>{parameters.map(parameter => { const present = Object.hasOwn(value.parameters, parameter.parameterId), draft = value.parameters[parameter.parameterId], error = errors[`parameters.${parameter.parameterId}`], id = `batch-parameter-${parameter.parameterId}-error`; return <label className="grid gap-2 text-sm sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-start" key={parameter.parameterId}><span className="pt-2 font-medium">{parameter.name}{parameter.required ? <span className="text-danger"> *</span> : null}</span><span className="grid gap-1">{parameter.type === 'boolean' ? <Select aria-label={parameter.name} value={!present ? 'omitted' : draft === null ? 'null' : String(draft)} options={booleanOptions} clearable={false} disabled={busy} errorMessage={error} onValueChange={choice => setParameter(parameter.parameterId, choice === 'omitted' ? undefined : choice === 'null' ? null : choice === 'true')}/> : <Input aria-label={parameter.name} value={draft && typeof draft === 'object' ? draft.raw : draft == null ? '' : String(draft)} data-value-presence={!present ? 'omitted' : draft === null ? 'null' : 'provided'} disabled={busy} aria-invalid={Boolean(error)} aria-describedby={error ? id : undefined} onChange={event => setParameter(parameter.parameterId, parameter.type === 'number' ? { raw: event.target.value } : event.target.value)}/>} {error && parameter.type !== 'boolean' ? <span id={id} role="alert" className="text-xs text-danger">{error}</span> : null}{parameter.type !== 'boolean' ? <span className="flex gap-2"><Button size="sm" variant="ghost" disabled={busy || !present} onClick={() => setParameter(parameter.parameterId, undefined)}>不提供</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => setParameter(parameter.parameterId, null)}>设为空值</Button></span> : null}</span></label>})}</section>
    {allowUnlimited ? <RadioGroup label="执行次数" value={value.unlimited ? 'unlimited' : 'finite'} disabled={busy} options={[{ value: 'finite', label: '有限次数' }, { value: 'unlimited', label: '不限次数' }]} onValueChange={choice => onChange({ ...value, unlimited: choice === 'unlimited' })}/> : null}
    <label className="grid gap-2 text-sm"><span className="font-medium">本次任务数</span><Input className="max-w-64" aria-label="本次任务数" inputMode="numeric" value={value.maxTasks} disabled={busy || value.unlimited} aria-invalid={Boolean(errors.maxTasks)} aria-describedby={errors.maxTasks ? 'batch-max-tasks-error' : undefined} onChange={event => onChange({ ...value, maxTasks: event.target.value })}/>{errors.maxTasks ? <span id="batch-max-tasks-error" role="alert" className="text-xs text-danger">{errors.maxTasks}</span> : <span className="text-xs text-muted">范围 1–100，自动化配置值为默认值</span>}</label>
    <label className="grid gap-2 text-sm"><span className="font-medium">请求并发数</span><Input className="max-w-64" aria-label="请求并发数" inputMode="numeric" value={dataBatch ? value.concurrency ?? '1' : '1'} disabled={busy || !dataBatch} aria-invalid={Boolean(errors.concurrency)} aria-describedby={errors.concurrency ? 'batch-concurrency-error' : undefined} onChange={event => onChange({ ...value, concurrency: event.target.value })}/>{errors.concurrency ? <span id="batch-concurrency-error" role="alert" className="text-xs text-danger">{errors.concurrency}</span> : null}<span className="text-xs text-muted">{dataBatch ? '实际并发取本次请求、自动化并发、最大活动实例和执行容量的最小值' : '参数型自动化按顺序执行，并发数固定为 1'}</span></label>
    <p className="m-0 text-sm">{continueAfterFailure ? '失败后继续领取新任务' : dataBatch ? '首次确认失败后停止领取新任务；已领取任务继续到结束' : '首次确认失败后停止执行后续排队任务'}。使用自动化已保存的失败策略。</p>
    <section className="grid gap-2"><h3 className="m-0 text-sm font-semibold">本次环境覆盖</h3><RadioGroup label="本次环境覆盖" value={value.environmentOverride ? 'temporary' : 'automation'} disabled={busy} options={[{ value: 'automation', label: '使用自动化配置' }, { value: 'temporary', label: '每个任务创建临时环境' }]} onValueChange={choice => onChange(choice === 'automation' ? { ...value, environmentOverride: undefined } : { ...value, environmentOverride: structuredClone(temporaryEnvironmentOverride) })}/><p className="m-0 text-xs text-muted">本次覆盖只用于这个批次，不会修改自动化默认设置</p></section>
    <section className="grid gap-2"><h3 className="m-0 text-sm font-semibold">资源摘要</h3><div className="grid gap-2 rounded-control border border-line p-3 sm:grid-cols-4">{resources.map(resource => <span className="min-w-0" key={resource.label}><small className="block text-muted">{resource.label}</small><strong className="block truncate" title={resource.value}>{resource.value}</strong></span>)}</div><p className="m-0 rounded-control bg-surface-subtle p-2 text-sm">{value.unlimited ? '不限次数：只要存在符合条件的数据就继续运行，可随时停止批次' : `最多 ${value.maxTasks || '—'} 个任务；请求并发 ${value.concurrency ?? '1'}`}</p></section>
    <footer className="flex justify-end gap-2 border-t border-line pt-4"><Button disabled={busy} onClick={() => onOpenChange(false)}>取消</Button><Button variant="primary" loading={busy} loadingText={recovering ? '正在核对启动结果…' : '正在创建批次…'} disabled={busy || Boolean(Object.keys(errors).length) || checks.some(check => !check.accepted)} onClick={submit}>{value.unlimited ? '启动不限次数批次' : `启动 ${value.maxTasks || '—'} 个任务`}</Button></footer>
  </DialogContent></Dialog>
}
