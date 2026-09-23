import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { notify, Toaster } from '../../../shared/components/Toaster'
import { createProjectsApi, isDefinitiveProjectFailure } from '../api'
import { safeProjectError } from '../presentation-error'
import { toProjectCreate, toProjectPatch, type ProjectFormValues } from '../form-schema'
import { projectKeys, useProject, useProjectCleanupResidues, useProjectDirectory, useProjectOverview } from '../hooks'
import type { ProjectCreate, ProjectListConditions, ProjectPatch, ProjectRoute, ProjectSummary, ProjectView } from '../types'
import { ProjectFormDialog } from '../components/ProjectFormDialog'
import { ProjectLifecycleDialog, type LifecycleSubmit } from '../components/ProjectLifecycleDialog'
import { reportedCleanupResidue } from '../cleanup-residue'
import type { ProjectLifecycleChoice } from '../components/ProjectCard'
import { ProjectDirectoryPage } from './ProjectDirectoryPage'
import { ProjectOverviewPage } from './ProjectOverviewPage'
import { DataTableDirectoryPage } from '../../project-data/pages/DataTableDirectoryPage'
import { createProjectDataApi } from '../../project-data/api'
import { DataTableDetailPage } from '../../project-data/pages/DataTableDetailPage'
import { AutomationDirectoryPage } from '../../project-automations/pages/AutomationDirectoryPage'
import { AutomationDetailPage } from '../../project-automations/pages/AutomationDetailPage'
import { createAutomationApi } from '../../project-automations/api'
import { RunDirectoryPage } from '../../project-runs/pages/RunDirectoryPage'
import { StatisticsDrillPage } from '../../project-runs/pages/StatisticsDrillPage'
import { BatchDetailPage } from '../../project-runs/pages/BatchDetailPage'
import { TaskDetailPage } from '../../project-runs/pages/TaskDetailPage'
import { ManualDetailPage } from '../../project-runs/pages/ManualDetailPage'
import { StatisticsPage } from './StatisticsPage'
import { EnvironmentWorkspacePage } from '../../environments/pages/EnvironmentWorkspacePage'
import { EnvironmentDetailPage } from '../../environments/pages/EnvironmentDetailPage'

export type ProjectsWorkspaceProps = {
  route: ProjectRoute
  workspaceKey: string
  instanceId: string
  client: StreamingApiClient
  disabled: boolean
  onNavigate(route: ProjectRoute, options?: { replace?: boolean }): void
  registerLeaveGuard(guard: (() => Promise<boolean>) | null): void
}

const defaultConditions: ProjectListConditions = { query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 50 }
const storageKey = (workspaceKey: string) => `autoflow:projects-ui:${encodeURIComponent(workspaceKey)}`

