import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { createProjectDataApi, DataCommandUncertain, type DataTable, type DirectoryQuery, type TableCreate, type TablePatch } from '../api'
import { DataTableDirectory } from '../components/DataTableDirectory'
import { DataTableFormDialog } from '../components/DataTableFormDialog'
import { ExcelImportWizard } from '../components/ExcelImportWizard'
import { DataCommandNotAccepted } from '../data-command'
import { createExcelApi } from '../excel-api'
import type { DataTableFormValues } from '../form-schema'
import { createProjectFileClient } from '../project-file-client'

export type DataTableDirectoryPageProps = {
  workspaceKey: string; instanceId: string; projectId: string; client: StreamingApiClient
  disabled: boolean; readonly: boolean; onOpen(tableId: string): void
  registerLeaveGuard(guard: (() => Promise<boolean>) | null): void
}
const defaults: DirectoryQuery = { query: '', page: 1, pageSize: 50, sort: '-updatedAt' }
const sorts = [{ value: '-updatedAt', label: '最近修改' }, { value: 'updatedAt', label: '最早修改' }, { value: 'name', label: '名称升序' }, { value: '-name', label: '名称降序' }]
const sources = [{ value: 'all', label: '全部来源' }, { value: 'local', label: '本地数据' }, { value: 'excel', label: 'Excel 导入' }, { value: 'sheets', label: 'Google Sheets' }, { value: 'unconfigured', label: '未配置来源' }]
const storageKey = (workspace: string, project: string) => `autoflow:tables-ui:${JSON.stringify([workspace, project])}`
function readQuery(key: string): DirectoryQuery {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? '{}') as Partial<DirectoryQuery>
    return { query: typeof value.query === 'string' ? value.query : '', page: Number.isSafeInteger(value.page) && value.page! > 0 && value.page! <= 2147483647 ? value.page! : 1, pageSize: 50,
      sort: sorts.some(item => item.value === value.sort) ? value.sort! : defaults.sort,
      sourceKind: sources.some(item => item.value !== 'all' && item.value === value.sourceKind) ? value.sourceKind : undefined }
  } catch { return defaults }
}
const tableValues = (table: DataTable) => ({ name: table.name, description: table.description })
type Editor = { session: string; table: DataTable | null }
type Pending = { key: string; body: TableCreate; kind: 'create' } | { key: string; body: TablePatch; kind: 'patch'; tableId: string }

