import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowClockwise, ArrowDown, ArrowUp, Pause, Play, ShieldCheck } from '@phosphor-icons/react'
import { useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsBinding, SyncOperation } from '../sheets-api'

type Schema = components['schemas']

const kindLabels: Record<SyncOperation['kind'], string> = { pull: '拉取', push: '推送', reconcile: '核验', binding: '绑定', column: '增列', systemIdentity: '系统身份' }
const statusLabels: Record<SyncOperation['status'], string> = {
  notApplicable: '不适用', idle: '空闲', pending: '待发送', sending: '正在发送', verifying: '正在核验',
  confirmed: '已确认', failed: '未发送', unknown: '结果未知', paused: '已暂停',
}
const tone = (status: SyncOperation['status']) => status === 'confirmed' ? 'text-success' : status === 'unknown' ? 'text-clay' : status === 'failed' ? 'text-danger' : 'text-muted'
/** A record key is either a plain string or the typed form that keeps "1" apart from 1. */
const keyLabel = (key: string | { value: string }) => typeof key === 'string' ? key : key.value
const when = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))

export type SyncOperationPanelProps = {
  api: SheetsApi
  tableId: string
  scopeKey: string
  tableRevision: number
  binding: SheetsBinding | null
  readonly?: boolean
  disabled?: boolean
  onChanged?(): void
}