function readConditions(workspaceKey: string): ProjectListConditions {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}') as Partial<ProjectListConditions>
    return {
      query: typeof value.query === 'string' ? value.query : '',
      lifecycle: ['active', 'archived', 'all'].includes(value.lifecycle ?? '') ? value.lifecycle! : 'active',
      sort: ['name', '-name', 'updatedAt', '-updatedAt', 'lastOpenedAt', '-lastOpenedAt'].includes(value.sort ?? '') ? value.sort! : '-lastOpenedAt',
      page: Number.isSafeInteger(value.page) && value.page! > 0 && value.page! <= 2147483647 ? value.page! : 1,
      pageSize: 50,
    }
  } catch { return defaultConditions }
}
function writeConditions(workspaceKey: string, value: ProjectListConditions) {
  try { const current = JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}'); sessionStorage.setItem(storageKey(workspaceKey), JSON.stringify({ ...current, ...value })) } catch { /* unavailable storage */ }
}
type DirectoryMode = 'recent' | 'all'
const recentConditions: ProjectListConditions = { query: '', lifecycle: 'active', sort: '-lastOpenedAt', page: 1, pageSize: 6 }
function readMode(workspaceKey: string): DirectoryMode {
  try { return JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}').mode === 'all' ? 'all' : 'recent' } catch { return 'recent' }
}
function writeMode(workspaceKey: string, mode: DirectoryMode) {
  try { const current = JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}'); sessionStorage.setItem(storageKey(workspaceKey), JSON.stringify({ ...current, mode })) } catch { /* unavailable storage */ }
}
function readScrollTop(workspaceKey: string, mode: DirectoryMode) {
  try { const value = JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}'); const scroll = value.scrollPositions?.[mode] ?? (mode === 'all' ? value.scrollTop : 0); return typeof scroll === 'number' && Number.isFinite(scroll) ? Math.max(0, scroll) : 0 } catch { return 0 }
}
function writeScrollTop(workspaceKey: string, mode: DirectoryMode, scrollTop: number) {
  try { const current = JSON.parse(sessionStorage.getItem(storageKey(workspaceKey)) ?? '{}'); sessionStorage.setItem(storageKey(workspaceKey), JSON.stringify({ ...current, scrollPositions: { ...current.scrollPositions, [mode]: scrollTop } })) } catch { /* unavailable storage */ }
}
export function resetProjectUiState(workspaceKey: string) {
  try { sessionStorage.removeItem(storageKey(workspaceKey)) } catch { /* unavailable storage */ }
}

type Editor = { project: ProjectView | null; draftSession: string }
type PendingCommand = { key: string; body: ProjectCreate; kind: 'create' } | { key: string; body: ProjectPatch; kind: 'patch'; projectId: string }