/** Workspace/project changes reset drafts; a service instance change only revokes requests. */
export function DataTableDirectoryPage(props: DataTableDirectoryPageProps) {
  return <Directory key={JSON.stringify([props.workspaceKey, props.projectId])} {...props} />
}
function Directory({ workspaceKey, instanceId, projectId, client, disabled, readonly, onOpen, registerLeaveGuard }: DataTableDirectoryPageProps) {
  const key = storageKey(workspaceKey, projectId)
  const [query, setQuery] = useState(() => readQuery(key))
  const [editor, setEditor] = useState<Editor | null>(null)
  const [excelSession, setExcelSession] = useState<string | null>(null)
  const [recoveryPending, setRecoveryPending] = useState(false)
  const [notAccepted, setNotAccepted] = useState(false)
  const [submissionEpoch, setSubmissionEpoch] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [reloadOpen, setReloadOpen] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [leaveOpen, setLeaveOpen] = useState(false)
  const api = useMemo(() => createProjectDataApi(client, projectId), [client, projectId])
  const cache = useQueryClient()
  const prefix = useMemo(() => [workspaceKey, instanceId, 'project-data', projectId] as const, [workspaceKey, instanceId, projectId])
  const directory = useQuery({ queryKey: [...prefix, 'tables', query], queryFn: ({ signal }) => api.list(query, signal), enabled: !disabled })
  const pending = useRef<Pending | null>(null), dirty = useRef(false), excelDirty = useRef(false), busy = useRef(false), excelBusy = useRef(false), commandBusy = useRef(false)
  const creationMode = useRef<'form' | 'excel' | null>(null)
  const epoch = useRef(0), mounted = useRef(false)
  const scope = useRef({ workspaceKey, projectId, client, instanceId, disabled, readonly, session: editor?.session ?? excelSession })
  const files = useMemo(() => createProjectFileClient(client, window.autoflow, projectId, () => scope.current.workspaceKey === workspaceKey && scope.current.projectId === projectId && scope.current.client === client && scope.current.instanceId === instanceId && !scope.current.disabled), [client, instanceId, projectId, workspaceKey])
  const excelApi = useMemo(() => createExcelApi(client, files, projectId), [client, files, projectId])
  const leaveResolver = useRef<((allowed: boolean) => void) | null>(null)

  useLayoutEffect(() => {
    const previous = scope.current
    const session = editor?.session ?? excelSession
    scope.current = { workspaceKey, projectId, client, instanceId, disabled, readonly, session }
    if (previous.instanceId !== instanceId || previous.client !== client || previous.disabled !== disabled || previous.session !== session) {
      epoch.current++; commandBusy.current = false; busy.current = false
      setSubmissionEpoch(value => value + 1)
      setRecoveryPending(Boolean(pending.current)); setReloading(false); setReloadOpen(false)
    }
  }, [client, disabled, editor?.session, excelSession, instanceId, projectId, readonly, workspaceKey])
  useLayoutEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++; leaveResolver.current?.(false) } }, [])
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(query)) } catch { /* session storage can be unavailable */ } }, [key, query])
  useEffect(() => {
    if (!directory.data) return
    const last = Math.max(1, Math.ceil(directory.data.total / query.pageSize))
    if (query.page > last) setQuery(current => ({ ...current, page: last }))
  }, [directory.data, query.page, query.pageSize])
  const guard = useCallback(async () => {
    if (busy.current || excelBusy.current || commandBusy.current || pending.current) return false
    if (!dirty.current && !excelDirty.current) return true
    if (leaveResolver.current) return false
    setLeaveOpen(true)
    return new Promise<boolean>(resolve => { leaveResolver.current = resolve })
  }, [])
  useEffect(() => { registerLeaveGuard(guard); return () => registerLeaveGuard(null) }, [guard, registerLeaveGuard])
  const finishLeave = (allow: boolean) => {
    if (busy.current || excelBusy.current || commandBusy.current || pending.current) return
    if (allow) { dirty.current = false; excelDirty.current = false; creationMode.current = null; setEditor(null); setExcelSession(null) }
    const resolve = leaveResolver.current; leaveResolver.current = null; setLeaveOpen(false); resolve?.(allow)
  }
  const startEditor = (table: DataTable | null) => {
    if (disabled || readonly || commandBusy.current || pending.current || creationMode.current) return
    creationMode.current = 'form'
    setError(null); setConflict(false); setNotAccepted(false); dirty.current = false
    setEditor({ session: crypto.randomUUID(), table })
  }
  const startExcel = () => {
    if (disabled || readonly || commandBusy.current || pending.current || creationMode.current) return
    creationMode.current = 'excel'
    excelDirty.current = false; setExcelSession(crypto.randomUUID())
  }
  const execute = async (mode: 'submit' | 'lookup' | 'retry', values?: DataTableFormValues) => {
    if (!editor || scope.current.disabled || commandBusy.current || (mode !== 'lookup' && scope.current.readonly)) return
    if (mode === 'submit' && pending.current) return
    if (mode === 'retry' && (!pending.current || !notAccepted)) return
    if (mode === 'lookup' && !pending.current) return
    const resume = mode === 'lookup'
    if (!pending.current) {
      if (!values) return
      pending.current = editor.table
        ? { key: crypto.randomUUID(), kind: 'patch', tableId: editor.table.tableId, body: { ...values, expectedTableRevision: editor.table.tableRevision } }
        : { key: crypto.randomUUID(), kind: 'create', body: { ...values } }
    }
    const command = pending.current, ticket = ++epoch.current
    commandBusy.current = true; setError(null); setConflict(false); setNotAccepted(false)
    const current = () => mounted.current && ticket === epoch.current && scope.current.session === editor.session && scope.current.instanceId === instanceId && scope.current.client === client && scope.current.workspaceKey === workspaceKey && scope.current.projectId === projectId && !scope.current.disabled
    const policy = { lookupOnly: resume, canSubmit: () => current() && !scope.current.readonly }
    try {
      const saved = command.kind === 'create'
        ? await (resume ? api.resumeCreate(command.body, command.key, policy) : api.create(command.body, command.key, policy))
        : await (resume ? api.resumePatch(command.tableId, command.body, command.key, policy) : api.patch(command.tableId, command.body, command.key, policy))
      if (!current()) return
      pending.current = null; dirty.current = false; busy.current = false; commandBusy.current = false
      setRecoveryPending(false); creationMode.current = null; setEditor(null)
      cache.setQueryData([...prefix, 'table', saved.tableId], saved)
      void cache.invalidateQueries({ queryKey: [...prefix, 'tables'] })
      notify({ title: command.kind === 'create' ? '数据表已创建' : '数据表已保存', tone: 'success' })
      if (command.kind === 'create') onOpen(saved.tableId)
    } catch (caught) {
      if (!current()) return
      if (caught instanceof DataCommandNotAccepted) {
        setNotAccepted(true); setRecoveryPending(true); setError(caught.message)
        return
      }
      const uncertain = caught instanceof DataCommandUncertain || !(caught instanceof ApiClientError && caught.status >= 400 && caught.status < 500 && caught.status !== 408)
      if (!uncertain) pending.current = null
      setRecoveryPending(uncertain)
      setConflict(caught instanceof ApiClientError && caught.code === 'REVISION_CONFLICT')
      setError(uncertain ? '上次保存结果尚未确认，请先核对结果。' : caught.message)
    } finally { if (ticket === epoch.current) commandBusy.current = false }
  }
  const reload = async () => {
    if (!editor?.table || disabled || commandBusy.current || pending.current || reloading) return
    const ticket = ++epoch.current; setReloading(true)
    try {
      const latest = await api.get(editor.table.tableId)
      if (!mounted.current || ticket !== epoch.current) return
      setEditor({ session: crypto.randomUUID(), table: latest }); dirty.current = false
      setError(null); setConflict(false); setReloadOpen(false)
      cache.setQueryData([...prefix, 'table', latest.tableId], latest)
    } catch (caught) { if (mounted.current && ticket === epoch.current) { setError(caught instanceof Error ? caught.message : '载入最新资料失败'); setReloadOpen(false) } }
    finally { if (ticket === epoch.current) setReloading(false) }
  }
  const dirtyChanged = useCallback((value: boolean) => { dirty.current = value }, [])
  const savingChanged = useCallback((value: boolean) => { busy.current = value }, [])
  return <section className="grid min-w-0 gap-4" aria-label="项目数据">
    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
      <Input aria-label="搜索数据表" placeholder="搜索名称或描述" value={query.query} onChange={event => setQuery({ ...query, query: event.target.value, page: 1 })} />
      <Select aria-label="数据来源" clearable={false} value={query.sourceKind ?? 'all'} options={sources} onValueChange={value => setQuery({ ...query, sourceKind: value === 'all' || value === null ? undefined : value as DirectoryQuery['sourceKind'], page: 1 })} />
      <Select aria-label="数据表排序" clearable={false} value={query.sort} options={sorts} onValueChange={value => setQuery({ ...query, sort: value as DirectoryQuery['sort'], page: 1 })} />
    </div>
    {disabled ? <p role="status" className="text-sm text-muted">正在恢复服务连接，暂时无法保存。</p> : null}
    <DataTableDirectory items={directory.data?.items ?? []} loading={directory.isPending && !directory.isError} error={directory.error?.message} readonly={readonly || disabled} hasFilters={Boolean(query.query || query.sourceKind)} onRetry={() => void directory.refetch()} onCreate={() => startEditor(null)} onImportExcel={startExcel} onEdit={id => { const table = directory.data?.items.find(item => item.tableId === id); if (table) startEditor(table) }} onOpen={onOpen} />
    {directory.data ? <Pagination offset={(query.page - 1) * query.pageSize} limit={query.pageSize} total={directory.data.total} count={directory.data.items.length} disabled={directory.isFetching || disabled} onOffsetChange={offset => setQuery({ ...query, page: Math.floor(offset / query.pageSize) + 1 })} /> : null}
    <DataTableFormDialog open={Boolean(editor)} mode={editor?.table ? 'edit' : 'create'} sessionKey={editor?.session ?? 'closed'} submissionEpoch={submissionEpoch} initialValues={editor?.table ? tableValues(editor.table) : undefined}
      readonly={readonly || disabled} recoveryPending={recoveryPending} onRecover={disabled ? undefined : () => execute('lookup')} onSubmit={values => execute('submit', values)} onDirtyChange={dirtyChanged} onSavingChange={savingChanged} onRequestClose={guard}
      onOpenChange={open => { if (!open && !pending.current && !commandBusy.current) { dirty.current = false; creationMode.current = null; setEditor(null) } }} error={error}
      errorActions={notAccepted ? <div className="flex gap-2"><Button disabled={disabled || readonly} onClick={() => void execute('retry')}>重试原请求</Button><Button disabled={disabled} variant="ghost" onClick={() => { if (commandBusy.current || !notAccepted) return; pending.current = null; setNotAccepted(false); setRecoveryPending(false); setError(null) }}>放弃未接受请求</Button></div> : conflict ? <Button disabled={disabled || reloading} onClick={() => setReloadOpen(true)}>载入最新资料</Button> : undefined} />
    <ExcelImportWizard open={Boolean(excelSession)} mode="create" sessionKey={excelSession ?? 'closed'} scopeKey={JSON.stringify([workspaceKey, projectId])} contextKey={JSON.stringify([workspaceKey, instanceId, projectId])} api={excelApi} files={files} readonly={readonly} disabled={disabled} onClose={() => { excelDirty.current=false; creationMode.current=null; setExcelSession(null) }} onDirtyChange={value => { excelDirty.current=value }} onBusyChange={value => { excelBusy.current=value }} onCompleted={operation => { if (operation.status !== 'succeeded' || !operation.result || !('table' in operation.result)) return; excelDirty.current=false; creationMode.current=null; setExcelSession(null); void cache.invalidateQueries({ queryKey: [...prefix, 'tables'] }); onOpen(operation.result.table.tableId) }} />
    <AlertDialog open={leaveOpen} onOpenChange={open => { if (!open) finishLeave(false) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>离开后，本次数据表修改不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button onClick={() => finishLeave(false)}>继续编辑</Button></AlertDialogCancel><Button variant="danger" onClick={() => finishLeave(true)}>放弃修改</Button></div></AlertDialogContent></AlertDialog>
    <AlertDialog open={reloadOpen} onOpenChange={open => { if (!reloading) setReloadOpen(open) }}><AlertDialogContent><AlertDialogTitle>替换当前草稿？</AlertDialogTitle><AlertDialogDescription>载入最新资料后，当前输入将被替换。请先保留需要的内容。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={reloading}>继续编辑</Button></AlertDialogCancel><Button disabled={disabled || reloading} onClick={() => void reload()}>{reloading ? '正在载入…' : '重新编辑'}</Button></div></AlertDialogContent></AlertDialog>
  </section>
}
