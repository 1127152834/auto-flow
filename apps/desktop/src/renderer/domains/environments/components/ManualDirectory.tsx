import { WarningCircle } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import type { ManualItem } from '../api'

const time = (value: string | null) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
// Remaining retention is derived from the same deadline the core enforces, so the
// user can judge "处理前核验现场与剩余保留时间" without opening the task.
const remaining = (expiresAt: string | null) => {
  if (!expiresAt) return null
  const minutes = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 60_000)
  if (Number.isNaN(minutes)) return null
  return <small className={`block ${minutes <= 0 ? 'text-warning' : 'text-muted'}`}>{minutes <= 0 ? '已超过保留时间' : `剩余 ${minutes} 分钟`}</small>
}
const statuses: Record<string, string> = { waiting: '等待处理', resume_requested: '已请求继续', resolved: '已处理', expired: '已超时', lost: '已丢失', cancelled: '已取消' }
const openable = (status: string) => status === 'waiting' || status === 'resume_requested'

export function ManualDirectory({ items, loading = false, error, onRetry, onResume, onFinish, onOpen, onOpenTask, onOpenBatch, disabled }: {
  items: ManualItem[]
  loading?: boolean
  error?: string
  disabled?: boolean
  onRetry(): void
  onResume(item: ManualItem): void
  onFinish(item: ManualItem): void
  onOpen?(item: ManualItem): void
  onOpenTask?(taskId: string): void
  onOpenBatch?(runId: string): void
}) {
  return <section className="grid gap-4" aria-label="等待人工">
    {error ? <div role="alert" className="flex items-center justify-between rounded-control border border-warning/30 bg-warning/10 p-3"><span>{error}</span><Button onClick={onRetry}>重试读取</Button></div> : null}
    {loading && items.length === 0 ? <div role="status" aria-label="正在加载等待人工" className="grid gap-2">{[1, 2].map(item => <Skeleton key={item} className="h-16" />)}</div> : items.length ? <TableScroll label="等待人工" className="rounded-control border border-line bg-surface"><Table><TableHeader><TableRow><TableHead>现场信息</TableHead><TableHead>任务信息</TableHead><TableHead>保留时间</TableHead><TableHead>操作</TableHead></TableRow></TableHeader><TableBody>{items.map(item => <TableRow key={item.manualItemId}>
      <TableCell>
        <span className={`inline-flex items-center rounded-control border px-2 py-0.5 text-xs ${openable(item.status) ? 'border-warning/40 bg-warning-soft text-warning' : 'border-line bg-surface-subtle text-muted'}`}>{statuses[item.status] ?? item.status}</span>
        <small className="mt-1 block text-muted">临时现场与租约已保留</small>
      </TableCell>
      <TableCell>
        <dl className="m-0 grid gap-1 text-sm">
          <div className="flex items-baseline gap-2"><dt className="text-muted">任务</dt><dd className="m-0">{onOpenTask ? <Button variant="ghost" className="h-auto p-0 text-sm text-clay" onClick={() => onOpenTask(item.taskId)}>查看任务</Button> : '—'}</dd></div>
          <div className="flex items-baseline gap-2"><dt className="text-muted">批次</dt><dd className="m-0">{onOpenBatch ? <Button variant="ghost" className="h-auto p-0 text-sm text-clay" onClick={() => onOpenBatch(item.runId)}>查看批次</Button> : '—'}</dd></div>
          <div className="flex items-baseline gap-2"><dt className="shrink-0 text-muted">等待原因</dt><dd className="m-0 min-w-0 break-words">{item.reason || '运行记录请求人工确认'}</dd></div>
        </dl>
      </TableCell>
      <TableCell><time dateTime={item.expiresAt ?? undefined}>保留至 {time(item.expiresAt)}</time>{remaining(item.expiresAt)}</TableCell>
      <TableCell>{openable(item.status)
        ? <div className="flex flex-wrap gap-2">{onOpen ? <Button size="sm" disabled={disabled} onClick={() => onOpen(item)}>进入人工处理</Button> : null}<Button size="sm" variant="ghost" disabled={disabled} onClick={() => onResume(item)}>继续原任务</Button><Button size="sm" variant="ghost" disabled={disabled} onClick={() => onFinish(item)}>明确结束</Button></div>
        : '—'}</TableCell>
    </TableRow>)}</TableBody></Table></TableScroll> : !error ? <div className="grid min-h-56 place-items-center text-center"><div><WarningCircle size={48} className="mx-auto text-muted" /><h3>当前没有等待人工处理的环境。</h3></div></div> : null}
  </section>
}
