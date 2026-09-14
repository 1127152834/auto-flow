import { useEffect, useRef, useState } from 'react'
import { Clock, Cube, Database, SlidersHorizontal } from '@phosphor-icons/react'
import { Input } from '../../../shared/components/ui/input'
import { RadioGroup } from '../../../shared/components/ui/radio-group'
import { Switch } from '../../../shared/components/ui/switch'
import type { DraftState, FieldErrors, RunPolicy } from './policy-types'

export type RunPolicyEditorProps = {
  value: RunPolicy
  onChange(value: RunPolicy): void
  disabled?: boolean
  errors?: FieldErrors
  resetKey?: string | number
  onDraftStateChange?(state: DraftState): void
}

export function RunPolicyEditor({ value, onChange, disabled = false, errors = {}, resetKey, onDraftStateChange }: RunPolicyEditorProps) {
  const [maxTasksDraft, setMaxTasksDraft] = useState(String(value.maxTasks ?? ''))
  const [timeoutDraft, setTimeoutDraft] = useState(String(value.automaticExecutionTimeoutSeconds / 60))
  const pendingMaxTasks = useRef<number | undefined>(undefined), pendingTimeout = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (pendingMaxTasks.current === value.maxTasks) pendingMaxTasks.current = undefined
    else setMaxTasksDraft(String(value.maxTasks ?? ''))
  }, [value.maxTasks])
  useEffect(() => {
    if (pendingTimeout.current === value.automaticExecutionTimeoutSeconds) pendingTimeout.current = undefined
    else setTimeoutDraft(String(value.automaticExecutionTimeoutSeconds / 60))
  }, [value.automaticExecutionTimeoutSeconds])
  useEffect(() => {
    setMaxTasksDraft(String(value.maxTasks ?? ''))
    setTimeoutDraft(String(value.automaticExecutionTimeoutSeconds / 60))
  }, [resetKey])
  const maxTasks = Number(maxTasksDraft)
  const maxTasksError = maxTasksDraft.trim() === '' || !Number.isInteger(maxTasks) || maxTasks < 1 || maxTasks > 100 ? '最大任务数必须是 1–100 的整数' : errors.maxTasks
  const timeout = Number(timeoutDraft)
  const timeoutError = timeoutDraft.trim() === '' || !Number.isFinite(timeout) || timeout <= 0 || !Number.isFinite(timeout * 60) ? '请输入有限的正数' : errors.automaticExecutionTimeoutSeconds
  const draftDirty = maxTasksDraft !== String(value.maxTasks ?? '') || timeoutDraft !== String(value.automaticExecutionTimeoutSeconds / 60)
  const draftValid = !maxTasksError && !timeoutError && !Object.values(errors).some(Boolean)
  const draftCallback = useRef(onDraftStateChange), lastDraftState = useRef<DraftState | undefined>(undefined)
  useEffect(() => { draftCallback.current = onDraftStateChange }, [onDraftStateChange])
  useEffect(() => {
    if (lastDraftState.current?.dirty === draftDirty && lastDraftState.current.valid === draftValid) return
    lastDraftState.current = { dirty: draftDirty, valid: draftValid }
    draftCallback.current?.(lastDraftState.current)
  }, [draftDirty, draftValid])
  const maxTasksErrorId = 'run-policy-max-tasks-error'
  const timeoutErrorId = 'run-policy-timeout-error'

  return <section className="grid max-w-5xl gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)] lg:items-start">
    <div className="grid gap-6">
    <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">最大任务数 <span className="text-danger">*</span></span>
      <Input className="max-w-64" type="text" inputMode="numeric" aria-label="最大任务数" value={maxTasksDraft} disabled={disabled} aria-invalid={Boolean(maxTasksError)} aria-describedby={maxTasksError ? maxTasksErrorId : undefined} onChange={event => {
        const draft = event.target.value
        setMaxTasksDraft(draft)
        const parsed = Number(draft)
        const valid = Boolean(draft.trim()) && Number.isInteger(parsed) && parsed >= 1 && parsed <= 100
        if (valid) { pendingMaxTasks.current = parsed; onChange({ ...value, maxTasks: parsed }) }
      }} onBlur={() => { if (!maxTasksError) setMaxTasksDraft(String(value.maxTasks ?? '')) }}/>
      {maxTasksError ? <span id={maxTasksErrorId} role="alert" className="text-xs text-danger">{maxTasksError}</span> : <span className="text-xs text-muted">范围 1–100，新建自动化默认 1</span>}
    </label>
    <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">并发任务数</span>
      <Input className="max-w-64" type="number" aria-label="并发任务数" value={1} disabled />
      <span className="text-xs text-muted">当前版本按顺序执行</span>
    </label>
    <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-center"><span className="font-medium">失败处理</span><span className="flex items-center gap-3">
      <Switch aria-label="某个任务失败后停止创建后续任务" checked={!value.continueAfterFailure} disabled={disabled} onCheckedChange={stop => onChange({ ...value, continueAfterFailure: !stop })}/>
      某个任务失败后停止创建后续任务</span>
    </label>
    <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">单任务超时 <span className="text-danger">*</span></span>
      <span className="flex max-w-72 items-center gap-2"><Input type="text" inputMode="decimal" aria-label="单任务超时（分钟）" value={timeoutDraft} disabled={disabled} aria-invalid={Boolean(timeoutError)} aria-describedby={timeoutError ? timeoutErrorId : undefined} onChange={event => {
        const draft = event.target.value
        setTimeoutDraft(draft)
        const minutes = Number(draft)
        const seconds = minutes * 60
        const valid = Boolean(draft.trim()) && Number.isFinite(minutes) && minutes > 0 && Number.isFinite(seconds)
        if (valid) { pendingTimeout.current = seconds; onChange({ ...value, automaticExecutionTimeoutSeconds: seconds }) }
      }} onBlur={() => { if (!timeoutError) setTimeoutDraft(String(value.automaticExecutionTimeoutSeconds / 60)) }}/><span className="shrink-0">分钟</span></span>
      {timeoutError ? <span id={timeoutErrorId} role="alert" className="text-xs text-danger">{timeoutError}</span> : null}
    </label>
    <div className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2">
      <span className="pt-2 font-medium">任务结束时环境处理</span>
      <RadioGroup className="[&_div]:gap-3 [&_label]:rounded-control [&_label]:border [&_label]:border-line [&_label]:bg-surface [&_label]:px-3 [&_label]:py-1" label="任务结束时环境处理" value="cleanup" disabled options={[{ value: 'cleanup', label: '关闭并清理临时环境' }, { value: 'retain', label: '保留环境（暂未开放）' }]} onValueChange={() => undefined}/>
      <span className="text-xs text-muted">当前按最大任务数执行；无限运行暂未开放</span>
    </div>
    </div>
    <aside className="overflow-hidden rounded-control border border-line bg-surface text-sm" aria-label="本次运行策略">
      <h4 className="m-0 bg-surface-subtle px-5 py-4 text-base font-semibold">本次运行策略</h4>
      <ul className="m-0 grid list-none px-5 py-2"><li className="flex items-center gap-3 border-b border-line py-3"><Database size={21} aria-hidden/>最多 {value.maxTasks ?? '—'} 个任务</li><li className="flex items-center gap-3 border-b border-line py-3"><SlidersHorizontal size={21} aria-hidden/>串行执行</li><li className="flex items-center gap-3 border-b border-line py-3"><Clock size={21} aria-hidden/>单任务最长 {value.automaticExecutionTimeoutSeconds / 60} 分钟</li><li className="flex items-center gap-3 py-3"><Cube size={21} aria-hidden/>每个任务使用独立临时环境</li></ul>
    </aside>
  </section>
}
