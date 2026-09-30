import type { components } from '../../../shared/api/generated'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import { safeProjectError } from '../../projects/presentation-error'
import { DataCommandNotAccepted } from '../../project-data/data-command'
import { createOperationCommand } from '../../project-data/operation-command'
import { createProjectRunsApi } from '../../project-runs/api'
import { createEnvironmentApi, type EnvironmentOperation } from '../api'
import { bindableRecords, selectedTargets } from '../record-targets'

export function TaskEndPanel({ workspaceKey, instanceId, projectId, taskId, runId, executionGeneration, statusRevision = 0, inputs = [], client, disabled, environmentCleaned = false, durableEnd }: {
  durableEnd?: components['schemas']['TaskEndView'] | null
  workspaceKey: string
  instanceId: string
  projectId: string
  taskId: string
  runId: string
  executionGeneration: number
  statusRevision?: number
  inputs?: unknown[]
  client: StreamingApiClient
  disabled: boolean
  environmentCleaned?: boolean
}) {
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const connectionKey = useMemo(() => crypto.randomUUID(), [client, workspaceKey, instanceId, projectId, taskId])
  const instance = useQuery({
    queryKey: [workspaceKey, instanceId, 'environments', projectId, 'task-instance', taskId, statusRevision],
    queryFn: ({ signal }) => api.listInstances({ page: 1, pageSize: 5, taskId }, signal).then(page => page.items[0] ?? null),
    enabled: !disabled && !durableEnd,
  })
  const persistedEnd = useQuery({
    queryKey: [workspaceKey, instanceId, 'environments', projectId, 'task-end', taskId, statusRevision],
    queryFn: ({ signal }) => api.taskEnd(taskId, signal),
    enabled: !disabled && !durableEnd,
  })
  const records = useMemo(() => bindableRecords(inputs), [inputs])
  const [retain, setRetain] = useState(true)
  const [name, setName] = useState('登录环境')
  const [notes, setNotes] = useState('')
  const [selected, setSelected] = useState<Set<string>>(() => new Set(records.map(item => item.key)))
  const [replaceAllowed, setReplaceAllowed] = useState(false)
  const [repairReplaceAllowed, setRepairReplaceAllowed] = useState(false)
  const [excludedRepairTargets, setExcludedRepairTargets] = useState<Set<string>>(() => new Set())
  const [repairVersions, setRepairVersions] = useState<Map<string, number>>(() => new Map())
  const current = instance.data
  const targets = selectedTargets(records, selected, replaceAllowed)
  const end = useMutation({
    mutationFn: () => {
      if (!current) throw new Error('当前任务还没有环境实例')
      return api.end(taskId, {
        taskId,
        runId,
        instanceId: current.instanceId,
        expectedUseGeneration: current.instanceUseGeneration,
        executionGeneration,
        retainEnvironment: retain
          ? { enabled: true, mode: current.environmentId ? 'update' : 'saveAs', name, notes, expectedContentGeneration: current.sourceContentGeneration ?? undefined, recordTargets: targets }
          : { enabled: false },
      }, crypto.randomUUID())
    },
    onSuccess: async result => {
      await Promise.all([instance.refetch(), persistedEnd.refetch()])
      const phase = result.outcome && 'phase' in result.outcome ? String(result.outcome.phase) : 'completed'
      notify({
        title: phase === 'saved_unlinked' ? '环境已保存，关联未完成' : phase === 'completed' ? (retain ? '已保留登录环境' : '已结束并关闭环境') : '结束结果已记录',
        tone: phase === 'saved_unlinked' ? 'error' : 'success',
      })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  const endOutcome = persistedEnd.data?.outcome ?? end.data?.outcome
  const repair = useMutation<EnvironmentOperation>({
    mutationFn: () => {
      const operationId = persistedEnd.data?.saveOperationId
      if (!operationId) throw new Error('没有可修复的结束操作')
      return api.repair(operationId, {
        recordTargets: repairTargets,
      }, crypto.randomUUID())
    },
    onSuccess: async result => {
      const conflicts = Array.isArray(result.outcome?.conflicts) ? result.outcome.conflicts as Array<Record<string, unknown>> : []
      setRepairVersions(previous => new Map([...previous, ...bindableRecords(conflicts.map(conflict => ({ recordRef: conflict.record, linkRevision: conflict.currentLinkRevision }))).map(item => [item.key, item.expectedLinkRevision] as const)]))
      await Promise.all([instance.refetch(), persistedEnd.refetch()])
      const phase = result.outcome && 'phase' in result.outcome ? String(result.outcome.phase) : 'completed'
      notify({ title: phase === 'completed' ? '已按原操作修复关联' : '修复未完成，请核对当前关联事实', tone: phase === 'completed' ? 'success' : 'error' })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  if (durableEnd) return <DurableEndResult key={`${connectionKey}:${durableEnd.operationId}`} durableEnd={durableEnd} client={client} projectId={projectId} taskId={taskId} workspaceKey={workspaceKey} instanceId={instanceId} disabled={disabled} />
  const conflicts = Array.isArray(endOutcome?.conflicts) ? endOutcome.conflicts as Array<Record<string, unknown>> : []
  const conflictVersions = new Map([...bindableRecords(conflicts.map(conflict => ({ recordRef: conflict.record, linkRevision: conflict.currentLinkRevision }))).map(item => [item.key, item.expectedLinkRevision] as const), ...repairVersions])
  const repairRecords = bindableRecords((persistedEnd.data?.recordTargets ?? []).map((target, index) => ({ recordRef: target.recordRef, linkRevision: target.expectedLinkRevision, alias: `原目标 ${index + 1}` }))).map(item => ({ ...item, expectedLinkRevision: conflictVersions.get(item.key) ?? item.expectedLinkRevision }))
  const repairTargets = selectedTargets(repairRecords, new Set(repairRecords.filter(item => !excludedRepairTargets.has(item.key)).map(item => item.key)), repairReplaceAllowed)
  if (instance.isLoading || persistedEnd.isLoading) return <section role="status" className="rounded-control border border-line bg-surface p-4 text-sm">正在读取任务环境…</section>
  if (persistedEnd.isError) return <p role="alert">保留结果读取失败，请重新打开任务后重试。</p>
  if (!current) return <section className="rounded-control border border-line bg-surface p-4 text-sm text-muted">当前任务还没有可保留的环境实例。</section>
  const phase = persistedEnd.data?.associationPhase ?? (endOutcome && 'phase' in endOutcome ? String(endOutcome.phase) : null)
  const repairControls = phase === 'saved_unlinked' ? <fieldset className="grid gap-2">
    <legend>核对本次修复的原关联目标</legend>
    {repairRecords.map(item => <label key={item.key} className="flex items-center gap-2">
      <Checkbox checked={!excludedRepairTargets.has(item.key)} disabled={disabled || repair.isPending} onCheckedChange={checked => setExcludedRepairTargets(previous => {
        const next = new Set(previous)
        if (checked === true) next.delete(item.key)
        else next.add(item.key)
        return next
      })} />
      <span>{item.alias} · {String((item.recordRef.recordKey as Record<string, unknown> | undefined)?.value ?? item.recordRef.tableId)} · 关联版本 {item.expectedLinkRevision}</span>
    </label>)}
    <label className="flex items-center gap-2"><Checkbox checked={repairReplaceAllowed} disabled={disabled || repair.isPending} onCheckedChange={checked => setRepairReplaceAllowed(checked === true)} /><span>允许本次修复替换所选记录的现有关联</span></label>
    <Button size="sm" variant="secondary" disabled={disabled || repair.isPending || !persistedEnd.data?.saveOperationId || !repairTargets.length} onClick={() => repair.mutate()}>修复关联</Button>
  </fieldset> : null
  if (environmentCleaned || current.state === 'cleaned' || phase === 'saved_unlinked' || phase === 'completed') return <section className="grid gap-3 rounded-control border border-line bg-surface p-4 text-sm" aria-label="环境结束结果">
    <p role="status" className="m-0">{environmentCleaned || current.state === 'cleaned' ? '本次浏览器工作副本已清理，不能再次保存本次会话。' : '本次保留结果已记录，不能再次保存本次会话。'}</p>
    {phase === 'completed' && endOutcome?.phase === 'saved_unlinked' ? <p role="status" className="m-0">已修复记录关联，原任务的失败结果保持不变。</p> : null}
    {phase === 'saved_unlinked' ? <>
      <p role="alert" className="m-0 text-warning">环境已保存，记录关联未完成。可用原操作修复，不会重跑网页。</p>
      {repairControls}
    </> : null}
  </section>
  const toggle = (key: string, checked: boolean) => {
    setSelected(currentSelected => {
      const next = new Set(currentSelected)
      if (checked) next.add(key)
      else next.delete(key)
      return next
    })
  }
  return <section className="grid gap-3 rounded-control border border-line bg-surface p-4" aria-label="结束并保留环境">
    <h3 className="m-0 text-base">结束任务</h3>
    <p className="m-0 text-sm text-muted">保留环境会保存当前登录上下文。关联账号只使用本任务已声明的记录目标；保存成功但关联失败会显示部分结果，不会假装已完成。</p>
    <label className="flex items-center gap-2 text-sm"><Checkbox checked={retain} onCheckedChange={value => setRetain(value === true)} disabled={disabled || end.isPending} /><span>保留当前登录环境</span></label>
    {retain ? <div className="grid gap-2 md:grid-cols-2">
      <label className="grid gap-1 text-sm"><span>环境名称</span><Input value={name} maxLength={36} onChange={event => setName(event.target.value)} aria-label="保留环境名称" /></label>
      <label className="grid gap-1 text-sm"><span>备注</span><Input value={notes} maxLength={120} onChange={event => setNotes(event.target.value)} aria-label="保留环境备注" /></label>
    </div> : null}
    {retain && records.length ? <fieldset className="grid gap-2">
      <legend className="text-sm">关联账号</legend>
      {records.map(item => <label key={item.key} className="flex items-center gap-2 text-sm">
        <Checkbox checked={selected.has(item.key)} onCheckedChange={value => toggle(item.key, value === true)} disabled={disabled || end.isPending} />
        <span>{item.alias}{item.currentEnvironmentId ? ' · 已有其他环境关联' : ''}</span>
      </label>)}
      <label className="flex items-center gap-2 text-sm"><Checkbox checked={replaceAllowed} onCheckedChange={value => setReplaceAllowed(value === true)} disabled={disabled || end.isPending} /><span>允许替换已有关联</span></label>
    </fieldset> : retain ? <p className="m-0 text-sm text-muted">当前任务没有可关联的记录目标，可以只保存环境。</p> : null}
    <div className="flex flex-wrap gap-2">
      <Button size="sm" disabled={disabled || end.isPending} onClick={() => end.mutate()}>{retain ? '结束并保留' : '结束并关闭'}</Button>
    </div>
    {repairControls}
    {phase === 'saved_unlinked' ? <p role="alert" className="m-0 text-sm text-warning">环境已保存，记录关联未完成。可用原操作修复，不会重跑网页。</p> : null}
    {phase === 'completed' ? <p role="status" className="m-0 text-sm">结束事实已写入。原浏览器工作副本随后关闭。</p> : null}
  </section>
}


function DurableEndResult({ durableEnd, client, projectId, taskId, workspaceKey, instanceId, disabled }: {
  durableEnd: components['schemas']['TaskEndView']
  client: StreamingApiClient
  projectId: string
  taskId: string
  workspaceKey: string
  instanceId: string
  disabled: boolean
}) {
  const cache = useQueryClient()
  const operations = useMemo(() => createOperationCommand(client, projectId), [client, projectId])
  const runs = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId])
  // Like the existing durable operation dialogs, keep only recovery identity
  // in workspace-scoped storage. Instance changes revoke UI authority, not keys.
  const storageKey = `autoflow:end-repair:${JSON.stringify([workspaceKey, projectId, taskId, durableEnd.operationId])}`
  const [stored] = useState(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return { key: null, error: null }
      const value: unknown = JSON.parse(raw)
      if (!value || typeof value !== 'object' || !('key' in value) || typeof value.key !== 'string' || !value.key) throw new Error('关联修复恢复记录损坏，请核验原操作')
      return { key: value.key, error: null }
    } catch (cause) { return { key: null, error: safeProjectError(cause) } }
  })
  const [pending, setPending] = useState<string | null>(stored.key)
  const [error, setError] = useState<string | null>(stored.error)
  const [preview, setPreview] = useState<components['schemas']['TaskEndView'] | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [working, setWorking] = useState(false)
  const active = useRef(false), lock = useRef(false), pendingKey = useRef(stored.key)
  useLayoutEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const current = () => active.current
  const visible = preview ?? durableEnd
  const targets = preview?.repairTargets ?? []
  const repairable = Boolean(preview?.saveOperationId && preview.associationPhase === 'saved_unlinked' && targets.length && targets.every(target => target.exists && typeof target.currentLinkRevision === 'number'))
  const readCurrent = async () => {
    const detail = await runs.getTask(taskId)
    if (current()) setPreview(detail.end ?? null)
  }
  const refresh = async () => {
    if (disabled || !current() || lock.current || pendingKey.current || stored.error) return
    lock.current = true; setWorking(true); setConfirmed(false); setPreview(null); setError(null)
    try { await readCurrent() } catch (cause) { if (current()) setError(safeProjectError(cause)) }
    finally { if (current()) { lock.current = false; setWorking(false) } }
  }
  const clearPending = () => {
    localStorage.removeItem(storageKey)
    pendingKey.current = null; setPending(null); setPreview(null)
  }
  const repair = async (lookupOnly: boolean) => {
    if (disabled || !current() || lock.current || stored.error || (lookupOnly && !pendingKey.current) || (!lookupOnly && (pendingKey.current || !confirmed || !repairable))) return
    const key = pendingKey.current ?? crypto.randomUUID()
    lock.current = true; setWorking(true); setConfirmed(false); setError(null)
    try {
      if (!lookupOnly) {
        // Persist before sending: failure to retain the key prevents the write.
        localStorage.setItem(storageKey, JSON.stringify({ key }))
        pendingKey.current = key; setPending(key)
      }
      const operation = lookupOnly
        ? await operations.lookup(key, 'repairEndAssociation', current)
        : await operations.submit(`/api/v1/projects/${encodeURIComponent(projectId)}/environment-operations/${encodeURIComponent(preview!.saveOperationId!)}/repair`, {
          recordTargets: targets.map(target => ({ recordRef: target.recordRef, expectedLinkRevision: target.currentLinkRevision!, replaceAllowed: true })),
        }, key, 'repairEndAssociation', current)
      if (!current()) return
      if (operation.status === 'succeeded' || operation.status === 'failed') {
        clearPending()
        if (operation.status === 'failed') setError(safeProjectError(operation.error))
        await readCurrent()
        if (current()) await cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'project-runs', projectId, 'task', taskId] })
      }
    } catch (cause) {
      if (!current()) return
      const notAccepted = cause instanceof DataCommandNotAccepted || (!lookupOnly && cause instanceof ApiClientError && cause.status >= 400 && cause.status < 500 && cause.status !== 408)
      if (notAccepted) {
        try { clearPending() } catch (storageError) { setError(safeProjectError(storageError)); return }
      }
      setError(pendingKey.current ? '关联修复结果尚未确认，请核对原操作。' : safeProjectError(cause))
    } finally { if (current()) { lock.current = false; setWorking(false) } }
  }
  const busy = disabled || working || Boolean(stored.error)
  return <section className="grid gap-2 rounded-control border border-line bg-surface p-4" aria-label="项目结束结果">
    <h3 className="m-0 text-base">{visible.phase === 'saved_unlinked' ? (visible.associationPhase === 'completed' ? '上下文已保存，关联已修复' : '上下文已保存，关联未完成') : visible.phase === 'completed' ? 'End 已完成' : visible.phase === 'failed' ? 'End 失败' : '正在保留 · 结果待核验'}</h3>
    <p className="m-0 text-sm">原定业务结果：{visible.businessResult === 'succeeded' ? '成功' : visible.businessResult === 'failed' ? '失败' : '未记录'}</p>
    {visible.outcome ? <pre className="m-0 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(visible.outcome, null, 2)}</pre> : null}
    {visible.error ? <pre role="alert" className="m-0 whitespace-pre-wrap text-sm">{JSON.stringify(visible.error, null, 2)}</pre> : null}
    {error ? <p role="alert">{error}</p> : null}
    {pending ? <div className="grid gap-2"><p role="status">关联修复结果待核验，暂不能提交新修复。</p><Button size="sm" disabled={busy} onClick={() => void repair(true)}>核对原修复操作</Button></div> : null}
    {visible.associationPhase === 'completed' && visible.phase === 'saved_unlinked' ? <p role="status">关联已修复，历史运行失败事实保持不变。</p> : visible.phase === 'saved_unlinked' && visible.saveOperationId ? <>
      <Button size="sm" variant="secondary" disabled={busy || Boolean(pending)} onClick={() => void refresh()}>读取当前关联并修复</Button>
      {preview && !pending ? <>
        <ul className="text-sm">{targets.map((target, index) => <li key={index}>{JSON.stringify(target.recordRef)} · {target.exists ? `当前版本 ${target.currentLinkRevision} · ${target.currentEnvironmentId ?? '未关联环境'}` : '记录已不存在，无法修复'}</li>)}</ul>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={confirmed} disabled={busy || !repairable} onCheckedChange={value => setConfirmed(value === true)} /><span>确认按以上当前版本关联全部目标，并允许替换已有环境</span></label>
        <Button size="sm" disabled={busy || !confirmed || !repairable} onClick={() => void repair(false)}>确认修复关联</Button>
      </> : null}
    </> : null}
  </section>
}
