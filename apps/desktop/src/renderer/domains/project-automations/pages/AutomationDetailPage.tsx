import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Pagination } from '../../../shared/components/ui/pagination'
import { createAutomationApi } from '../api'
import { AutomationEditor } from '../components/AutomationEditor'
import { InputPlanEditor } from '../components/InputPlanEditor'
import { automationToForm, emptyAutomationForm } from '../form-schema'
import { createAutomationResourcesApi } from '../resources-api'
import type { ProjectView } from '../../projects/types'
import type { Automation, AutomationWrite } from '../types'
import { useAutomationCommand } from '../use-automation-command'
import { BatchLauncher } from '../../project-runs/components/BatchLauncher'
import { safeProjectError } from '../../projects/presentation-error'

export type AutomationDetailPageProps = {
  projectDefaults?: ProjectView['defaultResources'];
  workspaceKey: string; instanceId: string; projectId: string; automationId?: string; client: StreamingApiClient; disabled: boolean; readOnly: boolean
  onCreated(automationId: string): void
  onBatchCreated?(batchId: string): void
  registerLeaveGuard(guard: (() => Promise<boolean>) | null): void
}
type Baseline = { value: AutomationWrite; revision: number; resetKey: string }
export function AutomationDetailPage(props: AutomationDetailPageProps) {
  return <Detail key={JSON.stringify([props.workspaceKey, props.projectId, props.automationId ?? 'new'])} {...props} />
}
function Detail({ projectDefaults, workspaceKey, instanceId, projectId, automationId, client, disabled, readOnly, onCreated, onBatchCreated, registerLeaveGuard }: AutomationDetailPageProps) {
  const api = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const resources = useMemo(() => createAutomationResourcesApi(client, projectId), [client, projectId])
  const prefix = [workspaceKey, instanceId, 'automations', projectId]
  const cache = useQueryClient()
  const result = useQuery({ queryKey: [...prefix, 'detail', automationId], queryFn: ({ signal }) => api.get(automationId!, signal), enabled: Boolean(automationId) && !disabled })
  const workflows = useQuery({ queryKey: [workspaceKey, instanceId, 'workflow-catalog'], queryFn: ({ signal }) => resources.workflows(signal), enabled: !disabled })
  const profiles = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-profiles'], queryFn: ({ signal }) => resources.profiles(signal), enabled: !disabled })
  const proxies = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-proxies'], queryFn: ({ signal }) => resources.proxies(signal), enabled: !disabled })
  const models = useQuery({ queryKey: [workspaceKey, instanceId, 'automation-models'], queryFn: ({ signal }) => resources.models(signal), enabled: !disabled })
  const tables = useQuery({ queryKey: [...prefix, 'input-tables'], queryFn: ({ signal }) => resources.tables(signal), enabled: !disabled })
  const validation = useQuery({ queryKey: [...prefix, 'validation', automationId], queryFn: ({ signal }) => api.validation(automationId!, signal), enabled: Boolean(automationId) && !disabled })
  const [baseline, setBaseline] = useState<Baseline | null>(() => automationId ? null : { value: emptyAutomationForm(), revision: 0, resetKey: crypto.randomUUID() })
  const [latestConflict, setLatestConflict] = useState<Automation | null>(null)
  const [reloadConflict, setReloadConflict] = useState(0)
  const [confirmation, setConfirmation] = useState<'leave' | 'reset' | 'latest' | null>(null)
  const dirty = useRef(false), resolver = useRef<((allowed: boolean) => void) | null>(null)
  const [recordTableId, setRecordTableId] = useState<string | null>(null)
  const [recordPage, setRecordPage] = useState(1)
  const [startOpen, setStartOpen] = useState(false)
  const recordTable = tables.data?.find(table => table.id === recordTableId)
  const records = useQuery({ queryKey: [...prefix, 'input-records', recordTableId, recordTable?.datasetGeneration, recordPage], queryFn: ({ signal }) => resources.records(recordTable!, recordPage, signal), enabled: Boolean(recordTable) && !disabled })

  const replaceBaseline = (value: Automation) => {
    dirty.current = false
    setBaseline({ value: automationToForm(value), revision: value.managementRevision, resetKey: crypto.randomUUID() })
  }
  useEffect(() => { if (!baseline && result.data) replaceBaseline(result.data) }, [baseline, result.data])
  const command = useAutomationCommand({ client, projectId, workspaceKey, automationId, instanceId, disabled, readOnly, onSaved(saved, key) {
    replaceBaseline(saved)
    cache.setQueryData([...prefix, 'detail', saved.automationId], saved)
    void cache.invalidateQueries({ queryKey: prefix })
    notify({ title: automationId ? '自动化配置已保存' : '自动化已创建', tone: 'success', operationId: JSON.stringify([workspaceKey, key]) })
    if (!automationId) onCreated(saved.automationId)
  } })
  useEffect(() => {
    const original = command.restoredCommand
    if (original) setBaseline({ value: automationToForm(original.body), revision: 'expectedManagementRevision' in original.body ? original.body.expectedManagementRevision : 0, resetKey: `recover:${original.key}` })
  }, [command.restoredCommand])
  useEffect(() => {
    setLatestConflict(null)
    if (!command.conflict || !automationId || disabled) return
    const controller = new AbortController()
    void api.get(automationId, controller.signal).then(value => { if (!controller.signal.aborted) setLatestConflict(value) }).catch(() => undefined)
    return () => controller.abort()
  }, [api, automationId, command.conflict, disabled, instanceId, reloadConflict])
  const latestCommand = useRef(command); latestCommand.current = command
  const guard = useCallback(async () => {
    if (latestCommand.current.locked()) return false
    if (!dirty.current) return true
    if (resolver.current) return false
    setConfirmation('leave')
    return new Promise<boolean>(resolve => { resolver.current = resolve })
  }, [])
  useEffect(() => { registerLeaveGuard(guard); return () => { registerLeaveGuard(null); resolver.current?.(false) } }, [guard, registerLeaveGuard])

  const finishConfirmation = (accept: boolean) => {
    if (command.locked()) return
    if (accept && confirmation === 'latest' && latestConflict) replaceBaseline(latestConflict)
    if (accept && confirmation === 'reset' && baseline) { dirty.current = false; setBaseline({ ...baseline, resetKey: crypto.randomUUID() }) }
    if (accept && confirmation === 'leave') dirty.current = false
    if (accept) command.clearError()
    resolver.current?.(accept); resolver.current = null; setConfirmation(null)
  }
  if (!baseline) return <section className="rounded-card border border-line bg-surface p-6" role={result.error ? 'alert' : 'status'}>{result.error ? <><p>无法读取自动化：{safeProjectError(result.error)}</p><Button onClick={() => void result.refetch()}>重试读取</Button></> : '正在读取自动化…'}</section>
  const options = (tables.data ?? []).map(table => ({ ...table, ...(table.id === recordTableId && records.data ? { records: records.data.items } : {}) }))
  const readErrors = [workflows.error, profiles.error, proxies.error, models.error, tables.error, records.error, result.error].filter(Boolean)
  return <section className="grid min-w-0 gap-3">
    {readErrors.length > 0 ? <div role="alert" className="rounded-control border border-warning/40 bg-surface p-3 text-sm"><p>部分资料读取失败，当前草稿已保留。{readErrors.map(safeProjectError).join('；')}</p><Button size="sm" onClick={() => { void workflows.refetch(); void profiles.refetch(); void proxies.refetch(); void models.refetch(); void tables.refetch(); if (automationId) void result.refetch(); if (recordTable) void records.refetch() }}>重新读取资料</Button></div> : null}
    {command.recovering ? <div role="alert" className="flex flex-wrap items-center gap-3 border border-warning/40 bg-surface p-3 text-sm"><span>{command.notAccepted ? '原请求尚未接受，可以重试原请求或继续编辑。' : '保存结果尚未确认，请先核对原操作。'}</span><Button size="sm" disabled={disabled || command.busy} onClick={() => void command.lookup()}>核对保存结果</Button>{command.notAccepted ? <><Button size="sm" disabled={disabled || readOnly || command.busy} onClick={() => void command.retry()}>重试原请求</Button><Button size="sm" variant="ghost" disabled={command.busy} onClick={command.discardNotAccepted}>继续编辑</Button></> : null}</div> : null}
    {command.conflict ? <div role="alert" className="flex flex-wrap items-center gap-3 border border-warning/40 bg-surface p-3 text-sm"><p>自动化资料已变化，你的输入已保留。最新名称：{latestConflict?.name ?? '尚未读取'}。</p><Button size="sm" disabled={disabled || result.isFetching} onClick={() => setReloadConflict(value => value + 1)}>读取最新资料</Button><Button size="sm" disabled={!latestConflict || disabled} onClick={() => setConfirmation('latest')}>载入最新资料重新编辑</Button></div> : null}
    <AutomationEditor onStartRun={automationId && onBatchCreated ? () => { setStartOpen(true); void validation.refetch() } : undefined} validationNotice={automationId && validation.data && !validation.data.runnable ? <details className="mx-5 border-b border-line py-2 text-sm"><summary className="cursor-pointer text-muted">查看运行条件 · 尚未满足</summary><ul className="mb-0 mt-2 pl-5">{validation.data.issues.map((issue, index) => <li key={`${issue.code}:${index}`}>{safeProjectError(issue)}</li>)}</ul><p className="mb-0 text-muted">可以继续维护配置，保存配置不代表开始运行。</p></details> : null} initialValue={baseline.value} resetKey={baseline.resetKey} isNew={!automationId} disabled={disabled || readOnly} saving={command.busy} recovering={command.recovering} error={command.error} serverErrors={command.fields}
      workflowOptions={(workflows.data?.items ?? []).map(workflow => ({ id: workflow.workflowId, name: workflow.name, revision: workflow.revision, updatedAt: workflow.updatedAt, runnable: workflow.validation.runnable, validationMessage: workflow.validation.issues.map(safeProjectError).join('；') }))}
      environmentOptions={{ projectDefaults, profiles: profiles.data?.items ?? [], proxies: (proxies.data?.proxies ?? []).filter(proxy => proxy.enabled), pools: proxies.data?.pools ?? [], modelProviders: (models.data?.items ?? []).filter(provider => provider.enabled).map(provider => ({ id: provider.id, name: provider.name })) }}
      renderInputPlan={(value, onChange, locked, draft) => <><InputPlanEditor {...draft} value={value} onChange={onChange} disabled={locked} tables={options} onLoadRecords={id => { setRecordTableId(id); setRecordPage(1) }} />{records.isFetching ? <p role="status" className="text-sm text-muted">正在读取记录…</p> : null}{records.data && records.data.total > 200 ? <Pagination offset={(recordPage - 1) * 200} limit={200} count={records.data.items.length} total={records.data.total} disabled={records.isFetching || locked} showPage onOffsetChange={offset => setRecordPage(Math.floor(offset / 200) + 1)} /> : null}</>}
      onSubmit={value => command.submit(automationId ? { ...value, expectedManagementRevision: baseline.revision } : value, automationId)} onCancel={() => setConfirmation('reset')} onDraftStateChange={state => { dirty.current = state.dirty }} />
    {automationId && result.data && onBatchCreated ? <BatchLauncher open={startOpen} onOpenChange={setStartOpen} savedAutomation={{ ...result.data, ...baseline.value, managementRevision: baseline.revision }} validation={validation.data} validationLoading={validation.isFetching} validationError={validation.error ? safeProjectError(validation.error) : undefined} onRefreshValidation={() => void validation.refetch()} workspaceKey={workspaceKey} instanceId={instanceId} projectId={projectId} client={client} disabled={disabled || command.locked()} readOnly={readOnly} onBatchCreated={onBatchCreated} resourceSummary={[
      { label: '工作流', value: workflows.data?.items.find(item => item.workflowId === baseline.value.workflowId)?.name ?? '尚未读取' },
      { label: '浏览器配置', value: profiles.data?.items.find(item => item.id === ('profileId' in baseline.value.environmentPolicy ? baseline.value.environmentPolicy.profileId : projectDefaults?.profileId))?.name ?? '继承项目配置' },
      { label: '执行方式', value: '按顺序执行' },
      { label: '环境', value: baseline.value.environmentPolicy.source === 'newFromProfile' ? '每个任务创建临时环境' : '需修改环境来源' },
    ]}/> : null}
    <AlertDialog open={confirmation !== null} onOpenChange={open => { if (!open) finishConfirmation(false) }}><AlertDialogContent><AlertDialogTitle>{confirmation === 'latest' ? '替换为最新资料？' : '放弃未保存的修改？'}</AlertDialogTitle><AlertDialogDescription>当前草稿会被放弃，已保存的数据不会改变。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button onClick={() => finishConfirmation(false)}>继续编辑</Button></AlertDialogCancel><Button variant="danger" onClick={() => finishConfirmation(true)}>{confirmation === 'latest' ? '载入最新资料' : '放弃修改'}</Button></div></AlertDialogContent></AlertDialog>
  </section>
}
