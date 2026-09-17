import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { createAutomationApi } from '../../project-automations/api'
import type { ProjectRoute } from '../../projects/types'
import { createProjectRunsApi, type BatchQuery, type TaskQuery } from '../api'
import { BatchDirectory } from '../components/BatchDirectory'
import { TaskDirectory } from '../components/TaskDirectory'
import { runQueryKeys } from '../hooks'
import { presentRunFailure } from '../presentation'

export type RunPageContext = { workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean; onNavigate(route: ProjectRoute): void }
type Browse = { batch: BatchQuery; task: TaskQuery; batchPeriod: string | null; taskPeriod: string | null; scroll: Record<string, number> }
const empty = (): Browse => ({ batch: { page: 1, pageSize: 50, sort: '-createdAt' }, task: { page: 1, pageSize: 50, sort: '-createdAt' }, batchPeriod: null, taskPeriod: null, scroll: {} })
const validPeriod = (value: unknown) => value === '7d' || value === '30d' ? value : null
const periodStart = (period: string | null) => period ? new Date(Date.now() - Number.parseInt(period) * 86_400_000).toISOString() : undefined
const batchOptionName = (item: { automationName?: string | null; createdAt: string }) => `${item.automationName ?? '自动化'} · ${new Date(item.createdAt).toLocaleString('zh-CN')}`
function restore(key: string): Browse {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? '{}')
    const normalize = (input: Record<string, unknown>, filter: string, timeField: string) => ({ page: Number.isSafeInteger(input?.page) && Number(input.page) > 0 && Number(input.page) <= 2147483647 ? Number(input.page) : 1, pageSize: 50, sort: input?.sort === 'createdAt' ? 'createdAt' : '-createdAt', ...(typeof input?.q === 'string' && input.q.length <= 120 ? { q: input.q } : {}), ...(typeof input?.status === 'string' ? { status: input.status } : {}), ...(typeof input?.[filter] === 'string' ? { [filter]: input[filter] } : {}), ...(typeof input?.[timeField] === 'string' ? { [timeField]: input[timeField] } : {}) })
    return { batch: normalize(value.batch, 'automationId', 'startedFrom'), task: normalize(value.task, 'batchId', 'endedFrom'), batchPeriod: validPeriod(value.batchPeriod), taskPeriod: validPeriod(value.taskPeriod), scroll: value.scroll && typeof value.scroll === 'object' ? value.scroll : {} }
  } catch { return empty() }
}
export function RunDirectoryPage(props: RunPageContext & { view: 'batches' | 'tasks' }) {
  return <Directory key={JSON.stringify([props.workspaceKey, props.projectId])} {...props}/>
}
function Directory({ workspaceKey, instanceId, projectId, client, disabled, view, onNavigate }: RunPageContext & { view: 'batches' | 'tasks' }) {
  const key = `autoflow:run-directory:${JSON.stringify([workspaceKey, projectId])}`
  const [browse, setBrowse] = useState(() => restore(key))
  const api = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId])
  const automations = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const batch = useQuery({ queryKey: runQueryKeys.batches(workspaceKey, instanceId, projectId, browse.batch), queryFn: ({ signal }) => api.listBatches(browse.batch, signal), enabled: !disabled && view === 'batches', refetchInterval: 2000 })
  const task = useQuery({ queryKey: runQueryKeys.tasks(workspaceKey, instanceId, projectId, browse.task), queryFn: ({ signal }) => api.listTasks(browse.task, signal), enabled: !disabled && view === 'tasks', refetchInterval: 2000 })
  const options = useQuery({ queryKey: [workspaceKey, instanceId, 'project-runs', projectId, 'automation-options'], enabled: !disabled, queryFn: async ({ signal }) => {
    const result: { id: string; name: string }[] = []
    for (let page = 1; ; page++) { const data = await automations.list({ page, pageSize: 200, sort: 'name', query: '' }, signal); result.push(...data.items.map(item => ({ id: item.automationId, name: item.name }))); if (page * 200 >= data.total || data.items.length === 0) return result }
  } })
  const batchOptions = useQuery({ queryKey: [workspaceKey, instanceId, 'project-runs', projectId, 'batch-options'], enabled: !disabled && view === 'tasks', queryFn: async ({ signal }) => {
    const result: { id: string; name: string }[] = []
    for (let page = 1; ; page++) { const data = await api.listBatches({ page, pageSize: 200, sort: '-createdAt' }, signal); result.push(...data.items.map(item => ({ id: item.batchId, name: batchOptionName(item) }))); if (page * 200 >= data.total || data.items.length === 0) return result }
  } })
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(browse)) } catch { /* Viewing remains available without browser storage. */ } }, [key, browse])
  const loaded = view === 'batches' ? batch.data : task.data
  const hasLoaded = Boolean(loaded)
  useEffect(() => {
    if (!loaded) return
    const last = Math.max(1, Math.ceil(loaded.total / 50)), field = view === 'batches' ? 'batch' : 'task'
    if (browse[field].page > last) setBrowse(value => ({ ...value, [field]: { ...value[field], page: last } }))
  }, [loaded, view, browse])
  useEffect(() => {
    const saved = restore(key).scroll[view]
    if (hasLoaded && Number.isFinite(saved)) window.scrollTo(0, saved)
    // Restoration happens only when this view is mounted, not on live refresh.
  }, [key, view, hasLoaded])
  const remember = () => { try { const current = restore(key); sessionStorage.setItem(key, JSON.stringify({ ...current, scroll: { ...current.scroll, [view]: window.scrollY } })) } catch { /* optional position */ } }
  const open = (route: ProjectRoute) => { remember(); onNavigate(route) }
  const current = view === 'batches' ? batch : task
  return <section className="grid min-w-0 gap-4 rounded-card border border-line bg-surface p-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="m-0 text-2xl font-semibold">运行记录</h2><p className="mb-0 mt-2 text-sm text-muted">查看自动化批次、任务与真实执行结果</p></div><Button size="sm" disabled={disabled || current.isFetching} onClick={() => void current.refetch()}>刷新记录</Button></header>
    <Tabs value={view} onValueChange={value => open({ projectId, tab: 'runs', runView: value as 'batches' | 'tasks' })}><div className="flex flex-wrap items-center justify-between gap-3 border-b border-line"><TabsList className="border-0"><TabsTrigger value="batches">批次记录</TabsTrigger><TabsTrigger value="tasks">任务记录</TabsTrigger></TabsList><Select className="w-44" aria-label="运行记录排序" value={browse[view === 'batches' ? 'batch' : 'task'].sort} clearable={false} options={[{ value: '-createdAt', label: '最新创建在前' }, { value: 'createdAt', label: '最早创建在前' }]} onValueChange={sort => { const field = view === 'batches' ? 'batch' : 'task'; setBrowse(value => ({ ...value, [field]: { ...value[field], sort, page: 1 } })) }}/></div>
    {options.error || batchOptions.error ? <div role="alert" className="p-2 text-sm text-danger">筛选资料读取失败。<Button size="sm" onClick={() => { void options.refetch(); if (view === 'tasks') void batchOptions.refetch() }}>重试筛选资料</Button></div> : null}
    <TabsContent value="batches"><BatchDirectory page={batch.data} filters={{ q: browse.batch.q ?? null, automationId: browse.batch.automationId ?? null, status: browse.batch.status ?? null, period: browse.batchPeriod }} automationOptions={options.data} loading={batch.isLoading} refreshing={disabled} error={batch.error ? presentRunFailure(batch.error) : disabled && !batch.data ? '本地服务暂不可用，请等待连接恢复' : undefined} onFiltersChange={filters => setBrowse(value => ({ ...value, batchPeriod: filters.period, batch: { ...value.batch, q: filters.q ?? undefined, automationId: filters.automationId ?? undefined, status: filters.status ?? undefined, startedFrom: filters.period === value.batchPeriod ? value.batch.startedFrom : periodStart(filters.period), page: 1 } }))} onPageChange={page => setBrowse(value => ({ ...value, batch: { ...value.batch, page } }))} onOpen={item => open({ projectId, tab: 'runs', runView: 'batches', batchId: item.batchId })} onRetry={() => void batch.refetch()}/></TabsContent>
    <TabsContent value="tasks"><TaskDirectory page={task.data} filters={{ q: browse.task.q ?? null, batchId: browse.task.batchId ?? null, status: browse.task.status ?? null, period: browse.taskPeriod }} batchOptions={batchOptions.data} loading={task.isLoading} refreshing={disabled} error={task.error ? presentRunFailure(task.error) : disabled && !task.data ? '本地服务暂不可用，请等待连接恢复' : undefined} onFiltersChange={filters => setBrowse(value => ({ ...value, taskPeriod: filters.period, task: { ...value.task, q: filters.q ?? undefined, batchId: filters.batchId ?? undefined, status: filters.status ?? undefined, endedFrom: filters.period === value.taskPeriod ? value.task.endedFrom : periodStart(filters.period), page: 1 } }))} onPageChange={page => setBrowse(value => ({ ...value, task: { ...value.task, page } }))} onOpen={item => open({ projectId, tab: 'runs', taskId: item.taskId, taskTab: 'logs' })} onRetry={() => void task.refetch()}/></TabsContent></Tabs>
  </section>
}
