import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { createProfilesApi } from '../../profiles/api'
import { safeProjectError } from '../../projects/presentation-error'
import type { ProjectRoute } from '../../projects/types'
import { createEnvironmentApi } from '../api'
import { EnvironmentRenameDrawer, type EnvironmentRenameDraft } from '../components/EnvironmentRenameDrawer'

const stamp = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const environmentStates: Record<string, string> = { ready: '就绪', unavailable: '不可用', deleting: '删除中', deleted: '已删除' }
const instanceStates: Record<string, string> = { reserved: '已预约', starting: '启动中', active: '自动运行', closing: '停止中', saving: '保存中', cleaning: '清理中', retained_unsaved: '待处理保存', closed: '已结束', cleaned: '已清理', failed: '启动失败' }
const sources: Record<string, string> = { newFromProfile: '按浏览器配置新建', fixedEnvironment: '来自已有持久环境', inputEnvironment: '来自记录关联的环境' }
const statePill = (state: string) => <span className={`inline-flex items-center rounded-control border px-2 py-0.5 text-xs ${state === 'ready' ? 'border-sage/40 bg-sage-soft text-sage-strong' : state === 'unavailable' ? 'border-warning/40 bg-warning-soft text-warning' : 'border-line bg-surface-subtle text-muted'}`}>{environmentStates[state] ?? state}</span>

