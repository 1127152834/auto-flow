import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsBinding, SyncOperation } from '../sheets-api'
import type { SheetsSourceContext } from './DataTableSourcePanel'

type Operation = components['schemas']['ProjectOperationView']

export function SheetsColumnCreation({ context, binding, disabled }: { context: SheetsSourceContext; binding: SheetsBinding; disabled: boolean }) {
  const { api, tableId } = context
  const [fieldId, setFieldId] = useState(''), [name, setName] = useState(''), [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const pending = useQuery({ queryKey: ['sheets-columns', context.scopeKey, tableId], queryFn: async ({ signal }) => {
    const items: SyncOperation[] = []
    for (let page = 1; ; page++) {
      const result = await api.columnOperations(tableId, page, signal)
      items.push(...result.items.filter(item => item.status !== 'confirmed' && item.error?.code !== 'SYNC_ABANDONED'))
      if (page * result.pageSize >= result.total) return items
    }
  } })
  const fields = context.fields.filter(field => field.writable && !field.formula && !binding.mapping.some(entry => entry.fieldId === field.ref.fieldId))
  const field = fields.find(item => item.ref.fieldId === fieldId)
  const lock = disabled || busy
  const perform = async (action: () => Promise<Operation | void>) => {
    if (lock) return
    setBusy(true); setError(null)
    try {
      const operation = await action()
      if (!active.current) return
      if (operation && operation.status !== 'succeeded') setError(operation.error ? safeProjectError(operation.error) : '来源列尚未确认，请核验原操作。')
      else { setConfirmed(false); setFieldId(''); context.onChanged?.() }
    } catch (cause) { if (active.current) setError(safeProjectError(cause)) }
    finally { if (active.current) { setBusy(false); void pending.refetch() } }
  }
  const create = () => perform(async () => {
    if (!field || !name.trim() || !confirmed) throw new Error('请选择字段并确认来源修改。')
    const body = { fieldId, columnName: name.trim(), datasetGeneration: context.datasetGeneration,
      connectionId: binding.connectionId, spreadsheetId: binding.spreadsheetId, sheetId: binding.sheetId,
      expectedBindingEpoch: binding.bindingEpoch, expectedTableRevision: context.tableRevision }
    const report = await api.previewColumn(tableId, body)
    if (report.blockers.length) throw new Error(report.blockers.map(item => item.message).join(' '))
    return api.createColumn(tableId, { ...body, impactRevision: report.impactRevision }, crypto.randomUUID(), () => active.current)
  })
  const recover = (item: SyncOperation, retry = false) => perform(async () => {
    const report = await api.previewOriginalColumn(tableId, item.syncOperationId)
    if (report.blockers.length) throw new Error(report.blockers.map(blocker => blocker.message).join(' '))
    return (retry ? api.retryColumn : api.verifyColumn)(tableId, item.syncOperationId, { impactRevision: report.impactRevision, expectedTableRevision: report.expectedRevisions.tableRevision! })
  })
  return <section className="grid gap-3 rounded-control border border-line bg-surface p-5" aria-label="新建来源列">
    <h4 className="m-0 text-lg font-semibold">为本地字段新建来源列</h4>
    <p className="m-0 text-sm text-muted">只新增独立来源列，不接管同名列。核验后扩展映射，已有记录、状态和环境关联保留；本地值进入待推送队列。</p>
    <label className="grid gap-1 text-sm">本地字段<select aria-label="新建来源列的本地字段" disabled={lock} value={fieldId} onChange={event => { setFieldId(event.target.value); setName(fields.find(item => item.ref.fieldId === event.target.value)?.name ?? ''); setConfirmed(false) }}>
      <option value="">选择尚未映射的字段</option>{fields.map(item => <option key={item.ref.fieldId} value={item.ref.fieldId}>{item.name}</option>)}
    </select></label>
    <label className="grid gap-1 text-sm">来源列名<Input aria-label="新建来源列名称" disabled={lock} value={name} maxLength={200} onChange={event => { setName(event.target.value); setConfirmed(false) }} /></label>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={lock || !field} onChange={event => setConfirmed(event.target.checked)} />确认在 {binding.spreadsheetTitle || binding.spreadsheetId} / {binding.sheetName || binding.sheetId} 新增“{name || '未命名'}”并映射到本地“{field?.name ?? '未选择'}”。</label>
    <Button disabled={lock || !field || !name.trim() || !confirmed || pending.isPending || pending.isError || Boolean(pending.data?.some(item => item.status !== 'failed'))} onClick={() => void create()}>确认新建来源列</Button>
    {pending.isPending ? <p role="status">正在读取原增列操作…</p> : null}
    {pending.error ? <p role="alert">{safeProjectError(pending.error)}</p> : null}
    {pending.data?.map(item => <div key={item.syncOperationId} className="grid gap-2">
      <p className="m-0 text-sm">原增列操作 {item.syncOperationId} · {item.status}</p>
      {item.error ? <p role="alert">{safeProjectError(item.error)}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={lock} onClick={() => void recover(item, item.status === 'failed' && Boolean(item.error?.retryable))}>{item.status === 'failed' && item.error?.retryable ? '重试原未发送增列' : '核验原来源列'}</Button>
        {(item.status === 'failed' && item.error?.unsent) || item.status === 'pending' ? <Button disabled={lock} onClick={() => void perform(async () => { await api.cancelColumn(tableId, item.syncOperationId, item.statusRevision) })}>取消原未发送增列</Button> : null}
      </div>
    </div>)}
    {error ? <p role="alert">{error}</p> : null}
  </section>
}
