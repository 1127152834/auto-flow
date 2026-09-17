import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { notify } from '../../../shared/components/Toaster'
import { createProjectRunsApi, type TaskQuery } from '../api'
import { BatchConfigurationSnapshot, BatchDetail } from '../components/BatchDetail'
import { TaskDirectory } from '../components/TaskDirectory'
import { StopBatchDialog } from '../components/StopBatchDialog'
import { RunCommandNotice } from '../components/RunCommandNotice'
import { runQueryKeys, useBatchCommand } from '../hooks'
import type { RunPageContext } from './RunDirectoryPage'
import { presentRunFailure } from '../presentation'
const terminal = new Set(['completed', 'failed', 'stopped', 'interrupted'])
export function BatchDetailPage(props: RunPageContext & { batchId: string }) {
  return <Detail key={JSON.stringify([props.workspaceKey, props.projectId, props.batchId])} {...props}/>
}
function Detail({ workspaceKey, instanceId, projectId, client, disabled, readOnly, batchId, onNavigate }: RunPageContext & { batchId: string }) {
  const cache = useQueryClient(), api = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId])
  const [query, setQuery] = useState<TaskQuery>({ batchId, page: 1, pageSize: 50, sort: 'createdAt' })
  const [period, setPeriod] = useState<string | null>(null)
  const detail = useQuery({ queryKey: runQueryKeys.batch(workspaceKey, instanceId, projectId, batchId), queryFn: ({ signal }) => api.getBatch(batchId, signal), enabled: !disabled, refetchInterval: value => value.state.data && terminal.has(value.state.data.batch.status) ? false : 1000 })
  const tasks = useQuery({ queryKey: runQueryKeys.tasks(workspaceKey, instanceId, projectId, query), queryFn: ({ signal }) => api.listTasks(query, signal), enabled: !disabled, refetchInterval: detail.data && terminal.has(detail.data.batch.status) ? false : 1000 })
  const batchTerminal = Boolean(detail.data && terminal.has(detail.data.batch.status)), terminalTasksRefreshed = useRef(false), refetchTasks = tasks.refetch
  useEffect(() => { if (!batchTerminal) { terminalTasksRefreshed.current = false; return }; if (terminalTasksRefreshed.current) return; terminalTasksRefreshed.current = true; void refetchTasks() }, [batchTerminal, refetchTasks])
  const [confirmation, setConfirmation] = useState<'stop' | 'forceStop' | null>(null)
  const refresh = () => { void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'project-runs', projectId] }) }
  const command = useBatchCommand({ client, workspaceKey, instanceId, projectId, scope: { type: 'stop', batchId }, disabled, readOnly,
    onAccepted(operation, key) { const resource = operation.resource as { type?: unknown; projectId?: unknown; batchId?: unknown }; if ((operation.kind !== 'stopBatch' && operation.kind !== 'forceStopBatch') || resource.type !== 'batch' || resource.projectId !== projectId || resource.batchId !== batchId) return; setConfirmation(null); refresh(); notify({ title: '停止请求已接受，正在清理', tone: 'info', operationId: JSON.stringify([workspaceKey, key]) }); return true },
    onCompleted(batch, key) { if (batch.projectId !== projectId || batch.batchId !== batchId) return; setConfirmation(null); refresh(); notify({ title: '停止操作已完成', tone: 'success', operationId: JSON.stringify([workspaceKey, key]) }) },
  })
  const back = () => onNavigate({ projectId, tab: 'runs', runView: 'batches' })
  if (!detail.data) return <section className="rounded-card border border-line bg-surface p-5"><p role={detail.error || disabled ? 'alert' : 'status'}>{detail.error ? `批次读取失败：${presentRunFailure(detail.error)}` : disabled ? '本地服务暂不可用，请等待连接恢复。' : '正在读取批次…'}</p><Button onClick={back}>返回批次列表</Button>{detail.error ? <Button disabled={disabled} onClick={() => void detail.refetch()}>重试读取</Button> : null}</section>
  const batch = detail.data.batch, stopping = ['stopping', 'reconciling'].includes(batch.status), forceEligible = detail.data.forceStopAllowed
  return <section className="grid min-w-0 gap-4"><RunCommandNotice command={command} disabled={disabled} readOnly={readOnly}/>{detail.error ? <div role="alert" className="text-sm text-danger">刷新失败，保留上次读取的批次：{presentRunFailure(detail.error)}<Button onClick={() => void detail.refetch()}>重试读取</Button></div> : null}
    <BatchDetail detail={detail.data} showConfiguration={false} onBack={back} stopping={disabled || command.busy} onStop={!stopping ? () => setConfirmation('stop') : undefined} onForceStop={forceEligible ? () => setConfirmation('forceStop') : undefined}/>
    {stopping ? <p className="rounded-control border border-warning/30 bg-surface p-3 text-sm">{forceEligible ? '普通停止宽限期已结束，可以强制停止并核验资源清理。' : '正在停止并核验资源清理。普通停止宽限期结束后才允许强制停止。'}最终结果以持久运行事实为准。</p> : null}
    <section className="rounded-card border border-line bg-surface p-5"><h3 className="mt-0">本批次任务</h3><TaskDirectory context="batch" page={tasks.data} filters={{ q: query.q ?? null, batchId, status: query.status ?? null, period }} batchOptions={[{ id: batchId, name: `${batch.automationName ?? '自动化'} · ${new Date(batch.createdAt).toLocaleString('zh-CN')}` }]} loading={tasks.isLoading} refreshing={disabled} error={tasks.error ? presentRunFailure(tasks.error) : disabled && !tasks.data ? '本地服务暂不可用，请等待连接恢复' : undefined} onFiltersChange={filters => { const nextPeriod = filters.period; setPeriod(nextPeriod); setQuery(value => ({ ...value, q: filters.q ?? undefined, status: filters.status ?? undefined, endedFrom: nextPeriod === period ? value.endedFrom : nextPeriod ? new Date(Date.now() - Number.parseInt(nextPeriod) * 86_400_000).toISOString() : undefined, page: 1 })) }} onPageChange={page => setQuery(value => ({ ...value, page }))} onOpen={task => onNavigate({ projectId, tab: 'runs', taskId: task.taskId, taskTab: 'logs' })} onRetry={() => void tasks.refetch()}/></section>
    <section className="overflow-hidden rounded-card border border-line bg-surface"><BatchConfigurationSnapshot value={(detail.data.configurationSnapshot ?? {}) as Record<string, unknown>}/></section>
    <StopBatchDialog key={confirmation ?? 'closed'} open={confirmation !== null} force={confirmation === 'forceStop'} busy={command.busy} error={command.error} automationName={batch.automationName ?? '自动化'} startedAt={batch.createdAt} activeTaskCount={batch.activeTaskCount} onOpenChange={open => { if (!open) setConfirmation(null) }} onConfirm={reason => { const body = { expectedStatusRevision: batch.statusRevision, reason }; void (confirmation === 'forceStop' ? command.forceStop(batchId, body) : command.stop(batchId, body)) }}/>
  </section>
}
