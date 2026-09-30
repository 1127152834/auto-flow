import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Clock, Monitor, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { Select } from '../../../shared/components/ui/select'
import { TableStatus } from '../../../shared/components/ui/table-status'
import { Textarea } from '../../../shared/components/ui/textarea'
import { createEnvironmentApi } from '../../environments/api'
import { safeProjectError } from '../../projects/presentation-error'
import type { ProjectRoute } from '../../projects/types'
import { createProjectRunsApi } from '../api'
import { ManualResumeFields, parseManualInputs } from '../components/ManualResumeFields'
import { DataCommandNotAccepted } from '../../project-data/data-command'
import { presentRunFailure } from '../presentation'

export type ManualDetailPageProps = { workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean; onNavigate(route: ProjectRoute): void; manualItemId: string }
const statuses: Record<string, string> = { waiting: '等待人工', resume_requested: '已请求继续', resolved: '已处理', expired: '已超时', lost: '已丢失', cancelled: '已取消' }
const taskStatuses: Record<string, string> = { queued: '排队中', running: '运行中', waiting_manual: '等待人工', resume_queued: '等待恢复', finishing: '正在结束', stopping: '正在停止', reconciling: '正在核对', succeeded: '成功', failed: '失败', cancelled: '已取消', timed_out: '已超时', interrupted: '已中断' }
const instanceStates: Record<string, string> = { active: '运行中', waiting_manual: '等待人工', retained_unsaved: '保留（未保存）', closed: '已关闭', cleaned: '已清理' }
const short = (value: string) => value.slice(0, 8)
const stamp = (value: string | null | undefined) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
const remaining = (expiresAt: string | null | undefined) => {
  if (!expiresAt) return null
  const minutes = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 60_000)
  return Number.isNaN(minutes) ? null : minutes
}
/** Checkpoint targets arrive from the core as node identifiers or objects; anything else stays visible but unusable. */
const targetOption = (entry: unknown, index: number) => {
  if (typeof entry === 'string' && entry) return { value: entry, label: entry }
  if (entry && typeof entry === 'object') {
    const record = entry as Record<string, unknown>
    const value = [record.nodeId, record.targetNodeId, record.id].find(candidate => typeof candidate === 'string' && candidate) as string | undefined
    if (value) return { value, label: typeof record.title === 'string' ? record.title : typeof record.name === 'string' ? record.name : value }
  }
  return { value: `unusable-target-${index}`, label: `目标节点 ${index + 1}（资料不完整）`, disabled: true }
}

