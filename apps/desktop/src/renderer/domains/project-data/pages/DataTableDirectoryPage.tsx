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
import type { DataTableFormValues } from '../form-schema'

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
  const [recoveryPending, setRecoveryPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [reloadOpen, setReloadOpen] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [leaveOpen, setLeaveOpen] = useState(false)
  const api = useMemo(() => createProjectDataApi(client, projectId), [client, projectId])
  const cache = useQueryClient()
  const prefix = useMemo(() => [workspaceKey, instanceId, 'project-data', projectId] as const, [workspaceKey, instanceId, projectId])
  const directory = useQuery({ queryKey: [...prefix, 'tables', query], queryFn: ({ signal }) => api.list(query, signal), enabled: !disabled })
  const pending = useRef<Pending | null>(null), dirty = useRef(false), busy = useRef(false), commandBusy = useRef(false)
  const epoch = useRef(0), mounted = useRef(false)
  const scope = useRef({ instanceId, disabled, readonly, session: editor?.session })
  const leaveResolver = useRef<((allowed: boolean) => void) | null>(null)

  useLayoutEffect(() => {
    const previous = scope.current
    scope.current = { instanceId, disabled, readonly, session: editor?.session }
    if (previous.instanceId !== instanceId || previous.disabled !== disabled || previous.session !== editor?.session) {
      epoch.current++; commandBusy.current = false; busy.current = false
      setRecoveryPending(Boolean(pending.current)); setReloading(false); setReloadOpen(false)
    }
  }, [disabled, editor?.session, instanceId, readonly])
  useLayoutEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++; leaveResolver.current?.(false) } }, [])
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(query)) } catch { /* session storage can be unavailable */ } }, [key, query])
  useEffect(() => {
    if (!directory.data) return
    const last = Math.max(1, Math.ceil(directory.data.total / query.pageSize))
    if (query.page > last) setQuery(current => ({ ...current, page: last }))
  }, [directory.data, query.page, query.pageSize])
  const guard = useCallback(async () => {
    if (busy.current || commandBusy.current || pending.current) return false
    if (!dirty.current) return true
    if (leaveResolver.current) return false
    setLeaveOpen(true)
    return new Promise<boolean>(resolve => { leaveResolver.current = resolve })
  }, [])
  useEffect(() => { registerLeaveGuard(guard); return () => registerLeaveGuard(null) }, [guard, registerLeaveGuard])
  const finishLeave = (allow: boolean) => {
    if (busy.current || commandBusy.current || pending.current) return
    if (allow) { dirty.current = false; setEditor(null) }
    const resolve = leaveResolver.current; leaveResolver.current = null; setLeaveOpen(false); resolve?.(allow)
  }
  const startEditor = (table: DataTable | null) => {
    if (disabled || readonly || commandBusy.current || pending.current) return
    setError(null); setConflict(false); dirty.current = false
    setEditor({ session: crypto.randomUUID(), table })
  }
  const execute = async (values?: DataTableFormValues) => {
    if (!editor || scope.current.disabled || commandBusy.current || (!pending.current && scope.current.readonly)) return
    const resume = Boolean(pending.current)
    if (!pending.current) {
      if (!values) return
      pending.current = editor.table
        ? { key: crypto.randomUUID(), kind: 'patch', tableId: editor.table.tableId, body: { ...values, expectedTableRevision: editor.table.tableRevision } }
        : { key: crypto.randomUUID(), kind: 'create', body: { ...values } }
    }
    const command = pending.current, ticket = ++epoch.current
    commandBusy.current = true; setError(null); setConflict(false)
    const current = () => mounted.current && ticket === epoch.current && scope.current.session === editor.session && scope.current.instanceId === instanceId && !scope.current.disabled
    try {
      const saved = command.kind === 'create'
        ? await (resume ? api.resumeCreate(command.body, command.key) : api.create(command.body, command.key))
        : await (resume ? api.resumePatch(command.tableId, command.body, command.key) : api.patch(command.tableId, command.body, command.key))
      if (!current()) return
      pending.current = null; dirty.current = false; busy.current = false; commandBusy.current = false
      setRecoveryPending(false); setEditor(null)
      cache.setQueryData([...prefix, 'table', saved.tableId], saved)
      void cache.invalidateQueries({ queryKey: [...prefix, 'tables'] })
      notify({ title: command.kind === 'create' ? '数据表已创建' : '数据表已保存', tone: 'success' })
      if (command.kind === 'create') onOpen(saved.tableId)
    } catch (caught) {
      if (!current()) return
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
    <DataTableDirectory items={directory.data?.items ?? []} loading={directory.isPending && !directory.isError} error={directory.error?.message} readonly={readonly || disabled} hasFilters={Boolean(query.query || query.sourceKind)} onRetry={() => void directory.refetch()} onCreate={() => startEditor(null)} onEdit={id => { const table = directory.data?.items.find(item => item.tableId === id); if (table) startEditor(table) }} onOpen={onOpen} />
    {directory.data ? <Pagination offset={(query.page - 1) * query.pageSize} limit={query.pageSize} total={directory.data.total} count={directory.data.items.length} disabled={directory.isFetching || disabled} onOffsetChange={offset => setQuery({ ...query, page: Math.floor(offset / query.pageSize) + 1 })} /> : null}
    <DataTableFormDialog open={Boolean(editor)} mode={editor?.table ? 'edit' : 'create'} sessionKey={editor?.session ?? 'closed'} submissionEpoch={`${instanceId}:${disabled}`} initialValues={editor?.table ? tableValues(editor.table) : undefined}
      readonly={readonly || disabled} recoveryPending={recoveryPending} onRecover={disabled ? undefined : () => execute()} onSubmit={execute} onDirtyChange={dirtyChanged} onSavingChange={savingChanged} onRequestClose={guard}
      onOpenChange={open => { if (!open && !pending.current && !commandBusy.current) { dirty.current = false; setEditor(null) } }} error={error}
      errorActions={conflict ? <Button disabled={disabled || reloading} onClick={() => setReloadOpen(true)}>载入最新资料</Button> : undefined} />
    <AlertDialog open={leaveOpen} onOpenChange={open => { if (!open) finishLeave(false) }}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>离开后，本次数据表修改不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button onClick={() => finishLeave(false)}>继续编辑</Button></AlertDialogCancel><Button variant="danger" onClick={() => finishLeave(true)}>放弃修改</Button></div></AlertDialogContent></AlertDialog>
    <AlertDialog open={reloadOpen} onOpenChange={open => { if (!reloading) setReloadOpen(open) }}><AlertDialogContent><AlertDialogTitle>替换当前草稿？</AlertDialogTitle><AlertDialogDescription>载入最新资料后，当前输入将被替换。请先保留需要的内容。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={reloading}>继续编辑</Button></AlertDialogCancel><Button disabled={disabled || reloading} onClick={() => void reload()}>{reloading ? '正在载入…' : '重新编辑'}</Button></div></AlertDialogContent></AlertDialog>
  </section>
}