export function ProjectsWorkspace({ route, workspaceKey, instanceId, client, disabled, onNavigate, registerLeaveGuard }: ProjectsWorkspaceProps) {
  const api = useMemo(() => createProjectsApi(client), [client])
  const cache = useQueryClient()
  const tableApi = useMemo(() => createProjectDataApi(client, route.projectId ?? ''), [client, route.projectId])
  // Observe the detail page's existing query; route/instance identity prevents stale breadcrumbs.
  const tableContext = useQuery({
    queryKey: [workspaceKey, instanceId, 'project-data', route.projectId, 'table', route.tableId, 'view'],
    queryFn: ({ signal }) => tableApi.get(route.tableId!, signal),
    enabled: Boolean(route.projectId && route.tableId && route.tab === 'data'),
  })
  const automationApi = useMemo(() => createAutomationApi(client, route.projectId ?? ''), [client, route.projectId])
  const automationContext = useQuery({
    queryKey: [workspaceKey, instanceId, 'automations', route.projectId, 'detail', route.automationId],
    queryFn: ({ signal }) => automationApi.get(route.automationId!, signal),
    enabled: Boolean(route.projectId && route.automationId && route.tab === 'automations') && !disabled,
  })
  const [conditions, setConditionsState] = useState(() => readConditions(workspaceKey))
  const [mode, setModeState] = useState<DirectoryMode>(() => readMode(workspaceKey))
  const [scrollTop, setScrollTop] = useState(() => readScrollTop(workspaceKey, readMode(workspaceKey)))
  const [editor, setEditor] = useState<Editor | null>(null)
  // One confirmation session owns one command identity: a lost response is
  // replayed under the same key instead of archiving or deleting twice.
  const [lifecycle, setLifecycle] = useState<{ project: ProjectView; action: ProjectLifecycleChoice; key: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [recoveryPending, setRecoveryPending] = useState(false)
  const dataGuard = useRef<(() => Promise<boolean>) | null>(null)
  const registerDataGuard = useCallback((next: (() => Promise<boolean>) | null) => { dataGuard.current = next }, [])
  const [retainedProject, setRetainedProject] = useState<{ workspaceKey: string; project: ProjectView } | null>(null)
  const dirtyRef = useRef(false)
  const savingRef = useRef(false)
  const [leaveOpen, setLeaveOpen] = useState(false)
  const [openError, setOpenError] = useState<{ project: ProjectSummary; message: string } | null>(null)
  const leaveResolver = useRef<((allowed: boolean) => void) | null>(null)
  const pending = useRef<PendingCommand | null>(null)
  const openTicket = useRef(0)
  const commandTicket = useRef(0)
  const commandBusy = useRef(false)
  const mounted = useRef(false)
  const scope = useRef({ workspaceKey, instanceId, editor: editor?.draftSession })
  scope.current = { workspaceKey, instanceId, editor: editor?.draftSession }

  const directory = useProjectDirectory(api, workspaceKey, instanceId, conditions, mode === 'all')
  const recent = useProjectDirectory(api, workspaceKey, instanceId, recentConditions, mode === 'recent')
  // Only projects that are still deleting can carry cleanup residue; they live
  // in the archive directory until the residue is gone.
  const lifecycleResidue = useProjectCleanupResidues(api, workspaceKey, instanceId, useMemo(() => [...(directory.data?.items ?? []), ...(recent.data?.items ?? [])].filter(item => item.lifecycleState === 'deleting').map(item => item.projectId), [directory.data, recent.data]))
  const detail = useProject(api, workspaceKey, instanceId, route.projectId)
  const overview = useProjectOverview(api, workspaceKey, instanceId, route.projectId, route.tab === 'overview')
  useLayoutEffect(() => { if (detail.data) setRetainedProject({ workspaceKey, project: detail.data }) }, [detail.data, workspaceKey])

  useEffect(() => { setConditionsState(readConditions(workspaceKey)); setModeState(readMode(workspaceKey)); setScrollTop(readScrollTop(workspaceKey, readMode(workspaceKey))); setEditor(null); dirtyRef.current = false; pending.current = null }, [workspaceKey])
  const setConditions = (value: ProjectListConditions) => { setScrollTop(0); writeScrollTop(workspaceKey, 'all', 0); setConditionsState(value); writeConditions(workspaceKey, value) }
  const setMode = (value: DirectoryMode) => { setModeState(value); writeMode(workspaceKey, value); setScrollTop(readScrollTop(workspaceKey, value)) }
  useEffect(() => {
    if (mode !== 'all' || !directory.data || directory.isPlaceholderData) return
    const lastPage = Math.max(1, Math.ceil(directory.data.total / conditions.pageSize))
    if (conditions.page > lastPage) {
      const next = { ...conditions, page: lastPage }
      setConditionsState(next); writeConditions(workspaceKey, next); setScrollTop(0); writeScrollTop(workspaceKey, 'all', 0)
    }
  }, [directory.data, directory.isPlaceholderData, conditions, workspaceKey, mode])
  useEffect(() => {
    commandTicket.current++; commandBusy.current = false; savingRef.current = false
    setSaving(false); setRecoveryPending(Boolean(pending.current))
  }, [instanceId])
  useEffect(() => { openTicket.current++ }, [route.projectId])

  const guard = useCallback(async () => {
    if (savingRef.current) return false
    if (!dirtyRef.current && !pending.current) return await dataGuard.current?.() ?? true
    if (leaveResolver.current) return false
    setLeaveOpen(true)
    const allowed = await new Promise<boolean>(resolve => { leaveResolver.current = resolve })
    return allowed && (await dataGuard.current?.() ?? true)
  }, [])
  useEffect(() => { registerLeaveGuard(guard); return () => registerLeaveGuard(null) }, [guard, registerLeaveGuard])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; openTicket.current++; commandTicket.current++; leaveResolver.current?.(false) }
  }, [])

  const finishLeave = (allowed: boolean) => {
    const resolve = leaveResolver.current; leaveResolver.current = null; setLeaveOpen(false)
    if (allowed) { dirtyRef.current = false; setEditor(null); pending.current = null; setRecoveryPending(false) }
    resolve?.(allowed)
  }

  const submit = async (values: ProjectFormValues, revision: number | null) => {
    if (disabled || commandBusy.current || !editor || (editor.project && editor.project.lifecycleState !== 'active')) return false
    commandBusy.current = true
    const attempt = ++commandTicket.current
    const captured = { ...scope.current }
    const isCurrent = () => mounted.current && attempt === commandTicket.current && scope.current.workspaceKey === captured.workspaceKey && scope.current.instanceId === captured.instanceId && scope.current.editor === captured.editor
    const resuming = Boolean(pending.current)
    if (!pending.current) pending.current = editor.project
      ? { key: crypto.randomUUID(), body: toProjectPatch(values, revision!), kind: 'patch', projectId: editor.project.projectId }
      : { key: crypto.randomUUID(), body: toProjectCreate(values), kind: 'create' }
    const command = pending.current
    let saved: ProjectView
    try {
      saved = command.kind === 'create'
        ? resuming ? await api.resumeCreate(command.body, command.key) : await api.create(command.body, command.key)
        : resuming ? await api.resumePatch(command.projectId, command.body, command.key) : await api.patch(command.projectId, command.body, command.key)
    } catch (error) {
      if (!isCurrent()) return false
      if (isDefinitiveProjectFailure(error)) { pending.current = null; setRecoveryPending(false) }
      else setRecoveryPending(true)
      throw error
    } finally {
      if (attempt === commandTicket.current) commandBusy.current = false
    }
    if (!isCurrent()) return false
    pending.current = null
    setRecoveryPending(false)
    cache.setQueryData(projectKeys.detail(workspaceKey, instanceId, saved.projectId), saved)
    void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'projects'] })
    void cache.invalidateQueries({ queryKey: projectKeys.overview(workspaceKey, instanceId, saved.projectId) })
    dirtyRef.current = false; savingRef.current = false
    setSaving(false); setEditor(null)
    leaveResolver.current?.(true); leaveResolver.current = null; setLeaveOpen(false)
    notify({ title: command.kind === 'create' ? '项目已创建' : '项目已更新', tone: 'success', operationId: JSON.stringify([workspaceKey, command.key]) })
    if (command.kind === 'create') onNavigate({ projectId: saved.projectId, tab: 'overview' })
  }

  const startLifecycle = (project: ProjectSummary, action: ProjectLifecycleChoice) => setLifecycle({ project: project as ProjectView, action, key: crypto.randomUUID() })

  const lifecycleImpact = async () => {
    if (!lifecycle || lifecycle.action === 'restore') throw new Error('缺少生命周期动作')
    return api.lifecycleImpact(lifecycle.project.projectId, lifecycle.action)
  }

  const lifecycleSubmit = async (values: LifecycleSubmit) => {
    if (!lifecycle) throw new Error('缺少生命周期动作')
    const { projectId } = lifecycle.project
    const operation = lifecycle.action === 'archive'
      ? await api.archive(projectId, { impactRevision: values.impactRevision, expectedManagementRevision: values.expectedManagementRevision }, lifecycle.key)
      : await api.remove(projectId, values, lifecycle.key)
    void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'projects'] })
    void cache.invalidateQueries({ queryKey: projectKeys.detail(workspaceKey, instanceId, projectId) })
    notify({
      title: operation.status === 'failed' ? '归档未完成，请核对残留' : lifecycle.action === 'archive' ? '归档命令已接受' : '删除命令已接受',
      tone: operation.status === 'failed' ? 'error' : 'success',
      operationId: operation.operationId,
    })
    if (lifecycle.action === 'delete' && operation.status === 'succeeded' && route.projectId === projectId) onNavigate({ tab: 'overview' })
    return operation
  }

  const restoreProject = async (project: ProjectSummary) => {
    try {
      const operation = await api.restore(project.projectId, { expectedManagementRevision: (project as ProjectView).managementRevision })
      void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'projects'] })
      void cache.invalidateQueries({ queryKey: projectKeys.detail(workspaceKey, instanceId, project.projectId) })
      notify({ title: operation.status === 'succeeded' ? '项目已恢复' : '恢复命令已接受', tone: 'success', operationId: operation.operationId })
    } catch (error) {
      notify({ title: safeProjectError(error), tone: 'error' })
    }
  }

  const selectLifecycle = (project: ProjectSummary, action: ProjectLifecycleChoice) => {
    if (action === 'restore') void restoreProject(project)
    else startLifecycle(project, action)
  }

  const openProject = async (project: ProjectSummary) => {
    const ticket = ++openTicket.current
    const captured = `${workspaceKey}:${instanceId}`
    setOpenError(null)
    let result
    try { result = await api.open(project.projectId) }
    catch (error) {
      if (mounted.current && ticket === openTicket.current && `${scope.current.workspaceKey}:${scope.current.instanceId}` === captured) setOpenError({ project, message: safeProjectError(error) })
      return
    }
    if (!mounted.current || ticket !== openTicket.current || `${scope.current.workspaceKey}:${scope.current.instanceId}` !== captured) return
    cache.setQueryData(projectKeys.detail(workspaceKey, instanceId, project.projectId), result.project)
    void cache.invalidateQueries({ queryKey: [workspaceKey, instanceId, 'projects'] })
    onNavigate({ projectId: project.projectId, tab: 'overview' })
  }

  const definitiveReadFailure = detail.error instanceof ApiClientError && detail.error.status >= 400 && detail.error.status < 500 && detail.error.status !== 408
  const project = detail.data ?? (!definitiveReadFailure && retainedProject?.workspaceKey === workspaceKey && retainedProject.project.projectId === route.projectId ? retainedProject.project : undefined)
  const editorProjectId = editor?.project?.projectId
  const openStudio = (workflowId?: string) => {
    if (!project || disabled || project.lifecycleState !== 'active') return
    if (!window.autoflow?.openAutomationStudio) { notify({ title: '当前环境无法打开工作流工作台', tone: 'error' }); return }
    void window.autoflow.openAutomationStudio({ workspaceKey, instanceId, projectId: project.projectId, ...(workflowId ? { workflowId } : {}) }).catch(error => notify({ title: safeProjectError(error), tone: 'error' }))
  }
  return <>
    <Toaster />
    {route.projectId && route.tab === 'overview' && overview.isPending ? <p role="status" className="mx-auto max-w-7xl px-6 text-sm text-muted">正在加载概览…</p> : null}
    {route.projectId && route.tab === 'overview' && overview.isError ? <div role="alert" className="mx-auto flex max-w-7xl items-center gap-3 px-6 pt-4 text-sm text-danger"><span>{safeProjectError(overview.error)}</span><Button size="sm" disabled={overview.isFetching} onClick={() => void overview.refetch()}>重试概览</Button></div> : null}
    {openError ? <div className="fixed bottom-5 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-control border border-danger/30 bg-surface px-4 py-3 shadow-lg" role="alert"><span>{openError.message}</span><Button size="sm" onClick={() => void openProject(openError.project)}>重试</Button></div> : null}
    {route.projectId && project ? <ProjectOverviewPage overview={overview.data ?? null} overviewError={overview.isError ? safeProjectError(overview.error) : null} onOpenResource={target => onNavigate({ ...target, projectId: project.projectId })} detailContext={route.automationId || route.automationCreate ? { name: route.automationCreate ? '新建自动化' : automationContext.data?.name ?? '自动化配置', label: '返回自动化目录', onBack: () => onNavigate({ projectId: project.projectId, tab: 'automations' }) } : route.tab === 'runs' && (route.batchId || route.taskId || route.manualItemId || route.runFrozen) ? { name: route.manualItemId ? '人工事项' : route.taskId ? '任务详情' : route.runFrozen ? '任务' : '批次详情', label: route.runFrozen ? '返回统计' : route.manualItemId ? '返回等待人工' : '返回运行记录', onBack: () => onNavigate(route.runFrozen ? { projectId: project.projectId, tab: 'statistics' } : { projectId: project.projectId, tab: 'runs', ...(route.manualItemId ? { runView: 'manual' } : { runView: 'batches' }) }) } : route.tab === 'environments' && route.environmentId ? { name: '环境详情', label: '返回环境', onBack: () => onNavigate({ projectId: project.projectId, tab: 'environments' }) } : undefined} tableBackLabel={route.record ? "返回记录列表" : "返回数据表"} onTableBack={() => onNavigate({ projectId: project.projectId, tab: "data", ...(route.record ? { tableId: route.tableId, dataTab: "records" } : {}) })} tableName={tableContext.data?.name} tableDetail={Boolean(route.tableId)} project={project} tab={route.tab} disabled={disabled} onBack={() => onNavigate({ tab: 'overview' })} onEdit={() => { if (!disabled && project.lifecycleState === 'active') setEditor({ project, draftSession: `edit:${project.projectId}:${Date.now()}` }) }} onTabChange={tab => onNavigate({ projectId: project.projectId, tab })}>
      {route.tab === 'automations' ? route.automationId || route.automationCreate
        ? <AutomationDetailPage projectDefaults={project.defaultResources} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} automationId={route.automationId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} registerLeaveGuard={registerDataGuard} onOpenStudio={openStudio} onBatchCreated={batchId => onNavigate({ projectId: project.projectId, tab: 'runs', runView: 'batches', batchId })} onCreated={automationId => onNavigate({ projectId: project.projectId, tab: 'automations', automationId }, { replace: true })} onDeleted={() => onNavigate({ projectId: project.projectId, tab: 'automations' })} />
        : <AutomationDirectoryPage onOpenStudio={() => openStudio()} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onOpen={automationId => onNavigate({ projectId: project.projectId, tab: 'automations', automationId })} onCreate={() => onNavigate({ projectId: project.projectId, tab: 'automations', automationCreate: true })} />
        : route.tab === 'runs' ? route.manualItemId
        ? <ManualDetailPage key={`${workspaceKey}:${instanceId}:${project.projectId}:${route.manualItemId}`} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} manualItemId={route.manualItemId}/>
        : route.taskId ? <TaskDetailPage key={`${workspaceKey}:${instanceId}:${project.projectId}:${route.taskId}`} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} taskId={route.taskId} tab={route.taskTab ?? 'logs'}/>
        : route.batchId ? <BatchDetailPage workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} batchId={route.batchId}/>
        : route.runFrozen ? <StatisticsDrillPage key={`${workspaceKey}:${instanceId}:${project.projectId}:${route.runFrozen.resultSetId}`} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} frozen={route.runFrozen} onNavigate={target => onNavigate({ projectId: project.projectId, ...target })}/>
        : <RunDirectoryPage workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} view={route.runView ?? 'batches'}/>
        : route.tab === 'data' ? route.tableId
        ? <DataTableDetailPage key={`${workspaceKey}:${project.projectId}:${route.tableId}`} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} tableId={route.tableId} tab={route.dataTab ?? 'records'} record={route.record} onRecordNavigate={(record, options) => onNavigate({ ...route, dataTab: 'records', record }, options)} client={client} disabled={disabled} readonly={project.lifecycleState !== 'active'} registerLeaveGuard={registerDataGuard} onBack={() => onNavigate({ projectId: project.projectId, tab: 'data' })} onTabChange={dataTab => onNavigate({ ...route, dataTab, record: undefined })} />
        : <DataTableDirectoryPage workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} readonly={project.lifecycleState !== 'active'} registerLeaveGuard={registerDataGuard} onOpen={tableId => onNavigate({ projectId: project.projectId, tab: 'data', tableId, dataTab: 'records' })} />
        : route.tab === 'statistics' ? <StatisticsPage key={`${workspaceKey}:${instanceId}:${project.projectId}`} workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} client={client} disabled={disabled} onOpenRuns={() => onNavigate({ projectId: project.projectId, tab: 'runs', runView: 'batches' })} onOpenFailures={frozen => onNavigate({ projectId: project.projectId, tab: 'runs', runFrozen: frozen })} />
        : route.tab === 'environments' ? route.environmentId
        ? <EnvironmentDetailPage workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} environmentId={route.environmentId} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} />
        : <EnvironmentWorkspacePage workspaceKey={workspaceKey} instanceId={instanceId} projectId={project.projectId} project={project} client={client} disabled={disabled} readOnly={project.lifecycleState !== 'active'} onNavigate={onNavigate} />
        : undefined}
      </ProjectOverviewPage>
      : route.projectId && detail.isLoading ? <main className="p-6" role="status">正在加载项目…</main>
      : route.projectId && detail.isError ? <main className="grid gap-3 p-6" role="alert"><p>无法加载项目。</p><div className="flex gap-2"><Button onClick={() => void detail.refetch()}>重试</Button><Button variant="ghost" onClick={() => onNavigate({ tab: 'overview' })}>返回项目目录</Button></div></main>
      : <ProjectDirectoryPage key={mode} mode={mode} onModeChange={setMode} recentItems={recent.data?.items} recentLoading={recent.isLoading} recentError={recent.isError ? '刷新最近项目失败' : null} page={directory.data} conditions={conditions} loading={directory.isLoading} refreshing={mode === 'recent' ? recent.isFetching : directory.isFetching} disabled={disabled} error={directory.isError ? '刷新项目失败' : null} initialScrollTop={scrollTop} onScrollTopChange={value => { setScrollTop(value); writeScrollTop(workspaceKey, mode, value) }} onConditionsChange={setConditions} onRefresh={() => void (mode === 'recent' ? recent.refetch() : directory.refetch())} cleanupResidue={lifecycleResidue} onCreate={() => setEditor({ project: null, draftSession: `create:${Date.now()}` })} onOpen={project => void openProject(project)} onEdit={project => setEditor({ project: project as ProjectView, draftSession: `edit:${project.projectId}:${Date.now()}` })} onLifecycle={selectLifecycle} />}
    <ProjectFormDialog open={Boolean(editor)} project={editor?.project ?? null} draftSession={editor?.draftSession ?? 'closed'} submissionEpoch={`${instanceId}:${editor?.draftSession ?? 'closed'}`} recoveryPending={recoveryPending} disabled={disabled} onOpenChange={open => { if (!open) setEditor(null) }} onSubmit={submit} onLoadLatest={editorProjectId ? () => api.get(editorProjectId) : undefined} onDirtyChange={value => { dirtyRef.current = value }} onSavingChange={value => { savingRef.current = value; setSaving(value) }} onRequestClose={guard} />
    {lifecycle && lifecycle.action !== 'restore' ? <ProjectLifecycleDialog
      open
      action={lifecycle.action}
      project={lifecycle.project}
      disabled={disabled}
      onOpenChange={open => { if (!open) setLifecycle(null) }}
      onLoadImpact={lifecycleImpact}
      onLoadResidue={() => api.operations(lifecycle.project.projectId).then(reportedCleanupResidue)}
      onSubmit={lifecycleSubmit}
      onFinished={operation => { if (operation.status === 'succeeded' || operation.status === 'failed') setLifecycle(null) }}
    /> : null}
    <AlertDialog open={leaveOpen} onOpenChange={open => { if (!open && !savingRef.current) finishLeave(false) }}><AlertDialogContent><AlertDialogTitle>保存项目修改后离开？</AlertDialogTitle><AlertDialogDescription>{recoveryPending ? '上次保存结果尚未确认。请先核对，避免遗失操作结果。' : '可以先保存修改、放弃本次修改，或继续编辑。'}</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={saving} onClick={() => finishLeave(false)}>继续编辑</Button></AlertDialogCancel><Button variant="ghost" disabled={saving || recoveryPending} onClick={() => finishLeave(true)}>放弃修改</Button><AlertDialogAction asChild><Button variant="primary" disabled={saving || disabled} onClick={event => { event.preventDefault(); document.querySelector<HTMLFormElement>('#project-form')?.requestSubmit() }}>{recoveryPending ? '核对后离开' : '保存后离开'}</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