function Facts({ items }: { items: [string, ReactNode][] }) {
  return <dl className="m-0 grid gap-4 sm:grid-cols-2">
    {items.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-xs font-medium text-muted">{label}</dt><dd className="m-0 mt-1 min-w-0 text-sm [overflow-wrap:anywhere]">{value}</dd></div>)}
  </dl>
}

export function EnvironmentDetailPage({ workspaceKey, instanceId, projectId, environmentId, client, disabled, readOnly, onNavigate }: {
  workspaceKey: string
  instanceId: string
  projectId: string
  environmentId: string
  client: StreamingApiClient
  disabled: boolean
  readOnly: boolean
  onNavigate?(route: ProjectRoute): void
}) {
  const api = useMemo(() => createEnvironmentApi(client, projectId), [client, projectId])
  const profilesApi = useMemo(() => createProfilesApi(client), [client])
  const cache = useQueryClient()
  const prefix = [workspaceKey, instanceId, 'environments', projectId] as const
  const detail = useQuery({
    queryKey: [...prefix, 'detail', environmentId],
    queryFn: ({ signal }) => api.get(environmentId, signal),
    enabled: !disabled,
  })
  const impact = useQuery({
    queryKey: [...prefix, 'impact', environmentId],
    queryFn: ({ signal }) => api.impact(environmentId, signal),
    enabled: !disabled,
  })
  // The artboard's 保存时的资源快照 names the browser configuration the copy was taken
  // from, so the directory resolves the saved profile id instead of printing it.
  const profiles = useQuery({
    queryKey: [workspaceKey, instanceId, 'profiles'],
    queryFn: () => profilesApi.list(),
    enabled: !disabled,
    staleTime: 60_000,
  })
  const environment = detail.data?.environment
  const [editing, setEditing] = useState(false)
  const save = useMutation({
    mutationFn: (draft: EnvironmentRenameDraft) => api.patch(environmentId, {
      expectedMetadataRevision: environment!.ref.metadataRevision,
      name: draft.name,
      notes: draft.notes,
    }, crypto.randomUUID()),
    onSuccess: () => {
      notify({ title: '环境名称已更新', tone: 'success' })
      setEditing(false)
      void cache.invalidateQueries({ queryKey: prefix })
    },
  })
  const maintenance = useMutation({
    mutationFn: () => api.startMaintenance(environmentId, environment!.ref.contentGeneration, crypto.randomUUID()),
    onSuccess: () => {
      notify({ title: '已打开维护副本', tone: 'success' })
      void cache.invalidateQueries({ queryKey: prefix })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  const openBrowser = useMutation({
    mutationFn: () => api.openInstance(detail.data!.activeInstance!.instanceId, detail.data!.activeInstance!.instanceUseGeneration, crypto.randomUUID()),
    onSuccess: () => notify({ title: '已请求进入当前浏览器', tone: 'success' }),
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  const discard = useMutation({
    mutationFn: () => api.discardMaintenance(environmentId, {
      maintenanceOperationId: detail.data!.activeInstance!.maintenanceOperationId!,
      instanceId: detail.data!.activeInstance!.instanceId,
    }, crypto.randomUUID()),
    onSuccess: () => {
      notify({ title: '已放弃维护副本', tone: 'success' })
      void cache.invalidateQueries({ queryKey: prefix })
    },
    onError: error => notify({ title: safeProjectError(error), tone: 'error' }),
  })
  if (detail.isLoading) return <section role="status" className="rounded-card border border-line bg-surface p-6">正在读取持久环境…</section>
  if (detail.isError || !environment) return <section role="alert" className="grid gap-3 rounded-card border border-line bg-surface p-6"><p>无法读取持久环境。{detail.error ? safeProjectError(detail.error) : ''}</p><Button onClick={() => void detail.refetch()}>重试读取</Button></section>
  const busy = Boolean(detail.data?.activeInstance)
  const blockers = impact.data?.blockers ?? []
  const profileName = profiles.data?.items.find(item => item.id === environment.profileId)?.name
  const sourceTask = environment.createdFromTaskId
  return <section className="grid gap-5" aria-label="持久环境详情">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="m-0 text-2xl font-semibold [overflow-wrap:anywhere]">{environment.name}</h2>
        <p className="mb-0 mt-2 text-sm text-muted">稳定环境身份不会随名称改变。后续任务只把它当作来源，每个任务仍使用独立工作副本。</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={disabled || readOnly} onClick={() => setEditing(true)}>重命名</Button>
        {busy ? <Button size="sm" disabled={disabled || readOnly || openBrowser.isPending} onClick={() => openBrowser.mutate()}>进入当前浏览器</Button> : null}
        {busy && detail.data?.activeInstance?.maintenanceOperationId
          ? <Button size="sm" variant="secondary" disabled={disabled || readOnly || discard.isPending} onClick={() => discard.mutate()}>放弃维护</Button>
          : <Button size="sm" variant="secondary" disabled={disabled || readOnly || busy || maintenance.isPending} onClick={() => maintenance.mutate()}>维护打开</Button>}
      </div>
    </header>
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-label="基本信息">
        <h3 className="m-0 text-base">基本信息</h3>
        <Facts items={[
          ['状态', statePill(environment.state)],
          ['保存时间', <time dateTime={environment.createdAt}>{stamp(environment.createdAt)}</time>],
          ['来源任务', sourceTask
            ? (onNavigate ? <Button variant="ghost" className="h-auto p-0 text-sm text-clay" onClick={() => onNavigate({ projectId, tab: 'runs', runView: 'tasks', taskId: sourceTask, taskTab: 'logs' })}>查看来源任务</Button> : '已记录')
            : '未记录来源任务'],
          ['创建来源', sources[environment.createdFromSource ?? ''] ?? '保存的环境副本'],
          ['输入记录', detail.data?.linkedRecordCount ? `${detail.data.linkedRecordCount} 条记录仍关联此环境` : '没有记录关联此环境'],
          ['现场实例', detail.data?.activeInstance ? `占用中 · ${instanceStates[detail.data.activeInstance.state] ?? detail.data.activeInstance.state}` : '未占用'],
        ]} />
        <p className="m-0 text-sm">备注：{environment.notes || '无备注'}</p>
        <p className="m-0 rounded-control border border-line bg-subtle p-3 text-sm text-muted">保存原因：工作流结束节点明确声明保存。任务结束后使用过的工作副本会被关闭并清理，只有这里保留的副本会继续存在。</p>
      </section>
      <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-label="保存时的资源快照">
        <h3 className="m-0 text-base">保存时的资源快照</h3>
        <Facts items={[
          ['浏览器配置', profiles.isError ? '浏览器配置暂时无法读取' : profileName ?? (profiles.isLoading ? '正在读取…' : '已删除或不可见')],
          ['代理', '跟随保存时的浏览器配置'],
          ['工作副本', '每个任务创建独立副本；不会并发共用这个可变实例'],
          ['引用', `${environment.ref.contentGeneration} 个已发布内容代次`],
        ]} />
        <p className="m-0 text-sm text-muted">保存时截图不属于本阶段已实现的能力，这里不展示占位图。</p>
      </section>
    </div>
    <p className="m-0 text-xs text-muted">技术信息：内容代次 {environment.ref.contentGeneration} · 元数据修订 {environment.ref.metadataRevision}</p>
    <EnvironmentRenameDrawer
      open={editing}
      initialName={environment.name}
      initialNotes={environment.notes}
      saving={save.isPending}
      disabled={disabled || readOnly}
      error={save.isError ? safeProjectError(save.error) : undefined}
      onOpenChange={setEditing}
      onSubmit={draft => save.mutate(draft)}
    />
    <section className="grid gap-2 rounded-card border border-line bg-surface p-5" aria-label="删除影响">
      <h3 className="m-0 text-base">删除影响</h3>
      {impact.isError ? <p role="alert" className="m-0 text-sm">无法读取删除影响。{safeProjectError(impact.error)}</p> : null}
      {impact.data ? <>
        <p className="m-0 text-sm text-muted">当前有 {impact.data.impacts.length} 条记录关联。删除命令属于后续关闭阶段；这里只展示已批准的影响事实。</p>
        {blockers.length ? <p role="status" className="m-0 text-sm text-warning">删除被占用阻止：{blockers.map(item => String(item.state ?? item.kind)).join('；')}</p> : <p className="m-0 text-sm">当前没有活动占用阻止删除。</p>}
      </> : null}
    </section>
  </section>
}
