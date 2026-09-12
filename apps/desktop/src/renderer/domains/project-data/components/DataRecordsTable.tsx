import type { components } from '../../../shared/api/generated'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../shared/components/ui/table'

type Schema = components['schemas']
type RecordView = Schema['DataRecordView']
export type DataRecordsTableProps = {
  page?: Schema['DataRecordPage']; fields: Schema['DataFieldView'][]; statuses: Schema['DataStatusView'][]
  visibleFieldIds?: string[]; loading?: boolean; error?: string | null; hasFilters?: boolean; readonly?: boolean
  onRetry(): void; onOpen(record: RecordView): void; onPageChange(page: number): void
  onCreate?(): void; onStatusChange?(record: RecordView): void
}
const keyLabels = { text: '文本', integer: '整数', uuid: 'UUID' }
function valueLabel(cell: Schema['DataCellView'] | undefined): string {
  if (!cell) return '未填写'
  if (!cell.readable) return '不可读取'
  if (cell.error) return `读取失败：${cell.error}`
  const value = cell.value
  if (value === null) return '空值'
  if (value === '') return '空字符串'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return value.value + (value.precision === 'datetime' ? ` ${value.offset ?? '无时区'}` : '')
  return String(value)
}

export function DataRecordsTable({ page, fields, statuses, visibleFieldIds, loading = false, error, hasFilters = false, readonly = false, onRetry, onOpen, onPageChange, onCreate, onStatusChange }: DataRecordsTableProps) {
  const visible = visibleFieldIds ? new Set(visibleFieldIds) : null
  const columns = fields.filter(field => !visible || visible.has(field.ref.fieldId))
  const statusMap = new Map(statuses.map(status => [status.statusId, status]))
  return <section aria-label="数据记录" aria-busy={loading} className="grid min-w-0 gap-4">
    <header className="flex items-center justify-between gap-3"><h2 className="m-0 text-lg font-semibold text-ink">数据记录</h2>{onCreate && !readonly ? <Button variant="primary" disabled={loading} onClick={onCreate}>新增记录</Button> : null}</header>
    {error ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm"><span>{error}{page ? '。当前仍显示上次成功载入的内容。' : ''}</span><Button variant="ghost" disabled={loading} onClick={onRetry}>重试</Button></div> : null}
    {!page && loading ? <div role="status" className="grid gap-2"><span className="sr-only">正在加载记录</span><Skeleton className="h-12" /><Skeleton className="h-24" /></div>
      : page && page.items.length === 0 ? <div className="rounded-card border border-dashed border-line bg-surface p-10 text-center"><p className="font-medium">{hasFilters ? '没有匹配的记录' : '还没有记录'}</p><p className="text-sm text-muted">{hasFilters ? '调整筛选条件后重试。' : '新增记录，或从来源设置导入数据。'}</p></div>
      : page ? <div tabIndex={0} role="region" aria-label="记录表格，超出宽度时可水平滚动" className="min-w-0 overflow-x-auto rounded-card border border-line bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clay/50">
        <Table className="w-full table-fixed" style={{ minWidth: `${192 + 160 + 112 + columns.length * 200}px` }}><TableHeader><TableRow><TableHead className="w-48">记录身份</TableHead>{columns.map(field => <TableHead key={field.ref.fieldId} className="w-[200px]"><span className="block truncate" title={field.name}>{field.name}</span></TableHead>)}<TableHead className="w-40">业务状态</TableHead><TableHead className="w-28">操作</TableHead></TableRow></TableHeader>
          <TableBody>{page.items.map(record => {
            const cells = new Map(record.values.map(cell => [cell.fieldId, cell]))
            const key = record.ref.recordKey, identity = `${keyLabels[key.type]} · ${key.value}`
            const status = record.statusId ? statusMap.get(record.statusId) : undefined
            const statusName = record.statusId ? status?.name ?? '状态不可用' : '未设置'
            return <TableRow key={JSON.stringify(record.ref)}><TableCell><span className="block truncate" title={identity}>{identity}</span></TableCell>{columns.map(field => {
              const label = valueLabel(cells.get(field.ref.fieldId))
              return <TableCell key={field.ref.fieldId}><span className="block truncate whitespace-pre" title={label}>{label}</span></TableCell>
            })}<TableCell>{onStatusChange ? <Button size="sm" variant="ghost" disabled={readonly || loading} aria-label={`修改状态 ${identity}`} onClick={() => onStatusChange(record)}>{statusName}</Button> : <Badge>{statusName}</Badge>}</TableCell><TableCell><Button size="sm" variant="ghost" aria-label={`查看记录 ${identity}`} onClick={() => onOpen(record)}>查看</Button></TableCell></TableRow>
          })}</TableBody></Table>
      </div> : null}
    {page ? <Pagination offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={loading} onOffsetChange={offset => onPageChange(Math.floor(offset / page.pageSize) + 1)} /> : null}
  </section>
}
