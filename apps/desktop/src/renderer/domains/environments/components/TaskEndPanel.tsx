import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import { safeProjectError } from '../../projects/presentation-error'
import { createEnvironmentApi } from '../api'
import { bindableRecords, selectedTargets } from '../record-targets'

export function TaskEndPanel({ workspaceKey, instanceId, projectId, taskId, runId, executionGeneration, inputs = [], client, disabled }: {
  workspaceKey: string
  instanceId: string
  projectId: string
  taskId: string
  runId: string
  executionGeneration: number
  inputs?: unknown[]
  client: StreamingApiClient
  disabled: boolean
}) {
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const instance = useQuery({
    queryKey: [workspaceKey, instanceId, 'environments', projectId, 'task-instance', taskId],
    queryFn: ({ signal }) => api.listInstances({ page: 1, pageSize: 5, taskId }, signal).then(page => page.items[0] ?? null),
    enabled: !disabled,
  })
  const records = useMemo(() => bindableRecords(inputs), [inputs])
  const [retain, setRetain] = useState(true)
  const [name, setName] = useState('登录环境')
  const [notes, setNotes] = useState('')
  const [selected, setSelected] = useState<Set<string>>(() => new Set(records.map(item => item.key)))
  const [replaceAllowed, setReplaceAllowed] = useState(false)
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
    onSuccess: result => {
      const phase = result.outcome && 'phase' in result.outcome ? String(result.outcome.phase) : 'completed'
      notify({
        title: phase === 'saved_unlinked' ? '环境已保存，关联未完成' : phase === 'completed' ? (retain ? '已保留登录环境' : '已结束并关闭环境') : '结束结果已记录',
        tone: phase === 'saved_unlinked' ? 'error' : 'success',
      })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  const conflicts = Array.isArray(end.data?.outcome?.conflicts) ? end.data.outcome.conflicts as Array<Record<string, unknown>> : []
  const repair = useMutation({
    mutationFn: () => {
      const operationId = end.data?.operation.operationId
      if (!operationId) throw new Error('没有可修复的结束操作')
      return api.repair(operationId, {
        recordTargets: conflicts.length
          ? conflicts.flatMap(conflict => {
            const recordRef = conflict.record && typeof conflict.record === 'object' ? conflict.record as Record<string, unknown> : null
            const revision = conflict.currentLinkRevision
            if (!recordRef || typeof revision !== 'number') return []
            return [{ recordRef, expectedLinkRevision: revision, replaceAllowed: true }]
          })
          : targets.map(item => ({ ...item, replaceAllowed: true })),
      }, crypto.randomUUID())
    },
    onSuccess: result => {
      const phase = result.outcome && 'phase' in result.outcome ? String(result.outcome.phase) : 'completed'
      notify({ title: phase === 'completed' ? '已按原操作修复关联' : '修复未完成，请核对当前关联事实', tone: phase === 'completed' ? 'success' : 'error' })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  if (instance.isLoading) return <section role="status" className="rounded-control border border-line bg-surface p-4 text-sm">正在读取任务环境…</section>
  if (!current) return <section className="rounded-control border border-line bg-surface p-4 text-sm text-muted">当前任务还没有可保留的环境实例。</section>
  const phase = end.data?.outcome && 'phase' in end.data.outcome ? String(end.data.outcome.phase) : null
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
      {phase === 'saved_unlinked' ? <Button size="sm" variant="secondary" disabled={disabled || repair.isPending} onClick={() => repair.mutate()}>修复关联</Button> : null}
    </div>
    {phase === 'saved_unlinked' ? <p role="alert" className="m-0 text-sm text-warning">环境已保存，记录关联未完成。可用原操作修复，不会重跑网页。</p> : null}
    {phase === 'completed' ? <p role="status" className="m-0 text-sm">结束事实已写入。原浏览器工作副本随后关闭。</p> : null}
  </section>
}
