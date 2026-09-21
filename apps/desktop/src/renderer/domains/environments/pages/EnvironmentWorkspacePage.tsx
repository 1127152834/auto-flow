import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Clock, HardDrive, Monitor } from '@phosphor-icons/react'
import { notify } from '../../../shared/components/Toaster'
import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { safeProjectError } from '../../projects/presentation-error'
import type { ProjectRoute, ProjectView } from '../../projects/types'
import { createEnvironmentApi, type EnvironmentInstance, type EnvironmentQuery, type ManualItem } from '../api'
import { EnvironmentDirectory } from '../components/EnvironmentDirectory'
import { ManualDirectory } from '../components/ManualDirectory'
import { ProjectDefaultsPanel } from '../components/ProjectDefaultsPanel'

export type EnvironmentWorkspacePageProps = {
  workspaceKey: string
  instanceId: string
  projectId: string
  project: ProjectView
  client: StreamingApiClient
  disabled: boolean
  readOnly: boolean
  onNavigate(route: ProjectRoute): void
}

type View = 'running' | 'manual' | 'saved' | 'defaults'
const stamp = (value: number) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const clock = (value: string | null) => value ? new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)) : '—'
const minutesLeft = (expiresAt: string | null) => {
  if (!expiresAt) return null
  const minutes = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 60_000)
  return Number.isNaN(minutes) ? null : minutes
}
const sections: Record<View, { title: string; note: string }> = {
  // 当前现场 composes the manual and automatic partitions the way the approved
  // artboard does, so its heading and subtitle are built from live counts below.
  running: { title: '当前现场', note: '' },
  manual: { title: '等待人工现场', note: '保留浏览器、输入和租约；现场保留期间仍占用运行容量。' },
  saved: { title: '持久环境', note: '工作流结束节点明确保存的记录，不是正在运行的会话。' },
  defaults: { title: '项目默认资源', note: '用于未单独指定对应资源的方案。' },
}
const sorts = [
  { value: '-updatedAt', label: '最近修改' },
  { value: 'updatedAt', label: '最早修改' },
  { value: 'name', label: '名称升序' },
  { value: '-name', label: '名称降序' },
]
const states = [
  { value: '', label: '全部状态' },
  { value: 'ready', label: '就绪' },
  { value: 'unavailable', label: '不可用' },
  { value: 'deleting', label: '删除中' },
]
const sources: Record<string, string> = { newFromProfile: '按浏览器配置新建', fixedEnvironment: '固定持久环境', inputEnvironment: '使用记录关联环境' }
const instanceStates: Record<string, string> = { reserved: '已预约', starting: '启动中', active: '自动运行', closing: '停止中', saving: '保存中', cleaning: '清理中', retained_unsaved: '待处理保存' }
const instanceTones: Record<string, string> = {
  active: 'border-sage/40 bg-sage-soft text-sage-strong',
  saving: 'border-clay/30 bg-clay-soft text-clay',
  retained_unsaved: 'border-warning/40 bg-warning-soft text-warning',
}
const pill = (label: string, tone?: string) => <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-control border px-2 py-0.5 text-xs ${tone ?? 'border-line bg-surface-subtle text-muted'}`}>{label}</span>

export function EnvironmentWorkspacePage(props: EnvironmentWorkspacePageProps) {
  return <Workspace key={JSON.stringify([props.workspaceKey, props.projectId])} {...props} />
}

function Workspace({ workspaceKey, instanceId, projectId, project, client, disabled, readOnly, onNavigate }: EnvironmentWorkspacePageProps) {
  const [view, setView] = useState<View>('running')
  const [query, setQuery] = useState<EnvironmentQuery>({ query: '', page: 1, pageSize: 50, sort: '-updatedAt' })
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const cache = useQueryClient()
  const prefix = [workspaceKey, instanceId, 'environments', projectId] as const
  // Every partition stays loaded so the section chips and the right column can show
  // real counts, the way the approved environment artboard renders them. Nothing is
  // invented: a partition without loaded data renders without a count instead of "0".
  const saved = useQuery({
    queryKey: [...prefix, 'saved', query],
    queryFn: ({ signal }) => api.list(query, signal),
    enabled: !disabled,
  })
  const running = useQuery({
    queryKey: [...prefix, 'running'],
    queryFn: ({ signal }) => api.listInstances({ page: 1, pageSize: 50 }, signal),
    enabled: !disabled,
    refetchInterval: 4000,
  })
  const liveStates = new Set(['reserved', 'starting', 'active', 'closing', 'saving', 'cleaning', 'retained_unsaved'])
  const runningItems = (running.data?.items ?? []).filter(item => liveStates.has(item.state))
  const manual = useQuery({
    queryKey: [...prefix, 'manual'],
    queryFn: ({ signal }) => api.listManual({ page: 1, pageSize: 50 }, signal),
    enabled: !disabled,
  })
  const manualItems = manual.data?.items ?? []
  // A scene waiting for a human is still a live work copy, but the artboard lists it under
  // 需要人工处理; only the rest of the live copies belong under 自动运行.
  const automaticItems = runningItems.filter(item => !manualItems.some(entry => entry.instanceId === item.instanceId))
  const openTask = (taskId: string) => onNavigate({ projectId, tab: 'runs', runView: 'tasks', taskId, taskTab: 'logs' })
  const openBatch = (batchId: string) => onNavigate({ projectId, tab: 'runs', runView: 'batches', batchId })
  const openInstance = useMutation({
    mutationFn: (item: { instanceId: string; instanceUseGeneration: number }) => api.openInstance(item.instanceId, item.instanceUseGeneration, crypto.randomUUID()),
    onSuccess: () => { notify({ title: '已请求进入当前浏览器', tone: 'success' }); void cache.invalidateQueries({ queryKey: prefix }) },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  // One manual detail serves both the run-records and environment entries, so this page only navigates.
  const openManualItem = (item: ManualItem) => onNavigate({ projectId, tab: 'runs', runView: 'manual', manualItemId: item.manualItemId })
  const maintenance = useMutation({
    mutationFn: (item: { environmentId: string; contentGeneration: number }) => api.startMaintenance(item.environmentId, item.contentGeneration, crypto.randomUUID()),
    onSuccess: () => { notify({ title: '已打开维护副本', tone: 'success' }); void cache.invalidateQueries({ queryKey: prefix }) },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  const actionsDisabled = disabled || readOnly
  const partitions = [
    { value: 'running' as View, label: '运行环境', count: running.data ? runningItems.length : null },
    { value: 'manual' as View, label: '等待人工', count: manual.data ? manual.data.total : null },
    { value: 'saved' as View, label: '持久环境', count: saved.data ? saved.data.total : null },
    { value: 'defaults' as View, label: '项目默认资源', count: null },
  ]
  const section = sections[view]
  const lastUpdated = Math.max(saved.dataUpdatedAt, running.dataUpdatedAt, manual.dataUpdatedAt)
  const heading = view === 'running'
    ? { title: '当前现场', note: running.data ? (runningItems.length ? `${runningItems.length} 个临时现场 · 含 ${manualItems.length} 个等待人工` : '当前没有临时现场') : '' }
    : view === 'saved' && saved.data
      ? { title: section.title, note: `工作流结束节点明确保存的 ${saved.data.total} 条记录，不是正在运行的会话。` }
      : section
  return <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_19rem] xl:items-start">
    <div className="grid min-w-0 gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="m-0 text-xl font-semibold">{heading.title}</h2>
          {heading.note ? <p className="mb-0 mt-2 text-sm text-muted">{heading.note}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {lastUpdated ? <span className="text-sm text-muted">最后更新：{stamp(lastUpdated)}</span> : null}
          <Button size="sm" variant="secondary" disabled={disabled || saved.isFetching || running.isFetching || manual.isFetching} onClick={() => { void saved.refetch(); void running.refetch(); void manual.refetch() }}>刷新</Button>
        </div>
      </header>
      <Tabs value={view} onValueChange={value => setView(value as View)}>
        <TabsList variant="segmented" aria-label="环境分区">
          {partitions.map(item => <TabsTrigger key={item.value} variant="segmented" value={item.value} aria-label={item.count === null ? item.label : `${item.label} ${item.count}`}>{item.label}{item.count === null ? null : <span aria-hidden className="ml-1.5 text-xs text-muted">{item.count}</span>}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="running">
          <LiveBoard
            manualItems={manualItems}
            instances={automaticItems}
            manualError={manual.error ? safeProjectError(manual.error) : disabled && !manual.data ? '本地服务暂不可用，请等待连接恢复' : undefined}
            instanceError={running.error ? safeProjectError(running.error) : disabled && !running.data ? '本地服务暂不可用，请等待连接恢复' : undefined}
            loading={running.isLoading || manual.isLoading}
            disabled={actionsDisabled || openInstance.isPending}
            onRetry={() => { void running.refetch(); void manual.refetch() }}
            onEnterManual={openManualItem}
            onOpenInstance={item => openInstance.mutate(item)}
            onOpenTask={openTask}
            onOpenBatch={openBatch}
            onOpenEnvironment={environmentId => onNavigate({ projectId, tab: 'environments', environmentId })}
          />
        </TabsContent>
        <TabsContent value="manual">
          <ManualDirectory
            items={manualItems}
            loading={manual.isLoading}
            error={manual.error ? safeProjectError(manual.error) : undefined}
            disabled={actionsDisabled}
            onRetry={() => void manual.refetch()}
            onResume={openManualItem}
            onFinish={openManualItem}
            onOpen={openManualItem}
            onOpenTask={openTask}
            onOpenBatch={openBatch}
          />
        </TabsContent>
        <TabsContent value="saved">
          <div className="mb-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_10rem_12rem] md:items-end">
            <SearchInput aria-label="搜索持久环境" value={query.query} onChange={event => setQuery(current => ({ ...current, query: event.target.value, page: 1 }))} />
            <Select aria-label="持久环境状态" clearable={false} value={query.state ?? ''} options={states} onValueChange={state => setQuery(current => ({ ...current, state: state || undefined, page: 1 }))} />
            <Select aria-label="持久环境排序" clearable={false} value={query.sort} options={sorts} onValueChange={sort => setQuery(current => ({ ...current, sort: sort as EnvironmentQuery['sort'], page: 1 }))} />
          </div>
          <EnvironmentDirectory
            page={saved.data}
            query={query.query}
            loading={saved.isLoading}
            error={saved.error ? safeProjectError(saved.error) : disabled && !saved.data ? '本地服务暂不可用，请等待连接恢复' : undefined}
            disabled={actionsDisabled || maintenance.isPending}
            onOpen={environmentId => onNavigate({ projectId, tab: 'environments', environmentId })}
            onOpenTask={openTask}
            onMaintenance={item => maintenance.mutate(item)}
            onRetry={() => void saved.refetch()}
          />
          {saved.data ? <Pagination showPage offset={(saved.data.page - 1) * saved.data.pageSize} limit={saved.data.pageSize} total={saved.data.total} count={saved.data.items.length} disabled={saved.isFetching} onOffsetChange={offset => setQuery(current => ({ ...current, page: Math.floor(offset / current.pageSize) + 1 }))} /> : null}
        </TabsContent>
        <TabsContent value="defaults">
          <ProjectDefaultsPanel project={project} readOnly={readOnly} />
        </TabsContent>
      </Tabs>
    </div>
    <aside className="grid min-w-0 gap-4" aria-label="环境概览">
      <DefaultsCard project={project} count={saved.data ? saved.data.total : null} onShowDefaults={() => setView('defaults')} onShowSaved={() => setView('saved')} />
    </aside>
  </section>
}

// The approved artboard keeps 项目默认资源 and 持久环境 visible next to the current
// scene, so the two shortcuts live in a right column instead of only inside the chips.
function DefaultsCard({ project, count, onShowDefaults, onShowSaved }: { project: ProjectView; count: number | null; onShowDefaults(): void; onShowSaved(): void }) {
  const resources = project.defaultResources
  const proxy = { sourceDefault: '沿用浏览器配置', none: '不使用代理', fixed: '固定代理', pool: '代理池' }[resources.proxy.mode] ?? resources.proxy.mode
  const rows: [string, string][] = [['浏览器', resources.profileId ? '已指定浏览器配置' : '未指定'], ['代理', proxy]]
  return <>
    <section className="grid gap-3 rounded-control border border-line bg-surface p-4" aria-label="项目默认资源概览">
      <h3 className="m-0 flex items-center gap-2 text-sm font-semibold"><Monitor size={19} aria-hidden className="text-clay" />项目默认资源</h3>
      <dl className="grid gap-2 text-sm">
        {rows.map(([label, value]) => <div key={label} className="flex items-baseline justify-between gap-3"><dt className="text-muted">{label}</dt><dd className="m-0 min-w-0 truncate text-right font-medium">{value}</dd></div>)}
      </dl>
      <Button variant="ghost" className="justify-between text-clay" onClick={onShowDefaults}>查看默认资源<ArrowRight aria-hidden /></Button>
    </section>
    <section className="grid gap-3 rounded-control border border-line bg-surface p-4" aria-label="持久环境概览">
      <h3 className="m-0 flex items-center gap-2 text-sm font-semibold"><HardDrive size={19} aria-hidden className="text-clay" />持久环境{count === null ? null : ` ${count}`}</h3>
      <p className="m-0 text-sm text-muted">工作流明确保存的环境。</p>
      <Button variant="ghost" className="justify-between text-clay" onClick={onShowSaved}>查看持久环境{count === null ? null : ` ${count}`}<ArrowRight aria-hidden /></Button>
    </section>
  </>
}

function minutesText(expiresAt: string | null) {
  const minutes = minutesLeft(expiresAt)
  if (minutes === null) return null
  return <span className={minutes <= 0 ? 'text-warning' : 'text-muted'}>{minutes <= 0 ? '已超时' : `剩余 ${minutes} 分钟`}</span>
}

function LiveBoard({ manualItems, instances, manualError, instanceError, loading, disabled, onRetry, onEnterManual, onOpenInstance, onOpenTask, onOpenBatch, onOpenEnvironment }: {
  manualItems: ManualItem[]
  instances: EnvironmentInstance[]
  manualError?: string
  instanceError?: string
  loading: boolean
  disabled: boolean
  onRetry(): void
  onEnterManual(item: ManualItem): void
  onOpenInstance(item: EnvironmentInstance): void
  onOpenTask(taskId: string): void
  onOpenBatch(batchId: string): void
  onOpenEnvironment(environmentId: string): void
}) {
  const waiting = manualItems.filter(item => item.status === 'waiting' || item.status === 'resume_requested')
  const error = manualError ?? instanceError
  return <section className="grid gap-4" aria-label="当前现场">
    {error ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-warning/30 bg-warning/10 p-3"><span>{error}</span><Button onClick={onRetry}>重试读取</Button></div> : null}
    {!error && loading && !waiting.length && !instances.length ? <p className="m-0 text-sm text-muted">正在读取当前现场…</p> : null}
    {waiting.length ? <div className="grid gap-3">
      <h3 className="m-0 text-sm font-semibold">需要人工处理 {waiting.length}</h3>
      <div className="grid gap-3 lg:grid-cols-2">
        {waiting.map(item => <article key={item.manualItemId} className="grid min-w-0 gap-3 rounded-control border border-warning/30 bg-surface p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            {pill('等待人工', 'border-warning/40 bg-warning-soft text-warning')}
            <div className="grid justify-items-end text-xs">
              <span className="text-muted">保留至 {clock(item.expiresAt)}</span>
              {minutesText(item.expiresAt)}
            </div>
          </div>
          <dl className="grid gap-1.5 text-sm">
            <div className="flex items-baseline gap-3"><dt className="shrink-0 text-muted">任务</dt><dd className="m-0 min-w-0"><Button variant="ghost" className="h-auto p-0 text-sm text-clay" onClick={() => onOpenTask(item.taskId)}>查看任务</Button></dd></div>
            {item.reason ? <div className="flex items-baseline gap-3"><dt className="shrink-0 text-muted">等待原因</dt><dd className="m-0 min-w-0 break-words">{item.reason}</dd></div> : null}
          </dl>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={disabled} onClick={() => onEnterManual(item)}>进入人工处理</Button>
            <Button size="sm" variant="ghost" onClick={() => onOpenTask(item.taskId)}>查看任务</Button>
          </div>
        </article>)}
      </div>
    </div> : null}
    {instances.length ? <div className="grid gap-3">
      <h3 className="m-0 text-sm font-semibold">自动运行 {instances.length}</h3>
      <ul className="m-0 grid list-none gap-2 p-0">
        {instances.map(item => <li key={item.instanceId} className="grid min-w-0 gap-3 rounded-control border border-line bg-surface p-3 lg:grid-cols-[8rem_minmax(0,1fr)_11rem_11rem_auto] lg:items-center">
          {pill(instanceStates[item.state] ?? item.state, instanceTones[item.state])}
          <div className="grid min-w-0 gap-1 text-sm">
            <span className="truncate">{sources[item.source] ?? item.source}</span>
            {item.environmentId ? <Button variant="ghost" className="h-auto w-fit p-0 text-xs text-clay" onClick={() => onOpenEnvironment(item.environmentId!)}>关联的持久环境</Button> : <span className="text-xs text-muted">独立工作副本</span>}
          </div>
          <div className="grid gap-1 text-sm"><span className="text-xs text-muted">任务</span>{item.activeTaskId ? <Button variant="ghost" className="h-auto w-fit p-0 text-sm text-clay" onClick={() => onOpenTask(item.activeTaskId!)}>查看任务</Button> : <span>—</span>}</div>
          <div className="grid gap-1 text-sm"><span className="text-xs text-muted">批次</span>{item.activeRunId ? <Button variant="ghost" className="h-auto w-fit p-0 text-sm text-clay" onClick={() => onOpenBatch(item.activeRunId!)}>查看批次</Button> : <span>—</span>}</div>
          <div className="flex flex-wrap items-center justify-end gap-2"><span className="text-xs text-muted"><Clock className="mr-1 inline" size={14} aria-hidden />{new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.updatedAt))}</span><Button size="sm" disabled={disabled} onClick={() => onOpenInstance(item)}>进入当前浏览器</Button></div>
        </li>)}
      </ul>
    </div> : null}
    {!error && !loading && !waiting.length && !instances.length ? <p className="m-0 text-sm text-muted">当前没有临时现场。任务启动后，正在占用的临时环境会出现在这里。</p> : null}
  </section>
}
