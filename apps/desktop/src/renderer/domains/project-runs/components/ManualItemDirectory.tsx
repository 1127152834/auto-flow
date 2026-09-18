import { ArrowRight, ClockCountdown, MagnifyingGlass, X } from '@phosphor-icons/react'
import { FormEvent, useEffect, useState } from 'react'
import type { ManualItem, ManualSort } from '../../environments/api'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'
import { TableToolbar } from '../../../shared/components/ui/table-toolbar'
import { presentRunFailure } from '../presentation'

export type ManualItemFilters = { q: string | null; status: string | null; sort: ManualSort }
export type ManualItemPage = { items: ManualItem[]; page: number; pageSize: number; total: number }
const statuses = [{ value: '', label: '全部状态' }, { value: 'waiting', label: '等待处理' }, { value: 'resume_requested', label: '已请求继续' }, { value: 'resolved', label: '已处理' }, { value: 'expired', label: '已超时' }, { value: 'lost', label: '已丢失' }, { value: 'cancelled', label: '已取消' }]
const statusLabel = (value: string) => statuses.find(item => item.value === value)?.label ?? value
const tone = (value: string) => value === 'waiting' ? 'warning' : ['expired', 'lost'].includes(value) ? 'danger' : value === 'resolved' ? 'success' : 'neutral'
const retention = (expiresAt: string | null) => expiresAt === null ? null : new Date(expiresAt).getTime() - Date.now()

export function ManualItemDirectory({ page, filters, loading = false, refreshing = false, error, onFiltersChange, onPageChange, onOpen, onOpenTask, onOpenBatch, onRetry }: {
  page?: ManualItemPage
  filters: ManualItemFilters
  loading?: boolean
  refreshing?: boolean
  error?: string
  onFiltersChange(value: ManualItemFilters): void
  onPageChange(page: number): void
  onOpen(item: ManualItem): void
  onOpenTask(taskId: string): void
  onOpenBatch(runId: string): void
  onRetry(): void
}) {
  const [search, setSearch] = useState(filters.q ?? '')
  useEffect(() => setSearch(filters.q ?? ''), [filters.q])
  const submit = (event: FormEvent) => { event.preventDefault(); const q = search.trim(); if (q !== (filters.q ?? '')) onFiltersChange({ ...filters, q: q || null }) }
  // 默认只看「等待处理」，这不是用户施加的筛选，空态不应说成「没有匹配」。
  const filtered = Boolean(filters.q || (filters.status && filters.status !== 'waiting'))
  return <section className="grid gap-4"><TableToolbar label="等待人工筛选" className="flex flex-wrap justify-end gap-3"><form role="search" className="flex min-w-64 flex-1 gap-2" onSubmit={submit}><Input aria-label="搜索等待人工事项" value={search} maxLength={120} placeholder="搜索任务或等待原因" disabled={refreshing} onChange={event => setSearch(event.target.value)}/>{filters.q ? <Button type="button" variant="ghost" aria-label="清除等待人工搜索" disabled={refreshing} onClick={() => { setSearch(''); onFiltersChange({ ...filters, q: null }) }}><X aria-hidden/></Button> : null}<Button type="submit" aria-label="执行等待人工搜索" disabled={refreshing || search.trim() === (filters.q ?? '')}><MagnifyingGlass aria-hidden/></Button></form><Select aria-label="等待人工状态筛选" className="w-40" clearable={false} value={filters.status ?? ''} options={statuses} disabled={refreshing} onValueChange={value => onFiltersChange({ ...filters, status: value || null })}/><Select aria-label="等待人工排序" className="w-44" clearable={false} value={filters.sort} options={[{ value: 'expiresAt', label: '剩余时间最短优先' }, { value: '-updatedAt', label: '最近更新优先' }]} disabled={refreshing} onValueChange={value => onFiltersChange({ ...filters, sort: value === 'expiresAt' ? 'expiresAt' : '-updatedAt' })}/></TableToolbar>
    {error ? <div role="alert" className="flex items-center justify-between rounded-control border border-warning/30 bg-warning/10 p-3"><span>{page ? `刷新失败，当前显示上次读取的等待人工事项：${presentRunFailure(error)}` : `等待人工事项读取失败：${presentRunFailure(error)}`}</span><Button onClick={onRetry}>重试读取</Button></div> : null}
    {loading && !page ? <div role="status" aria-label="正在加载等待人工事项" className="grid gap-2">{[1, 2].map(item => <Skeleton key={item} className="h-16"/>)}</div> : page?.items.length ? <TableScroll label="等待人工目录" className="rounded-control border border-line bg-surface"><Table><TableHeader><TableRow><TableHead>等待原因</TableHead><TableHead>所属任务</TableHead><TableHead>剩余保留时间</TableHead><TableHead>操作</TableHead></TableRow></TableHeader><TableBody>{page.items.map(item => {
      const left = retention(item.expiresAt)
      return <TableRow key={item.manualItemId}>
        <TableCell>
          <strong className="block break-words">{item.reason || '运行记录请求人工确认'}</strong>
          <span className="mt-1 flex items-center gap-2 text-xs text-muted"><TableStatus tone={tone(item.status)}>{statusLabel(item.status)}</TableStatus><span>事项 {item.manualItemId.slice(0, 8)}</span></span>
        </TableCell>
        <TableCell>
          <div className="grid gap-1 text-sm">
            <Button variant="ghost" className="h-auto justify-start p-0 text-sm text-clay" onClick={() => onOpenTask(item.taskId)}>查看任务<ArrowRight aria-hidden/></Button>
            <Button variant="ghost" className="h-auto justify-start p-0 text-xs text-muted" onClick={() => onOpenBatch(item.runId)}>查看批次</Button>
          </div>
        </TableCell>
        <TableCell>
          {item.expiresAt === null ? <span className="text-muted">没有保留截止时间</span> : left !== null && left <= 0
            ? <><strong className="block text-warning">已超过保留时间</strong><small className="block text-muted">截止 {new Date(item.expiresAt).toLocaleString('zh-CN')}</small></>
            : <><strong className="block text-lg">{Math.ceil((left ?? 0) / 60_000)} 分钟</strong><small className="block text-muted">截止 {new Date(item.expiresAt).toLocaleString('zh-CN')}</small></>}
        </TableCell>
        <TableCell><Button variant="ghost" className="text-clay" onClick={() => onOpen(item)}>查看事项<ArrowRight aria-hidden/></Button></TableCell>
      </TableRow>
    })}</TableBody></Table></TableScroll> : !error ? <div className="grid min-h-72 place-items-center text-center"><div><ClockCountdown size={52} className="mx-auto text-muted"/><h3>{filtered ? '没有匹配的等待人工事项' : '当前没有等待人工处理的事项。'}</h3><p className="text-muted">{filtered ? '调整搜索或状态筛选后再试。' : '工作流在人工检查点暂停后会显示在这里；等待人工不暂停整个批次。'}</p>{filtered ? <Button onClick={() => { setSearch(''); onFiltersChange({ q: null, status: null, sort: 'expiresAt' }) }}>清除筛选</Button> : null}</div></div> : null}
    {page ? <><Pagination showPage offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={refreshing} onOffsetChange={offset => onPageChange(Math.floor(offset / page.pageSize) + 1)}/><p className="m-0 text-xs text-muted">共 {page.total} 项 · 保留时间以服务端记录为准。</p></> : null}</section>
}
