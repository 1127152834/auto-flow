import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, Info } from '@phosphor-icons/react'
import { useMemo, useRef, useState, type ReactNode } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { createProfilesApi } from '../../profiles/api'
import { safeProjectError } from '../../projects/presentation-error'
import type { ProjectRoute } from '../../projects/types'
import { createEnvironmentApi } from '../api'
import { EnvironmentConfigurationEditor } from '../components/EnvironmentConfigurationEditor'
import { EnvironmentRenameDrawer, type EnvironmentRenameDraft } from '../components/EnvironmentRenameDrawer'

const stamp = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const facts = (items: { [key: string]: unknown }[]) => items.map(item => ({ code: String(item.code ?? ''), message: String(item.message ?? '') }))
const blockersOf = (items: { [key: string]: unknown }[]) => items.map(item => ({ state: String(item.state ?? ''), message: String(item.message ?? item.code ?? '') }))
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
  // The artboard's 实例浏览器设置 names the browser configuration the copy was taken
  // from, so the directory resolves the saved profile id instead of printing it.
  const profiles = useQuery({
    queryKey: [workspaceKey, instanceId, 'profiles'],
    queryFn: () => profilesApi.list(),
    enabled: !disabled,
    staleTime: 60_000,
  })
  const environment = detail.data?.environment
  const [editing, setEditing] = useState(false)
  const [configuring, setConfiguring] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [removal, setRemoval] = useState<{ key: string; busy: boolean; error: string | null } | null>(null)
  const [removed, setRemoved] = useState<{ name: string; detached: number; operationId: string; at: string } | null>(null)
  const scope = useRef({ workspaceKey, instanceId })
  scope.current = { workspaceKey, instanceId }
  const removalLock = useRef(false)
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
  const remove = async () => {
    if (!environment || !impact.data || !removal || removalLock.current) return
    removalLock.current = true
    setRemoval(current => current && { ...current, busy: true, error: null })
    const captured = { ...scope.current }
    const current = () => scope.current.workspaceKey === captured.workspaceKey && scope.current.instanceId === captured.instanceId
    try {
      const operation = await api.remove(environmentId, {
        impactRevision: impact.data.impactRevision,
        expectedMetadataRevision: environment.ref.metadataRevision,
        expectedContentGeneration: environment.ref.contentGeneration,
      }, removal.key, current)
      if (operation.status !== 'succeeded') {
        setRemoval(current2 => current2 && { ...current2, busy: false, error: '删除命令已被接受但尚未结束，请稍后重新打开环境页面核对结果。' })
        return
      }
      const result = operation.result as { detachedRecordCount?: unknown } | null
      const detached = typeof result?.detachedRecordCount === 'number' ? result.detachedRecordCount : 0
      setRemoved({ name: environment.name, detached, operationId: operation.operationId, at: operation.completedAt ?? operation.updatedAt })
      setConfirming(false)
      setRemoval(null)
      void cache.invalidateQueries({ queryKey: prefix })
      notify({ title: '持久环境已删除', tone: 'success', operationId: operation.operationId })
    } catch (error) {
      setRemoval(current2 => current2 && { ...current2, busy: false, error: safeProjectError(error) })
    } finally { removalLock.current = false }
  }
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
  const impactFacts = facts(impact.data?.impacts ?? [])
  const impactBlockers = blockersOf(impact.data?.blockers ?? [])
  if (removed) return <section className="grid gap-5" aria-label="删除结果">
    <h2 className="m-0 text-2xl font-semibold">删除结果</h2>
    <div className="grid gap-5 rounded-card border border-line bg-surface p-6">
      <div className="flex items-center gap-4"><span className="grid size-14 shrink-0 place-items-center rounded-full bg-sage-soft text-sage-strong"><CheckCircle size={32} aria-hidden="true" /></span><div className="min-w-0"><h3 className="m-0 text-xl font-semibold">持久环境已删除</h3><p className="m-0 mt-1 text-sm text-muted">该项目的持久环境已成功删除。</p></div></div>
      <div className="grid gap-5 border-t border-line pt-5 md:grid-cols-2">
        <section className="grid gap-2" aria-label="已删除的内容"><h4 className="m-0 text-base font-semibold">已删除的内容</h4>
          <ul className="m-0 grid list-none gap-1 p-0 text-sm">
            <li>• 持久环境「{removed.name}」及其配置与内容代次</li>
            {removed.detached > 0 ? <li>• {removed.detached} 条记录的环境关联已解除</li> : null}
            {impactFacts.filter(item => !item.code.endsWith('_KEPT')).map(item => <li key={`${item.code}-${item.message}`}>• {item.message}</li>)}
          </ul>
          <p className="m-0 text-sm text-muted">仅删除环境及其配置；关联只解除引用，记录与自动化本身保留。</p>
        </section>
        <section className="grid gap-2 md:border-l md:border-line md:pl-6" aria-label="保留的内容"><h4 className="m-0 text-base font-semibold">保留的内容</h4>
          <ul className="m-0 grid list-none gap-1 p-0 text-sm">{impactFacts.filter(item => item.code.endsWith('_KEPT')).map(item => <li key={`${item.code}-${item.message}`}>• {item.message}</li>)}</ul>
          <p className="m-0 text-sm text-muted">以上内容继续保留，可在项目中正常使用。</p>
        </section>
      </div>
      <section className="grid gap-3 rounded-control border border-line bg-surface-subtle p-4" aria-label="操作审计"><h4 className="m-0 text-base font-semibold">操作审计</h4>
        <dl className="m-0 grid gap-4 sm:grid-cols-2"><div><dt className="text-xs font-medium text-muted">操作编号</dt><dd className="m-0 mt-1 break-all text-sm">{removed.operationId}</dd></div><div><dt className="text-xs font-medium text-muted">操作时间</dt><dd className="m-0 mt-1 text-sm"><time dateTime={removed.at}>{stamp(removed.at)}</time></dd></div></dl>
      </section>
      <p className="m-0 flex items-start gap-2 rounded-control border border-line bg-surface-subtle p-4 text-sm"><Info aria-hidden="true" className="mt-0.5 shrink-0" /><span><strong className="block">删除不可撤销</strong>持久环境一经删除，不可恢复，请谨慎操作。</span></p>
      {onNavigate ? <div className="flex justify-end"><Button variant="primary" onClick={() => onNavigate({ projectId, tab: 'environments' })}>返回环境</Button></div> : null}
    </div>
  </section>
  if (detail.isLoading) return <section role="status" className="rounded-card border border-line bg-surface p-6">正在读取持久环境…</section>
  if (detail.isError || !environment) return <section role="alert" className="grid gap-3 rounded-card border border-line bg-surface p-6"><p>无法读取持久环境。{detail.error ? safeProjectError(detail.error) : ''}</p><Button onClick={() => void detail.refetch()}>重试读取</Button></section>
  const busy = Boolean(detail.data?.activeInstance)
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
          : <Button size="sm" variant="secondary" disabled={disabled || readOnly || busy || !environment.browserConfiguration || maintenance.isPending} onClick={() => maintenance.mutate()}>维护打开</Button>}
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
      <section className="grid gap-4 rounded-card border border-line bg-surface p-5" aria-label="实例浏览器设置">
        <h3 className="m-0 text-base">实例浏览器设置</h3>
        <Facts items={[
          ['浏览器配置', profiles.isError ? '浏览器配置暂时无法读取' : profileName ?? (profiles.isLoading ? '正在读取…' : '已删除或不可见')],
          ['代理', environment.browserConfiguration ? { none: '不使用代理', fixed: '固定代理', pool: '代理池' }[environment.browserConfiguration.proxy.mode] : '原身份资料缺失'],
          ['浏览器内核', environment.browserConfiguration ? `${environment.browserConfiguration.kernel.edition === 'public' ? '公开版' : '授权版'} ${environment.browserConfiguration.kernel.version}` : '无法确认'],
          ['工作副本', '每个任务创建独立副本；不会并发共用这个可变实例'],
          ['引用', `${environment.ref.contentGeneration} 个已发布内容代次`],
        ]} />
        <p className="m-0 text-sm text-muted">实例设置独立保存，修改不会影响来源模板。</p>
        {!environment.browserConfiguration ? <p role="alert">原身份资料缺失，不能根据当前模板恢复此环境。</p> : configuring ? <EnvironmentConfigurationEditor key={`${workspaceKey}:${projectId}:${environmentId}`} environment={environment} client={client} workspaceKey={workspaceKey} instanceId={instanceId} disabled={disabled || readOnly || busy} onSaved={() => { setConfiguring(false); void cache.invalidateQueries({ queryKey: prefix }) }} /> : <Button disabled={disabled || readOnly || busy} onClick={() => setConfiguring(true)}>修改实例设置</Button>}
        {busy ? <p className="m-0 text-sm text-muted">关闭当前浏览器后可修改实例设置。</p> : null}
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
    <section className="grid gap-3 rounded-card border border-line bg-surface p-5" aria-label="删除影响">
      <h3 className="m-0 text-base">删除影响</h3>
      {impact.isError ? <p role="alert" className="m-0 text-sm">无法读取删除影响。{safeProjectError(impact.error)}</p> : null}
      {impact.isLoading ? <p role="status" className="m-0 text-sm text-muted">正在读取删除影响…</p> : null}
      {impact.data ? <>
        <ul className="m-0 grid list-none gap-1 p-0 text-sm">{impactFacts.map(item => <li key={`${item.code}-${item.message}`}>• {item.message}</li>)}</ul>
        {impactBlockers.length
          ? <ul role="status" className="m-0 grid list-none gap-1 p-0 text-sm text-warning">{impactBlockers.map(item => <li key={`${item.state}-${item.message}`}>• 删除被占用阻止：{item.message}（{item.state}）</li>)}</ul>
          : <p className="m-0 text-sm">当前没有活动占用阻止删除。</p>}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {impactBlockers.length ? <span className="mr-auto text-sm text-muted">先结束上面的占用才能删除。</span> : null}
          <Button variant="danger" size="sm" disabled={disabled || readOnly || impactBlockers.length > 0 || Boolean(removal?.busy)} onClick={() => { setConfirming(true); setRemoval({ key: crypto.randomUUID(), busy: false, error: null }) }}>删除环境</Button>
        </div>
      </> : null}
    </section>
    <AlertDialog open={confirming} onOpenChange={open => { if (!open && !removal?.busy) setConfirming(false) }}><AlertDialogContent>
      <AlertDialogTitle>删除持久环境</AlertDialogTitle>
      <AlertDialogDescription>删除不可撤销。删除后该环境不再可用于后续任务，记录、历史任务与全局资源保留。</AlertDialogDescription>
      <ul className="m-0 grid list-none gap-1 p-0 text-sm">{impactFacts.map(item => <li key={`${item.code}-${item.message}`}>• {item.message}</li>)}</ul>
      {removal?.error ? <p role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm">{removal.error}</p> : null}
      <div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={removal?.busy}>取消</Button></AlertDialogCancel><Button variant="danger" disabled={Boolean(removal?.busy)} onClick={() => void remove()}>{removal?.busy ? '正在删除…' : '删除环境'}</Button></div>
    </AlertDialogContent></AlertDialog>
  </section>
}