/** Sync facts for one table: what is pending, what was confirmed, and what must be reconciled. */
export function SyncOperationPanel({ api, tableId, scopeKey, tableRevision, binding, readonly = false, disabled = false, onChanged }: SyncOperationPanelProps) {
  const queries = useQueryClient()
  const state = useQuery({ queryKey: ['sheets-sync', scopeKey, tableId], queryFn: ({ signal }) => api.state(tableId, signal), retry: false })
  const operations = useQuery({ queryKey: ['sheets-operations', scopeKey, tableId], queryFn: ({ signal }) => api.operations(tableId, { pageSize: 50 }, signal), retry: false })
  const [busy, setBusy] = useState<string | null>(null), [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null)
  const locked = readonly || disabled
  const current = state.data?.binding ?? binding

  const run = async (name: string, work: () => Promise<string>) => {
    if (busy) return
    setBusy(name); setError(null); setNotice(null)
    try { setNotice(await work()) } catch (cause) { setError(safeProjectError(cause)) }
    finally {
      setBusy(null)
      await Promise.all([
        queries.invalidateQueries({ queryKey: ['sheets-sync', scopeKey, tableId] }),
        queries.invalidateQueries({ queryKey: ['sheets-operations', scopeKey, tableId] }),
        queries.invalidateQueries({ queryKey: ['data-table', scopeKey, tableId] }),
      ])
      onChanged?.()
    }
  }
  const summaryOf = (operation: Schema['ProjectOperationView']) => operation.result && 'summary' in operation.result ? operation.result.summary as Schema['SyncSummary'] : null

  const push = () => run('push', async () => {
    if (!current) throw new Error('尚未绑定来源，无法推送。')
    const operation = await api.push(tableId, 'due', current.bindingEpoch, crypto.randomUUID(), () => true)
    if (operation.status === 'failed') throw operation.error ?? new Error('推送未完成')
    const summary = summaryOf(operation)
    return summary ? `推送已处理：待发送 ${summary.pendingCount}，未知 ${summary.unknownCount}。` : '推送已提交，可在下方核对结果。'
  })
  const pull = () => run('pull', async () => {
    const operation = await api.pull(tableId, tableRevision, crypto.randomUUID(), () => true)
    if (operation.status === 'failed') throw operation.error ?? new Error('拉取未完成')
    return '拉取已提交：本地普通值不会被覆盖，公式列按来源刷新。'
  })
  const toggle = () => run(current?.syncPaused ? 'resume' : 'pause', async () => {
    if (!current) throw new Error('尚未绑定来源。')
    if (current.syncPaused) { await api.resume(tableId, current.bindingEpoch); return '已恢复调度。' }
    await api.pause(tableId, current.bindingEpoch)
    return '已暂停调度；在途发送仍会登记结果。'
  })
  const reconcile = (item: SyncOperation) => run(`reconcile:${item.syncOperationId}`, async () => {
    const operation = await api.reconcile(tableId, item.syncOperationId, item.statusRevision, crypto.randomUUID(), () => true)
    if (operation.status === 'failed') throw operation.error ?? new Error('核验未完成')
    return `已核验原目标，${kindLabels[item.kind]}操作已有确定结论。`
  })
  const abandon = (item: SyncOperation) => run(`abandon:${item.syncOperationId}`, async () => {
    await api.abandon(tableId, item.syncOperationId, { expectedStatusRevision: item.statusRevision, reason: '用户放弃未发送的来源变更' }, () => true)
    return '已放弃未发送的来源变更，本地事实不变。'
  })

  if (!current) return <p className="m-0 text-sm text-muted">尚未绑定工作表，绑定后这里会显示同步事实。</p>

  return <section className="grid gap-4" aria-label="同步状态">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="grid gap-1">
        <h4 className="text-lg font-semibold">同步状态</h4>
        <p className="m-0 text-sm text-muted">
          <span className={tone(state.data?.summary.status ?? 'idle')}>{statusLabels[state.data?.summary.status ?? 'idle']}</span>
          {'  '}待发送 {state.data?.summary.pendingCount ?? 0}　未知结果 {state.data?.summary.unknownCount ?? 0}
          {state.data?.summary.lastConfirmedAt ? `　最近确认 ${when(state.data.summary.lastConfirmedAt)}` : ''}
          {current.syncPaused ? '　调度已暂停' : ''}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={locked || Boolean(busy)} onClick={() => void push()}><ArrowUp size={16} aria-hidden="true" />推送本地改动</Button>
        <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void pull()}><ArrowDown size={16} aria-hidden="true" />拉取来源（含公式）</Button>
        <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void toggle()}>{current.syncPaused ? <><Play size={16} aria-hidden="true" />恢复调度</> : <><Pause size={16} aria-hidden="true" />暂停调度</>}</Button>
        <Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => { void state.refetch(); void operations.refetch() }}><ArrowClockwise size={16} aria-hidden="true" />刷新</Button>
      </div>
    </header>
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {notice ? <p role="status" className="m-0 text-sm text-success">{notice}</p> : null}
    {operations.isPending ? <Skeleton className="h-24" /> : operations.error ? <p role="alert" className="m-0 text-sm text-danger">同步记录暂时无法读取。<Button size="sm" variant="ghost" onClick={() => void operations.refetch()}>重新载入</Button></p> :
      (operations.data?.items.length ?? 0) === 0 ? <p className="m-0 text-sm text-muted">还没有同步记录。</p> :
        <TableScroll label="同步记录" className="rounded-control border border-line">
          <Table data-variant="compact" aria-label="同步记录">
            <TableHead><TableRow><TableCell>时间</TableCell><TableCell>类型</TableCell><TableCell>状态</TableCell><TableCell>目标</TableCell><TableCell>远端证据</TableCell><TableCell /></TableRow></TableHead>
            <TableBody>
              {operations.data!.items.map(item => <TableRow key={item.syncOperationId}>
                <TableCell className="whitespace-nowrap">{when(item.updatedAt)}</TableCell>
                <TableCell>{kindLabels[item.kind]}</TableCell>
                <TableCell className={tone(item.status)}>{statusLabels[item.status]}</TableCell>
                <TableCell className="max-w-72 break-all text-muted">{item.record ? keyLabel(item.record.recordKey as string | { value: string }) : (item.targetContentRevision ? `内容版本 ${item.targetContentRevision}` : '—')}</TableCell>
                <TableCell className="text-muted">{item.evidence ? `${item.evidence.outcome === 'matched' ? '远端一致' : item.evidence.outcome === 'ambiguous' ? '远端有歧义' : '远端不一致'} · ${item.evidence.fields.length} 个字段` : '—'}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    {item.status === 'unknown' ? <Button size="sm" disabled={locked || Boolean(busy)} onClick={() => void reconcile(item)}><ShieldCheck size={16} aria-hidden="true" />核对结果</Button> : null}
                    {item.status === 'pending' ? <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void abandon(item)}>放弃该意图</Button> : null}
                  </div>
                </TableCell>
              </TableRow>)}
            </TableBody>
          </Table>
        </TableScroll>}
    {state.data?.summary.unknownCount ? <p className="m-0 text-sm text-clay">有 {state.data.summary.unknownCount} 条发送结果未知。系统不会自动重发，请先核对原目标。</p> : null}
  </section>
}
