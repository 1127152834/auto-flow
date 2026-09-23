import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { ProjectRunAssets } from '../../project-data/components/ProjectRunAssets'
import { createProjectStatisticsApi, type StudioStatistics } from '../statistics-api'

type Props = { workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean }
const states: Record<string, string> = { starting: '启动中', running: '运行中', paused: '已暂停', failed_paused: '失败暂停', completed: '成功', failed: '失败', stopped: '已取消', interrupted: '已中断' }
const triggers: Record<string, string> = { unknown: '来源未记录', manual: '手动启动计划', time: '定时', startup: '应用启动', webhook: 'Webhook', hotkey: '快捷键', repeat: '重复计划' }
const number = (value: number) => value.toLocaleString('zh-CN')
const initialDate = () => { const date = new Date(); date.setDate(date.getDate() - 7); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 10) }
export function StudioStatisticsPanel(props: Props) {
  return <Statistics key={JSON.stringify([props.workspaceKey, props.instanceId, props.projectId])} {...props} />
}
function Statistics(props: Props) {
  const { workspaceKey, instanceId, projectId, client, disabled } = props
  const api = useMemo(() => createProjectStatisticsApi(client, projectId), [client, projectId])
  const [filter, setFilter] = useState({ from: initialDate(), to: '', workflowId: '', status: '', cursor: 0 })
  const [selected, setSelected] = useState<StudioStatistics['items'][number] | null>(null)
  const [logNode, setLogNode] = useState('')
  const [logCursor, setLogCursor] = useState(0)
  const [assets, setAssets] = useState(false)
  const from = new Date(`${filter.from}T00:00:00`)
  const to = filter.to ? new Date(`${filter.to}T23:59:59.999`) : null
  const valid = Number.isFinite(from.getTime()) && (!to || (Number.isFinite(to.getTime()) && to >= from))
  const prefix = [workspaceKey, instanceId, 'project-statistics', projectId, 'studio']
  const stats = useQuery({ queryKey: [...prefix, filter], enabled: !disabled && valid,
    queryFn: ({ signal }) => api.studio({ from: from.toISOString(), ...(to ? { to: to.toISOString() } : {}), ...(filter.workflowId ? { workflowId: filter.workflowId } : {}), ...(filter.status ? { status: filter.status } : {}), cursor: filter.cursor }, signal) })
  const logs = useQuery({ queryKey: [...prefix, 'logs', selected?.runId, logNode, logCursor], enabled: !disabled && Boolean(selected),
    queryFn: ({ signal }) => client.request<components['schemas']['StudioExecutionLogPage']>(`/api/workflow-runs/${encodeURIComponent(selected!.runId)}/logs?projectId=${encodeURIComponent(projectId)}&cursor=${logCursor}&limit=100${logNode ? `&nodeId=${encodeURIComponent(logNode)}` : ''}`, { signal }) })
  const change = (patch: Partial<typeof filter>) => { setSelected(null); setAssets(false); setLogCursor(0); setFilter(value => ({ ...value, ...patch, cursor: patch.cursor ?? 0 })) }
  const data = stats.error || !valid ? undefined : stats.data
  const metrics = data ? [
    ['运行总数', number(data.totalRuns)], ['成功率', data.successRate === null ? '无样本' : `${(data.successRate * 100).toFixed(1)}%`],
    ['平均运行时长', data.averageDurationMs === null ? '无样本' : `${number(data.averageDurationMs)} 毫秒`],
    ['节点执行次数', number(data.nodeExecutionCount)], ['产生结果的执行次数', number(data.extractionExecutionCount)],
    ['结果文件', number(data.artifactCount)], ['诊断文件', number(data.diagnosticCount)], ['调试次数', number(data.debugCount)],
  ] : []
  return <section aria-label="Studio 运行统计" className="grid gap-4 rounded-card border border-line bg-surface p-4">
    <p className="text-sm text-muted">按运行启动日期筛选；成功率为成功 /（成功 + 失败），时长含暂停和清理。结果次数不等于业务数据条数。</p>
    <div className="flex flex-wrap items-center gap-3">
      <label>开始日期<Input type="date" aria-label="Studio 统计开始日期" value={filter.from} onChange={event => change({ from: event.target.value })} /></label>
      <label>结束日期<Input type="date" aria-label="Studio 统计结束日期" value={filter.to} onChange={event => change({ to: event.target.value })} /></label>
      <Input aria-label="Studio 流程筛选" placeholder="流程 ID" value={filter.workflowId} onChange={event => change({ workflowId: event.target.value })} />
      <Select aria-label="Studio 运行状态筛选" value={filter.status} clearable={false} options={[{ value: '', label: '全部状态' }, ...Object.entries(states).map(([value, label]) => ({ value, label }))]} onValueChange={status => change({ status })} />
      <Button disabled={disabled || !valid || stats.isFetching} onClick={() => void stats.refetch()}>刷新 Studio 统计</Button>
    </div>
    {!valid ? <p role="alert">请选择有效日期，结束日期不能早于开始日期。</p> : null}
    {stats.isPending && !disabled && valid ? <p role="status">正在读取 Studio 统计…</p> : null}
    {disabled ? <p role="status">本地服务暂不可用。</p> : null}
    {stats.error ? <p role="alert">统计读取失败，请刷新后重试。</p> : null}
    {data ? <>
      <dl aria-label="Studio 统计指标" className="grid grid-cols-2 gap-3 lg:grid-cols-4">{metrics.map(([name, value]) => <div key={name} className="rounded-control border border-line p-3"><dt className="text-sm text-muted">{name}</dt><dd className="m-0 text-xl tabular-nums">{value}</dd></div>)}</dl>
      <div className="flex flex-wrap gap-3">{Object.entries(data.byStatus).map(([status, count]) => <Button key={status} disabled={disabled} onClick={() => change({ status })}>{states[status] ?? status} {number(count)}</Button>)}</div>
      <p className="text-sm text-muted">录制次数：{data.recordingCount === null ? data.recordingUnavailableReason : number(data.recordingCount)}。最近活动：{data.latestActivityAt ?? '无记录'}。统计读取时间：{data.calculatedAt}</p>
      <div className="grid gap-4 md:grid-cols-3"><div><h3>失败节点（前 10）</h3><ul>{data.failuresByNode.map(item => <li key={item.nodeId}>{item.nodeId} · {item.count} 次</li>)}</ul></div><div><h3>流程运行（前 10）</h3><ul>{data.runsByWorkflow.map(item => <li key={item.workflowId}><Button disabled={disabled} onClick={() => change({ workflowId: item.workflowId })}>{item.name} · {item.count} 次</Button></li>)}</ul></div><div><h3>启动来源</h3><ul>{Object.entries(data.byTrigger).map(([source, count]) => <li key={source}>{triggers[source] ?? source} · {count} 次</li>)}</ul></div></div>
      {!data.items.length ? <p>没有匹配的 Studio 运行</p> : <ul className="grid gap-2">{data.items.map(item => <li key={item.runId} className="flex flex-wrap justify-between gap-2 border-t border-line py-2"><span>{item.workflowName} · {states[item.status] ?? item.status} · {item.mode === 'debug' ? '调试' : item.mode === 'run' ? '运行' : '历史模式未记录'} · {item.startedAt}</span><Button aria-label={`查看运行 ${item.runId}`} disabled={disabled} onClick={() => { setSelected(item); setLogNode(''); setLogCursor(0); setAssets(false) }}>查看运行</Button></li>)}</ul>}
      <Pagination offset={filter.cursor} limit={50} total={data.totalRuns} count={data.items.length} disabled={disabled || stats.isFetching} onOffsetChange={cursor => change({ cursor })} />
    </> : null}
    {selected ? <section aria-label="统计运行详情" className="grid gap-3 border-t border-line pt-4"><div className="flex justify-between gap-3"><p>{selected.workflowName} · 运行 {selected.runId}</p><Button onClick={() => setSelected(null)}>关闭运行详情</Button></div>
      <Input aria-label="统计日志节点筛选" placeholder="节点 ID" value={logNode} onChange={event => { setLogNode(event.target.value); setLogCursor(0) }} />
      {logs.isPending ? <p role="status">正在读取运行日志…</p> : null}{logs.error ? <p role="alert">日志读取失败，请重试。<Button onClick={() => void logs.refetch()}>重试日志</Button></p> : null}
      {logs.data ? <><pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all">{logs.data.items.map(item => JSON.stringify(item)).join('\n') || '暂无运行日志'}</pre><Pagination offset={logCursor} limit={100} total={logs.data.total} count={logs.data.items.length} disabled={disabled || logs.isFetching} onOffsetChange={setLogCursor} /></> : null}
      <details key={selected.runId} onToggle={event => setAssets(event.currentTarget.open)}><summary className="cursor-pointer">本次运行的产物</summary>{assets ? <ProjectRunAssets {...props} initialRunId={selected.runId} /> : null}</details>
    </section> : null}
  </section>
}
