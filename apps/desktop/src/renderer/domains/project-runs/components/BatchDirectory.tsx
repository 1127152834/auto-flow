import { ArrowRight, Database, MagnifyingGlass, X } from '@phosphor-icons/react'
import { FormEvent, useEffect, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Select } from '../../../shared/components/ui/select'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableToolbar } from '../../../shared/components/ui/table-toolbar'
import { BatchStatus, type BatchStatusValue } from './BatchStatus'
import { presentRunFailure } from '../presentation'

type BatchPage = components['schemas']['BatchPage']
type Batch = components['schemas']['BatchView'] & { automationName?: string | null }
export type BatchFilters = { q: string | null; automationId: string | null; status: string | null; period: string | null }
export type BatchDirectoryProps = { page?: BatchPage; filters: BatchFilters; automationOptions?: { id: string; name: string }[]; loading?: boolean; refreshing?: boolean; error?: string; onFiltersChange(value: BatchFilters): void; onPageChange(page: number): void; onOpen(batch: Batch): void; onRetry(): void }

const statusOptions = [{ value: '', label: '全部状态' }, { value: 'accepted', label: '已接受' }, { value: 'running', label: '运行中' }, { value: 'blocked', label: '等待资源' }, { value: 'draining', label: '正在收尾' }, { value: 'stopping', label: '正在停止' }, { value: 'reconciling', label: '正在核对' }, { value: 'completed', label: '已完成' }, { value: 'stopped', label: '已停止' }, { value: 'failed', label: '失败' }, { value: 'interrupted', label: '已中断' }]
const time = (value: string) => new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))

export function BatchDirectory({ page, filters, automationOptions = [], loading = false, refreshing = false, error, onFiltersChange, onPageChange, onOpen, onRetry }: BatchDirectoryProps) {
  const [search, setSearch] = useState(filters.q ?? '')
  useEffect(() => setSearch(filters.q ?? ''), [filters.q])
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const q = search.trim()
    if (q !== (filters.q ?? '')) onFiltersChange({ ...filters, q: q || null })
  }
  const filtered = Boolean(filters.q || filters.automationId || filters.status || filters.period)
  const initial = loading && !page
  const automationChoices = filters.automationId && !automationOptions.some(item => item.id === filters.automationId)
    ? [{ value: filters.automationId, label: '自动化引用暂不可用' }, ...automationOptions.map(item => ({ value: item.id, label: item.name }))]
    : automationOptions.map(item => ({ value: item.id, label: item.name }))
  return <section className="grid gap-4">
    <TableToolbar label="批次筛选" className="flex flex-wrap justify-end gap-3">
      <form role="search" className="flex min-w-64 flex-1 gap-2" onSubmit={submit}>
        <Input aria-label="搜索批次" value={search} maxLength={120} placeholder="搜索自动化名称" disabled={refreshing} onChange={event => setSearch(event.target.value)}/>
        {filters.q ? <Button type="button" variant="ghost" aria-label="清除批次搜索" disabled={refreshing} onClick={() => { setSearch(''); onFiltersChange({ ...filters, q: null }) }}><X aria-hidden/></Button> : null}
        <Button type="submit" aria-label="执行批次搜索" disabled={refreshing || search.trim() === (filters.q ?? '')}><MagnifyingGlass aria-hidden/></Button>
      </form>
      <Select aria-label="自动化筛选" className="w-48" clearable={false} value={filters.automationId ?? ''} options={[{ value: '', label: '全部自动化' }, ...automationChoices]} disabled={refreshing} onValueChange={value => onFiltersChange({ ...filters, automationId: value || null })}/>
      <Select aria-label="批次状态筛选" className="w-40" clearable={false} value={filters.status ?? ''} options={statusOptions} disabled={refreshing} onValueChange={value => onFiltersChange({ ...filters, status: value || null })}/>
      <Select aria-label="批次时间筛选" className="w-32" clearable={false} value={filters.period ?? ''} options={[{ value: '', label: '全部时间' }, { value: '7d', label: '近 7 天' }, { value: '30d', label: '近 30 天' }]} disabled={refreshing} onValueChange={value => onFiltersChange({ ...filters, period: value || null })}/>
    </TableToolbar>
    {error ? <div role="alert" className="flex items-center justify-between rounded-control border border-warning/30 bg-warning/10 p-3"><span>{page ? `刷新失败，当前显示上次读取的记录：${presentRunFailure(error)}` : `批次读取失败：${presentRunFailure(error)}`}</span><Button onClick={onRetry}>重试读取</Button></div> : null}
    {initial ? <div role="status" aria-label="正在加载批次" className="grid gap-2">{[1, 2, 3].map(item => <Skeleton key={item} className="h-16"/>)}</div> : page?.items.length ? <TableScroll label="批次目录" className="rounded-control border border-line bg-surface"><Table><TableHeader><TableRow><TableHead>自动化</TableHead><TableHead>开始时间</TableHead><TableHead>批次状态</TableHead><TableHead>任务数量</TableHead><TableHead>操作</TableHead></TableRow></TableHeader><TableBody>{page.items.map(rawBatch => { const batch = rawBatch as Batch; return <TableRow key={batch.batchId}><TableCell><strong>{batch.automationName || automationOptions.find(item => item.id === batch.automationId)?.name || '自动化'}</strong><small className="block text-muted">开始于 {time(batch.createdAt)}</small></TableCell><TableCell><time dateTime={batch.createdAt}>{time(batch.createdAt)}</time></TableCell><TableCell><BatchStatus status={batch.status as BatchStatusValue}/></TableCell><TableCell>{batch.createdTaskCount} 个任务{batch.activeTaskCount ? ` · ${batch.activeTaskCount} 个进行中` : ''}</TableCell><TableCell><Button variant="ghost" className="text-clay" onClick={() => onOpen(batch)}>查看记录<ArrowRight aria-hidden/></Button></TableCell></TableRow>})}</TableBody></Table></TableScroll> : !error ? <div className="grid min-h-72 place-items-center text-center"><div><Database size={52} className="mx-auto text-muted"/><h3>{filtered ? '没有匹配的批次' : '还没有运行记录'}</h3><p className="text-muted">{filtered ? '调整搜索或筛选条件后再试。' : '自动化产生批次后，记录会按开始时间出现在这里。'}</p>{filtered ? <Button onClick={() => { setSearch(''); onFiltersChange({ q: null, automationId: null, status: null, period: null }) }}>清除筛选</Button> : null}</div></div> : null}
    {page ? <Pagination showPage offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={refreshing} onOffsetChange={offset => onPageChange(Math.floor(offset / page.pageSize) + 1)}/> : null}
  </section>
}
