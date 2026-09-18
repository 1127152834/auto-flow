import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowClockwise, ArrowDown, ArrowUp, Pause, Play, ShieldCheck, WarningCircle } from '@phosphor-icons/react'
import { useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
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

/** The three facts an operator needs before trusting either direction, in the prototype's own order. */
const boundaryRules = [
  { title: '业务状态只保存在项目内', detail: '待核对、已整理等业务状态保存在本项目，不会写回来源工作表。' },
  { title: '本地维护不等于云端已确认', detail: '本地修改保存后立即生效，云端结果另行核验。' },
  { title: '结果待核验的变化不重复发送', detail: '结果未知时先核对原目标，再决定下一步。' },
]

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

/** Sync facts for one table: what to pull, what is pending, and what must be reconciled. */
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

  const summary = state.data?.summary
  const items = operations.data?.items ?? []
  const pendingCount = summary ? summary.pendingCount : null
  const unknownCount = summary ? summary.unknownCount : null
  const lastPull = items.find((item) => item.kind === 'pull')
  const unknownItem = items.find((item) => item.status === 'unknown')
  const pendingItem = items.find((item) => item.status === 'pending')

  return <>
    <section className="grid gap-3 rounded-control border border-line bg-surface p-5" aria-label="拉取新增">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-control border border-line text-clay" aria-hidden="true"><ArrowDown size={20} /></span>
          <div><h4 className="m-0 text-lg font-semibold">拉取新增</h4><p className="m-0 text-sm text-muted">从 Google Sheets 获取新增记录</p></div>
        </div>
        <Button variant="secondary" disabled={locked || Boolean(busy)} onClick={() => void pull()}><ArrowDown size={16} aria-hidden="true" />拉取来源（含公式）</Button>
      </header>
      <p className="m-0 text-sm text-muted">
        {operations.isPending ? '正在读取拉取记录…' : operations.error ? '拉取记录暂时无法读取。' : lastPull ? <>最近一次 {when(lastPull.updatedAt)} · <span className={tone(lastPull.status)}>{statusLabels[lastPull.status]}</span></> : '还没有拉取记录。'}
      </p>
      <p className="m-0 text-sm text-muted">新记录加入本地；已有普通字段保留本地值，公式列按来源刷新。来源已删除的行不会自动删除本地记录。</p>
    </section>

    <section className="grid gap-3 rounded-control border border-line bg-surface p-5" aria-label="推送变化">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-control border border-line text-clay" aria-hidden="true"><ArrowUp size={20} /></span>
          <div><h4 className="m-0 text-lg font-semibold">推送变化</h4><p className="m-0 text-sm text-muted">将已保存的本地变化推送到 Google Sheets</p></div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <p className="m-0 text-sm text-muted">
            <span className={tone(summary?.status ?? 'idle')}>{statusLabels[summary?.status ?? 'idle']}</span>
            {'　'}待发送 {pendingCount ?? '—'}{'　'}结果待核验 {unknownCount ?? '—'}
          </p>
          <Button disabled={locked || Boolean(busy)} onClick={() => void push()}><ArrowUp size={16} aria-hidden="true" />推送本地改动</Button>
        </div>
      </header>
      {state.error ? <p role="alert" className="m-0 text-sm text-danger">同步状态暂时无法读取。<Button size="sm" variant="ghost" onClick={() => void state.refetch()}>重新载入</Button></p> : null}
      {state.isPending && !summary ? <Skeleton className="h-12" /> : null}
      {summary?.lastConfirmedAt ? <p className="m-0 text-sm text-muted">最近确认 {when(summary.lastConfirmedAt)}{current.syncPaused ? '　调度已暂停' : ''}</p> : current.syncPaused ? <p className="m-0 text-sm text-muted">调度已暂停；在途发送仍会登记结果。</p> : null}
      {unknownItem ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-warning/30 bg-warning/5 p-3">
        <div className="flex items-start gap-3">
          <WarningCircle size={22} weight="fill" className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          <div><p className="m-0 text-sm font-medium text-clay">请求已发出，尚未确认云端结果。</p><p className="m-0 text-sm text-muted">系统不会自动重发。请先核对该操作的原目标。</p></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" disabled={locked || Boolean(busy)} onClick={() => void reconcile(unknownItem)}><ShieldCheck size={16} aria-hidden="true" />核验云端结果</Button>
          {pendingItem ? <Button variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void abandon(pendingItem)}>放弃该意图</Button> : null}
        </div>
      </div> : pendingItem ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-line p-3">
        <p className="m-0 text-sm text-muted">有尚未发送的本地变化，推送会按当前映射发送。</p>
        <Button variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void abandon(pendingItem)}>放弃该意图</Button>
      </div> : null}
      {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
      {notice ? <p role="status" className="m-0 text-sm text-success">{notice}</p> : null}
    </section>

    <section className="grid gap-3 rounded-control border border-line bg-surface p-5" aria-label="同步记录">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="m-0 text-lg font-semibold">同步记录</h4>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void toggle()}>{current.syncPaused ? <><Play size={16} aria-hidden="true" />恢复调度</> : <><Pause size={16} aria-hidden="true" />暂停调度</>}</Button>
          <Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => { void state.refetch(); void operations.refetch() }}><ArrowClockwise size={16} aria-hidden="true" />刷新</Button>
        </div>
      </header>
      {operations.isPending ? <Skeleton className="h-24" /> : operations.error ? <p role="alert" className="m-0 text-sm text-danger">同步记录暂时无法读取。<Button size="sm" variant="ghost" onClick={() => void operations.refetch()}>重新载入</Button></p> :
        items.length === 0 ? <p className="m-0 text-sm text-muted">还没有同步记录。</p> :
          <TableScroll label="同步记录" className="rounded-control border border-line">
            <Table data-variant="compact" aria-label="同步记录">
              <TableHeader><TableRow><TableHead>时间</TableHead><TableHead>类型</TableHead><TableHead>状态</TableHead><TableHead>目标</TableHead><TableHead>远端证据</TableHead><TableHead>操作</TableHead></TableRow></TableHeader>
              <TableBody>
                {items.map(item => <TableRow key={item.syncOperationId}>
                  <TableCell className="whitespace-nowrap">{when(item.updatedAt)}</TableCell>
                  <TableCell>{kindLabels[item.kind]}</TableCell>
                  <TableCell className={tone(item.status)}>{statusLabels[item.status]}</TableCell>
                  <TableCell className="max-w-72 break-all text-muted">{item.record ? keyLabel(item.record.recordKey as string | { value: string }) : (item.targetContentRevision ? `内容版本 ${item.targetContentRevision}` : '—')}</TableCell>
                  <TableCell className="text-muted">{item.evidence ? `${item.evidence.outcome === 'matched' ? '远端一致' : item.evidence.outcome === 'ambiguous' ? '远端有歧义' : '远端不一致'} · ${item.evidence.fields.length} 个字段` : '—'}</TableCell>
                  <TableCell className="text-muted">
                    {item.status === 'unknown' || item.status === 'pending'
                      ? <div className="flex gap-2">
                        {item.status === 'unknown' ? <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void reconcile(item)}><ShieldCheck size={16} aria-hidden="true" />核对结果</Button> : null}
                        {item.status === 'pending' ? <Button size="sm" variant="ghost" disabled={locked || Boolean(busy)} onClick={() => void abandon(item)}>放弃该意图</Button> : null}
                      </div>
                      : '—'}
                  </TableCell>
                </TableRow>)}
              </TableBody>
            </Table>
          </TableScroll>}
    </section>
  </>
}

/** Static explanation of the same boundary the panel enforces; no counts are invented here. */
export function SyncBoundaryCard() {
  return <section className="grid gap-3 rounded-control border border-line bg-surface p-5" aria-label="同步边界">
    <h4 className="m-0 text-lg font-semibold">同步边界</h4>
    {boundaryRules.map(rule => <div key={rule.title} className="grid gap-1 rounded-control border border-line p-3">
      <p className="m-0 text-sm font-medium">{rule.title}</p>
      <p className="m-0 text-sm text-muted">{rule.detail}</p>
    </div>)}
  </section>
}