export function ManualDetailPage({ workspaceKey, instanceId, projectId, client, disabled, readOnly, onNavigate, manualItemId }: ManualDetailPageProps) {
  const queryClient = useQueryClient()
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const runs = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId])
  const prefix = [workspaceKey, instanceId, 'manual-item', projectId, manualItemId]
  const item = useQuery({
    queryKey: [...prefix, 'detail'],
    queryFn: ({ signal }) => api.getManual(manualItemId, signal),
    enabled: !disabled,
    refetchInterval: query => {
      const data = query.state.data as { status?: string } | undefined
      return data && !['waiting', 'resume_requested'].includes(data.status ?? '') ? false : 3000
    },
  })
  const live = item.data
  const instance = useQuery({ queryKey: [...prefix, 'instance', live?.instanceId], queryFn: ({ signal }) => api.getInstance(live!.instanceId!, signal), enabled: !disabled && Boolean(live?.instanceId) })
  const environment = useQuery({ queryKey: [...prefix, 'environment', instance.data?.environmentId], queryFn: ({ signal }) => api.get(instance.data!.environmentId!, signal), enabled: !disabled && Boolean(instance.data?.environmentId) })
  const task = useQuery({ queryKey: [...prefix, 'task', live?.taskId], queryFn: ({ signal }) => runs.getTask(live!.taskId, signal), enabled: !disabled && Boolean(live?.taskId) })
  const targets = Array.isArray(live?.allowedTargets) ? live.allowedTargets.map(targetOption) : []
  const [decision, setDecision] = useState<string | null>(null), [target, setTarget] = useState<string | null>(null), [reason, setReason] = useState('')
  const [inputDraft, setInputDraft] = useState<Record<string, string>>({})
  const pendingResume = useRef<{ key: string; body: { checkpointRevision: number; expectedStatusRevision: number; targetNodeId?: string; inputs?: Record<string, unknown> } } | null>(null)
  const [now, setNow] = useState(Date.now)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  const parsedInputs = parseManualInputs(live?.inputSchema ?? [], inputDraft)
  const [confirming, setConfirming] = useState(false), [agreed, setAgreed] = useState(false), [failure, setFailure] = useState<string>()
  const decisionName = useId()
  const firstTarget = targets.find(option => !option.disabled)?.value ?? null
  useEffect(() => { if (target === null && firstTarget) setTarget(firstTarget) }, [firstTarget, target])
  const terminal = live ? !['waiting', 'resume_requested'].includes(live.status) : false
  const expired = Boolean(live?.expiresAt && new Date(live.expiresAt).getTime() <= now)
  const locked = disabled || readOnly || !live || terminal || expired || live.status !== 'waiting'
  const chosen = decision ?? ''
  // 「标记完成」的知情勾选在确认弹窗内完成，此处不能再次要求 agreed，否则提交按钮永远不可用。
  const canSubmit = !locked && (chosen === 'continue' ? !parsedInputs.error && (Boolean(target) || Boolean(live?.canResume) && targets.length === 0) : chosen === 'fail' ? reason.trim().length > 0 : chosen === 'complete')
  const backToList = () => onNavigate({ projectId, tab: 'runs', runView: 'manual' })
  const openEnvironment = useMutation({
    mutationFn: () => api.openInstance(instance.data!.instanceId, instance.data!.instanceUseGeneration, crypto.randomUUID()),
    onSuccess: () => { notify({ title: '已请求进入当前浏览器', tone: 'success' }); void queryClient.invalidateQueries({ queryKey: prefix }) },
    onError: error => { setFailure(presentRunFailure(error, '无法进入当前浏览器')); notify({ title: safeProjectError(error), tone: 'error' }) },
  })
  const resume = useMutation({
    mutationFn: async () => {
      if (pendingResume.current) {
        try { return { operation: await api.lookupManualResume(pendingResume.current.key) } }
        catch (error) { if (!(error instanceof DataCommandNotAccepted) || locked) throw error }
      } else {
        pendingResume.current = { key: crypto.randomUUID(), body: { checkpointRevision: live!.checkpointRevision, expectedStatusRevision: live!.statusRevision, inputs: parsedInputs.values, ...(target ? { targetNodeId: target } : {}) } }
      }
      const command = pendingResume.current
      return api.resumeManual(manualItemId, command.body, command.key)
    },
    onSuccess: result => {
      pendingResume.current = null
      if (result.operation.status === 'failed') { setFailure('原继续请求未完成，请刷新检查点后处理。'); void queryClient.invalidateQueries({ queryKey: prefix }); return }
      notify({ title: '已请求继续原任务', tone: 'success' }); void queryClient.invalidateQueries({ queryKey: prefix }); backToList()
    },
    onError: error => {
      if (error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408) pendingResume.current = null
      setFailure(presentRunFailure(error, '提交处理结果失败'))
    },
  })
  const finish = useMutation({
    mutationFn: (outcome: 'succeeded' | 'failed') => api.finishManual(manualItemId, { expectedCheckpointRevision: live!.checkpointRevision, expectedStatusRevision: live!.statusRevision, outcome, reason: reason.trim() || (outcome === 'succeeded' ? '用户在管理页面标记完成' : '用户在管理页面标记失败'), retainEnvironment: { enabled: false } }, crypto.randomUUID()),
    onSuccess: (_result, outcome) => {
      notify({ title: outcome === 'succeeded' ? '人工事项已标记完成' : '人工事项已标记失败', tone: 'success' })
      void queryClient.invalidateQueries({ queryKey: prefix })
      setConfirming(false)
      backToList()
    },
    onError: error => { setFailure(presentRunFailure(error, '提交处理结果失败')); setConfirming(false) },
  })
  if (!live) return <section className="grid gap-3 rounded-control border border-line bg-surface p-5" role={item.error || disabled ? 'alert' : 'status'}>
    <p className="m-0">{item.error ? `无法读取等待人工事项：${presentRunFailure(item.error)}` : disabled ? '本地服务暂不可用，请等待连接恢复。' : '正在读取等待人工事项…'}</p>
    {item.error ? <Button size="sm" onClick={() => void item.refetch()}>重试读取</Button> : null}
  </section>
  const left = remaining(live.expiresAt)
  const parameters = Object.entries(task.data?.inputSnapshot.parameters ?? {})
  const choices = [
    { value: 'continue', label: '继续工作流', description: '从所选节点继续当前任务。', disabled: targets.length === 0 && !live.canResume },
    { value: 'complete', label: '标记完成', description: '本任务已处理完毕；完成不等于资料已保存，也不会自动写入业务数据。', disabled: false },
    { value: 'fail', label: '标记失败', description: '本任务无法继续，标记为失败。', disabled: false },
  ]
  return <section className="grid min-w-0 gap-4">
    <div className="flex flex-wrap items-center gap-3"><Button variant="ghost" size="sm" onClick={backToList}><ArrowLeft aria-hidden/>返回等待人工</Button><nav aria-label="面包屑" className="text-sm text-muted">运行记录 / 等待人工 / 事项 {short(live.manualItemId)}</nav></div>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="m-0 flex flex-wrap items-center gap-3 text-2xl font-semibold"><span className="min-w-0 break-words">{live.reason || '运行记录请求人工确认'}</span><TableStatus tone={terminal ? 'neutral' : 'warning'}>{statuses[live.status] ?? live.status}</TableStatus></h1>
        <p className="mb-0 mt-2 text-sm text-muted">{task.data?.automationName ?? '自动化'} · 批次 {short(live.runId)} · 任务 {short(live.taskId)}</p>
      </div>
      <div className="text-right"><p className="m-0 flex items-center justify-end gap-2 text-lg font-medium"><Clock aria-hidden/>{left === null ? '没有保留截止时间' : left <= 0 ? '已超过保留时间' : `剩余 ${left} 分钟`}</p><p className="m-0 text-sm text-muted">{live.expiresAt ? `${stamp(live.expiresAt)} 到期` : '保留时间未设置'} · 进入等待 {stamp(live.createdAt)}</p></div>
    </header>
    {failure ? <div role="alert" className="flex items-center justify-between rounded-control border border-warning/30 bg-warning/10 p-3"><span>{failure}</span><Button size="sm" onClick={() => setFailure(undefined)}>关闭提示</Button></div> : null}
    {resume.isError && pendingResume.current ? <div role="status" className="flex items-center justify-between gap-3 rounded-control border border-line p-3"><span>上次继续请求尚待核对。输入已保留，不会重复提交新命令。</span><Button disabled={resume.isPending} onClick={() => resume.mutate()}>核对继续请求</Button></div> : null}
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-5" aria-label={terminal ? '历史现场' : '当前现场'}>
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="m-0 text-lg font-semibold">{terminal ? '历史现场' : '当前现场'}</h2><p className="mb-0 mt-1 text-sm text-muted">{terminal ? '以下为本次任务留下的历史输入与现场事实，仅用于核对。' : '以下为本次任务的输入与现场事实，用于核对内容。'}</p></div>{!terminal && live.instanceId ? <Button size="sm" variant="secondary" disabled={disabled || readOnly || openEnvironment.isPending || !instance.data} loading={openEnvironment.isPending} onClick={() => openEnvironment.mutate()}><Monitor aria-hidden/>打开环境</Button> : <span className="text-sm text-muted">{terminal ? '现场已结束' : '未接入环境'}</span>}</header>
        <div className="rounded-control border border-line bg-subtle p-3 text-sm text-muted"><p className="m-0 flex items-start gap-2"><WarningCircle aria-hidden className="mt-0.5 shrink-0"/>{terminal ? '历史证据可查看；现场不再用于继续执行。' : '本阶段不提供运行中的现场截图。请用「打开环境」查看浏览器当前真实状态，本页只记录任务快照事实。'}</p><p className="m-0 mt-2">{live.instanceId ? `现场实例 ${short(live.instanceId)} · ${instanceStates[instance.data?.state ?? ''] ?? instance.data?.state ?? '读取中'}` : '本检查点没有保留的浏览器现场。'}</p></div>
        <dl className="m-0 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[8rem_minmax(0,1fr)]">
          <dt className="text-muted">自动化</dt><dd className="m-0 break-words">{task.data?.automationName ?? '自动化'}</dd>
          <dt className="text-muted">批次</dt><dd className="m-0">{short(live.runId)}</dd>
          <dt className="text-muted">任务</dt><dd className="m-0">{short(live.taskId)}</dd>
          <dt className="text-muted">等待原因</dt><dd className="m-0 break-words">{live.reason || '运行记录请求人工确认'}</dd>
          <dt className="text-muted">执行环境</dt><dd className="m-0 break-words">{environment.data ? environment.data.environment.name : instance.data ? '临时现场（未保存）' : '—'}</dd>
          {parameters.length ? <><dt className="text-muted">输入参数</dt><dd className="m-0 break-words">{parameters.map(([key, value]) => `${key}=${String(value)}`).join(' · ')}</dd></> : null}
          <dt className="text-muted">检查点</dt><dd className="m-0">修订 {live.checkpointRevision}</dd>
        </dl>
      </section>
      <section className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-5" aria-label={terminal ? '处理结果' : '处理方式'}>
        {terminal ? <>
          <div><h2 className="m-0 text-lg font-semibold">处理结果</h2><p className="mb-0 mt-1 text-sm text-muted">{live.status === 'expired' ? '保留时间已到，不能再提交人工处理。' : '该人工事项已结束，不能再提交人工处理。'}</p></div>
          <dl className="m-0 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[7rem_minmax(0,1fr)]">
            <dt className="text-muted">事项状态</dt><dd className="m-0 break-words">{statuses[live.status] ?? live.status}</dd>
            <dt className="text-muted">任务状态</dt><dd className="m-0">{task.data ? taskStatuses[task.data.task.status] ?? task.data.task.status : '读取中'}</dd>
            <dt className="text-muted">到期时间</dt><dd className="m-0">{live.expiresAt ? stamp(live.expiresAt) : '未设置'}</dd>
            <dt className="text-muted">继续请求</dt><dd className="m-0">{live.resumeStarted ? '已发出' : '未发出'}</dd>
            <dt className="text-muted">现场</dt><dd className="m-0 break-words">{instance.data ? instanceStates[instance.data.state] ?? instance.data.state : '—'}</dd>
          </dl>
          <p className="m-0 text-xs text-muted">管理侧只登记已确认的事实，不根据倒计时推断环境与占用的清理结果。</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => onNavigate({ projectId, tab: 'runs', taskId: live.taskId, taskTab: 'logs' })}>查看任务日志</Button>
            <Button size="sm" variant="secondary" loading={item.isFetching} onClick={() => void item.refetch()}>刷新状态</Button>
          </div>
        </> : <>
        <div><h2 className="m-0 text-lg font-semibold">处理方式</h2><p className="mb-0 mt-1 text-sm text-muted">请选择此任务接下来的去向。</p></div>
        <fieldset disabled={locked} className="m-0 grid min-w-0 gap-2 border-0 p-0">
          <legend className="sr-only">处理方式</legend>
          {choices.map(choice => <label key={choice.value} className={`grid grid-cols-[auto_minmax(0,1fr)] items-start gap-3 rounded-control border p-3 text-sm ${chosen === choice.value ? 'border-clay bg-surface' : 'border-line'} ${locked || choice.disabled ? 'text-muted' : ''}`}>
            <input type="radio" name={decisionName} value={choice.value} className="m-0 mt-0.5 h-[18px] w-[18px] shrink-0 appearance-none rounded-full border border-control-border bg-surface checked:border-[5px] checked:border-clay disabled:cursor-not-allowed disabled:opacity-50" checked={chosen === choice.value} disabled={locked || choice.disabled} onChange={() => { setDecision(choice.value); setFailure(undefined) }}/>
            <span className="min-w-0"><strong className="block">{choice.label}</strong><small className="block text-muted">{choice.description}</small></span>
          </label>)}
        </fieldset>
        {targets.length === 0 && !live.canResume ? <p className="m-0 text-xs text-muted">当前检查点没有管理页面可继续的目标节点（执行核心尚未接入）；继续工作流保持禁用，标记完成与标记失败可用。</p> : null}
        {chosen === 'continue' && targets.length > 0 ? <label className="grid gap-2 text-sm"><span>继续节点<abbr title="必填" className="ml-1 no-underline">*</abbr></span><Select aria-label="继续节点" clearable={false} placeholder="请选择继续节点" value={target} options={targets} disabled={locked || resume.isPending || Boolean(pendingResume.current)} onValueChange={setTarget}/><small className="text-muted">校验本次任务快照中的节点与上下文。</small></label> : null}
        {chosen === 'continue' ? <ManualResumeFields fields={live.inputSchema ?? []} draft={inputDraft} onChange={setInputDraft} disabled={locked || resume.isPending || Boolean(pendingResume.current)}/> : null}
        {chosen === 'fail' ? <label className="grid gap-2 text-sm"><span>失败说明<abbr title="必填" className="ml-1 no-underline">*</abbr></span><Textarea aria-label="失败说明" value={reason} maxLength={500} disabled={locked} placeholder="说明无法继续的原因，会写入原任务记录" onChange={event => setReason(event.target.value)}/></label> : null}
        <Button disabled={!canSubmit || finish.isPending || resume.isPending || Boolean(pendingResume.current)} loading={finish.isPending || resume.isPending} onClick={() => { setFailure(undefined); if (chosen === 'complete') { setConfirming(true); return } if (chosen === 'continue') resume.mutate(); else if (chosen === 'fail') finish.mutate('failed') }}>提交处理结果</Button>
        <p className="m-0 text-xs text-muted">处理结果写入原任务记录；不会创建新任务。{readOnly ? '项目处于归档状态，只能查看。' : ''}</p>
        </>}
      </section>
    </div>
    <Dialog open={confirming} onOpenChange={value => { if (!finish.isPending) { setConfirming(value); if (!value) setAgreed(false) } }}>
      <DialogContent>
        <DialogTitle>将这条任务标记完成？</DialogTitle>
        <DialogDescription>人工事项 {short(live.manualItemId)} · 任务 {short(live.taskId)}</DialogDescription>
        <div className="grid gap-3 text-sm">
          <p className="m-0">确认后将结束当前任务，不再执行后续节点。</p>
          <p className="m-0 flex items-start gap-2 rounded-control border border-warning/30 bg-warning/10 p-3"><WarningCircle aria-hidden className="mt-0.5 shrink-0"/>标记完成不等于资料已保存，也不会自动写入业务数据。</p>
          <p className="m-0 text-muted">处理结果写回原任务，不创建新任务。</p>
          <label className="grid gap-2"><span>处理说明（选填）</span><Textarea aria-label="处理说明" value={reason} maxLength={500} disabled={finish.isPending} placeholder="例如：已人工核对，后续由我维护资料。" onChange={event => setReason(event.target.value)}/></label>
          <label className="flex items-center gap-2"><Checkbox aria-label="我已了解，本次处理不会继续工作流" checked={agreed} disabled={finish.isPending} onCheckedChange={value => setAgreed(value === true)}/><span>我已了解，本次处理不会继续工作流</span></label>
          {failure ? <p role="alert" className="m-0 text-danger">{failure}</p> : null}
          <div className="flex justify-end gap-2"><Button variant="ghost" disabled={finish.isPending} onClick={() => { setConfirming(false); setAgreed(false) }}>取消</Button><Button loading={finish.isPending} disabled={!agreed || finish.isPending} onClick={() => finish.mutate('succeeded')}>确认标记完成</Button></div>
        </div>
      </DialogContent>
    </Dialog>
  </section>
}
