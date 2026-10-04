import { useEffect, useRef, useState } from 'react'
import { Clock, Cube, Database, SlidersHorizontal } from '@phosphor-icons/react'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import type { DraftState, FieldErrors, RunPolicy } from './policy-types'

export type RunPolicyEditorProps = {
  value: RunPolicy
  onChange(value: RunPolicy): void
  dataBatch?: boolean
  disabled?: boolean
  errors?: FieldErrors
  resetKey?: string | number
  onDraftStateChange?(state: DraftState): void
  /** Remediation M1 R1-11: machine-wide running-browser limit, when known. */
  machineLimit?: number | null
  /** Browser reuse needs a browser created from a profile; saved environments keep their own. */
  freshBrowser?: boolean
}

const claimModeOptions = [
  { value: 'unprocessed', label: '只处理还没处理过的数据', disabled: false },
  { value: 'cycle', label: '每次重新处理全部数据', disabled: false },
  { value: 'retryFailed', label: '只重试失败的数据', disabled: false },
]

export function RunPolicyEditor({ value, onChange, dataBatch = false, disabled = false, errors = {}, resetKey, onDraftStateChange, machineLimit, freshBrowser = true }: RunPolicyEditorProps) {
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
  const [limits, setLimits] = useState({ concurrency: String(value.concurrency), maxLiveInstances: String(value.maxLiveInstances) })
  useEffect(() => { setLimits(previous => ({ ...previous, concurrency: String(value.concurrency) })) }, [value.concurrency])
  useEffect(() => { setLimits(previous => ({ ...previous, maxLiveInstances: String(value.maxLiveInstances) })) }, [value.maxLiveInstances])
  useEffect(() => { setLimits({ concurrency: String(value.concurrency), maxLiveInstances: String(value.maxLiveInstances) }) }, [resetKey, dataBatch])
  const limitErrors = Object.fromEntries((['concurrency', 'maxLiveInstances'] as const).map(key => [key, (!limits[key].trim() || !Number.isInteger(Number(limits[key])) || Number(limits[key]) < 1 || Number(limits[key]) > 100) ? '必须是 1–100 的整数' : errors[key]]))
  // Remediation M2 R2-03/R2-04: a missing mode is how automations saved earlier keep reusing rows.
  const [budgetDraft, setBudgetDraft] = useState(String(value.retryBudget ?? 3))
  useEffect(() => { setBudgetDraft(String(value.retryBudget ?? 3)) }, [value.retryBudget, resetKey])
  const budget = Number(budgetDraft)
  const budgetError = !budgetDraft.trim() || !Number.isInteger(budget) || budget < 1 || budget > 20 ? '必须是 1–20 的整数' : undefined
  const maxTasks = Number(maxTasksDraft)
  const maxTasksError = maxTasksDraft.trim() === '' || !Number.isInteger(maxTasks) || maxTasks < 1 || maxTasks > 100 ? '最大任务数必须是 1–100 的整数' : errors.maxTasks
  const timeout = Number(timeoutDraft)
  const timeoutError = timeoutDraft.trim() === '' || !Number.isFinite(timeout) || timeout <= 0 || !Number.isFinite(timeout * 60) ? '请输入有限的正数' : errors.automaticExecutionTimeoutSeconds
  const draftDirty = (limits.concurrency !== String(value.concurrency) || limits.maxLiveInstances !== String(value.maxLiveInstances)) || maxTasksDraft !== String(value.maxTasks ?? '') || timeoutDraft !== String(value.automaticExecutionTimeoutSeconds / 60)
  const draftValid = !(dataBatch && budgetError) && !maxTasksError && !timeoutError && !Object.values(limitErrors).some(Boolean) && !Object.values(errors).some(Boolean)
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
    {(['concurrency', 'maxLiveInstances'] as const).map(key => <label key={key} className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">{key === 'concurrency' ? '请求并发数' : '最大活动实例'}</span>
      <Input className="max-w-64" inputMode="numeric" aria-label={key === 'concurrency' ? '请求并发数' : '最大活动实例'} value={limits[key]} disabled={disabled} aria-invalid={Boolean(limitErrors[key])} aria-describedby={limitErrors[key] ? `run-policy-${key}-error` : undefined} onChange={event => {
        const draft = event.target.value, parsed = Number(draft)
        setLimits(previous => ({ ...previous, [key]: draft }))
        if (draft.trim() && Number.isInteger(parsed) && parsed >= 1 && parsed <= 100) onChange({ ...value, [key]: parsed })
      }}/>
      {limitErrors[key] ? <span role="alert" id={`run-policy-${key}-error`} className="text-xs text-danger">{limitErrors[key]}</span> : <span className="text-xs text-muted">范围 1–100{key === 'concurrency' && machineLimit ? `；本机当前最多同时运行 ${machineLimit} 个浏览器${Number(limits.concurrency) > machineLimit ? `，实际同时运行不超过 ${machineLimit} 个` : ''}` : ''}</span>}
    </label>)}
    {dataBatch ? <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">领取方式</span>
      <Select className="max-w-72" aria-label="领取方式" value={value.claimMode ?? 'cycle'} clearable={false} disabled={disabled} options={claimModeOptions} onValueChange={mode => { if (mode) onChange({ ...value, claimMode: mode as NonNullable<RunPolicy['claimMode']> }) }}/>
      <span className="text-xs text-muted">结果不明、已停止重试或已跳过的数据在任何方式下都不会被自动领取。</span>
    </label> : null}
    {dataBatch ? <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">每行最多尝试</span>
      <Input className="max-w-64" inputMode="numeric" aria-label="每行最多尝试次数" value={budgetDraft} disabled={disabled} aria-invalid={Boolean(budgetError)} onChange={event => {
        const draft = event.target.value, parsed = Number(draft)
        setBudgetDraft(draft)
        if (draft.trim() && Number.isInteger(parsed) && parsed >= 1 && parsed <= 20) onChange({ ...value, retryBudget: parsed })
      }}/>
      {budgetError ? <span role="alert" className="text-xs text-danger">{budgetError}</span> : <span className="text-xs text-muted">含第一次；页面类失败按 1、5、30 分钟间隔重试，用完后停止重试</span>}
    </label> : null}
    {dataBatch ? <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">失败处理</span><span className="flex items-center gap-3">
      <Switch aria-label="失败过多时自动暂停批次" checked={value.failurePolicy === 'thresholds'} disabled={disabled} onCheckedChange={on => onChange(on ? { ...value, failurePolicy: 'thresholds' } : { ...value, failurePolicy: null })}/>
      失败过多时自动暂停批次</span>
      <span className="text-xs text-muted">{value.failurePolicy === 'thresholds' ? '单条失败不影响其他数据；最近 20 个任务过半页面失败、连续 5 个启动失败或连续 10 个相同原因失败时暂停，修复后可继续。' : '关闭时沿用下面的旧规则。'}</span>
    </label> : null}
    {!dataBatch || value.failurePolicy !== 'thresholds' ? <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-center"><span className="font-medium">{dataBatch ? '' : '失败处理'}</span><span className="flex items-center gap-3">
      <Switch aria-label="任务失败后继续下一个任务" checked={value.continueAfterFailure} disabled={disabled} onCheckedChange={continueAfterFailure => onChange({ ...value, continueAfterFailure })}/>
      任务失败后继续下一个任务</span>
    </label> : null}
    <label className="grid gap-2 text-sm md:grid-cols-[11rem_minmax(0,1fr)] md:items-start [&>:not(:first-child)]:md:col-start-2"><span className="pt-2 font-medium">浏览器会话</span><span className="flex items-center gap-3">
      <Switch aria-label="任务之间复用浏览器" checked={value.sessionMode === 'pool'} disabled={disabled || (!freshBrowser && value.sessionMode !== 'pool')} onCheckedChange={on => onChange({ ...value, sessionMode: on ? 'pool' : 'perTask' })}/>
      任务之间复用浏览器</span>
      {errors.sessionMode ? <span role="alert" className="text-xs text-danger">{errors.sessionMode}</span> : <span className="text-xs text-muted">{freshBrowser ? '适合不需要登录的采集：浏览器只启动一次，每个任务仍使用全新的隔离页面，互不共享 Cookie 和缓存。流程会保存环境或需要人工处理时不能开启。' : '使用已保存的登录环境时，每个任务都要用自己的浏览器。'}</span>}
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
    </div>
    <aside className="overflow-hidden rounded-control border border-line bg-surface text-sm" aria-label="本次运行策略">
      <h4 className="m-0 bg-surface-subtle px-5 py-4 text-base font-semibold">本次运行策略</h4>
      <ul className="m-0 grid list-none px-5 py-2"><li className="flex items-center gap-3 border-b border-line py-3"><Database size={21} aria-hidden/>最多 {value.maxTasks ?? '—'} 个任务</li><li className="flex items-center gap-3 border-b border-line py-3"><SlidersHorizontal size={21} aria-hidden/>{`配置并发上限 ${Math.min(value.concurrency, value.maxLiveInstances)}`}</li><li className="flex items-center gap-3 border-b border-line py-3"><Clock size={21} aria-hidden/>单任务最长 {value.automaticExecutionTimeoutSeconds / 60} 分钟</li><li className="flex items-center gap-3 py-3"><Cube size={21} aria-hidden/>每个任务使用独立临时环境</li></ul>
      <p className="m-0 border-t border-line px-5 py-3 text-xs text-muted">实际并发还受本次请求和执行容量限制</p>
    </aside>
  </section>
}
