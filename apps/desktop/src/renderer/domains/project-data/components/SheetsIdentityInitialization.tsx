import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsBinding, SheetsBindingWrite, SyncOperation } from '../sheets-api'

type Operation = components['schemas']['ProjectOperationView']
type Props = {
  api: SheetsApi; scopeKey: string; tableId: string; disabled: boolean
  request: Omit<SheetsBindingWrite, 'impactRevision'> | null
  onBound(binding: SheetsBinding): void
  onBusyChange?(busy: boolean): void
}

/** Explicit source mutation, with recovery loaded from the durable server ledger. */
export function SheetsIdentityInitialization({ api, scopeKey, tableId, disabled, request, onBound, onBusyChange }: Props) {
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const [confirmed, setConfirmed] = useState(false)
  const pending = useQuery({ queryKey: ['sheets-identity', scopeKey, tableId], queryFn: async ({ signal }) => {
    const items: SyncOperation[] = []
    for (let page = 1; ; page++) {
      const result = await api.operations(tableId, { page, pageSize: 100 }, signal)
      items.push(...result.items.filter(item => item.kind === 'systemIdentity' && item.status !== 'confirmed'))
      if (page * result.pageSize >= result.total) return items
    }
  } })
  const finish = (operation: Operation) => {
    if (!active.current) return
    if (operation.status === 'succeeded' && operation.result && 'spreadsheetId' in operation.result) onBound(operation.result)
    else setError(operation.error ? safeProjectError(operation.error) : '初始化结果尚未确认。请核验原操作，不要再次创建身份列。')
  }
  const run = async (action: () => Promise<Operation>) => {
    if (busy || disabled) return
    setBusy(true); onBusyChange?.(true); setError(null)
    try { finish(await action()) } catch (cause) { if (active.current) setError(safeProjectError(cause)) }
    finally { if (active.current) { setBusy(false); onBusyChange?.(false); void pending.refetch() } }
  }
  const start = () => run(async () => {
    if (!request || !confirmed) throw new Error('请确认新身份列及来源修改。')
    const report = await api.previewBinding(tableId, request)
    if (report.blockers.length) throw new Error(report.blockers.map(item => item.message).join(' '))
    return api.initializeIdentity(tableId, { ...request, impactRevision: report.impactRevision }, crypto.randomUUID(), () => active.current)
  })
  const recover = (item: SyncOperation, retry = false) => run(async () => {
    const report = await api.previewIdentity(tableId, item.syncOperationId)
    if (report.blockers.length) throw new Error(report.blockers.map(blocker => blocker.message).join(' '))
    return (retry ? api.retryIdentity : api.verifyIdentity)(tableId, item.syncOperationId, { impactRevision: report.impactRevision, expectedTableRevision: report.expectedRevisions.tableRevision! })
  })
  return <section aria-label="系统 UUID 身份初始化" className="grid gap-3 rounded-control border border-line p-3">
    <h4 className="m-0 font-semibold">系统 UUID 身份</h4>
    <p className="m-0 text-sm">在来源新增独立的 _autoflow_id 列，为现有数据行写入固定 UUID。只有完整核验后才建立本地绑定；原本地数据会换代，状态和环境关联不会继承。</p>
    {pending.isPending ? <p role="status">正在读取原初始化操作…</p> : null}
    {pending.error ? <p role="alert">{safeProjectError(pending.error)}</p> : null}
    {pending.data?.map(item => <div key={item.syncOperationId} className="grid gap-2">
      <p className="m-0 text-sm">原操作 {item.syncOperationId} · {item.status}</p>
      {item.error ? <p role="alert">{safeProjectError(item.error)}</p> : null}
      {item.status === 'failed' && item.error?.retryable
        ? <Button disabled={disabled || busy} onClick={() => void recover(item, true)}>重试原未发送计划</Button>
        : <Button disabled={disabled || busy} onClick={() => void recover(item)}>核验原初始化</Button>}
    </div>)}
    {request ? <>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={disabled || busy} onChange={event => setConfirmed(event.target.checked)} />确认在来源 {request.spreadsheetId} 的工作表 {request.sheetId} 新建 {request.identityStrategy.columnId} 列并写入 UUID，以及更换本地数据代次。</label>
      <Button disabled={disabled || busy || !confirmed || pending.isPending || pending.isError || Boolean(pending.data?.some(item => item.status !== 'failed'))} onClick={() => void start()}>初始化系统身份并绑定</Button>
    </> : null}
    {error ? <p role="alert">{error}</p> : null}
  </section>
}
