import type { ReactNode } from 'react'
import { DotsThree, Info, Trash } from '@phosphor-icons/react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { components } from '../../../shared/api/generated'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import type { RecordSelection } from '../use-record-selection'

type Schema = components['schemas']
type RecordView = Schema['DataRecordView']
export type DataRecordsTableProps = {
  page?: Schema['DataRecordPage']
  fields: Schema['DataFieldView'][]
  statuses: Schema['DataStatusView'][]
  draftRows?: ReactNode
  queryLocked?: boolean
  toolbar?: boolean
  visibleFieldIds?: string[]
  loading?: boolean
  error?: string | null
  hasFilters?: boolean
  readonly?: boolean
  disabled?: boolean
  onRetry(): void
  onOpen(record: RecordView): void
  onEdit?(record: RecordView): void
  onDelete?(record: RecordView): void
  onPageChange(page: number): void
  onCreate?(): void
  onStatusChange?(record: RecordView): void
  selection?: RecordSelection
  onBulkStatus?(): void
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

export function DataRecordsTable({ draftRows, queryLocked = false, toolbar = true, page, fields, statuses, visibleFieldIds, loading = false, error, hasFilters = false, readonly = false, disabled = false, onRetry, onOpen, onEdit, onDelete, onPageChange, onCreate, onStatusChange, selection, onBulkStatus }: DataRecordsTableProps) {
  const visible = visibleFieldIds ? new Set(visibleFieldIds) : null
  const columns = fields.filter((field) => !visible || visible.has(field.ref.fieldId))
  const statusMap = new Map(statuses.map((status) => [status.statusId, status]))
  return (
    <section aria-label="数据记录" aria-busy={loading} className="grid min-w-0 gap-2">
      {toolbar ? (
        <header className="flex items-center justify-between gap-3">
          <h2 className="m-0 text-lg font-semibold text-ink">数据记录</h2>
          {onCreate && !readonly ? (
            <Button variant="primary" disabled={loading || disabled} onClick={onCreate}>
              新增记录
            </Button>
          ) : null}
        </header>
      ) : null}
      {toolbar && selection && selection.count ? (
        <div role="toolbar" aria-label="批量记录操作" className="flex flex-wrap items-center gap-3 rounded-control border border-line bg-surface-subtle p-3">
          <span>已选择 {selection.count} 条</span>
          <Button size="sm" variant="ghost" disabled={loading || disabled} onClick={selection.clear}>
            清空选择
          </Button>
          {onBulkStatus ? (
            <Button size="sm" disabled={readonly || loading || disabled} onClick={onBulkStatus}>
              批量设置状态
            </Button>
          ) : null}
        </div>
      ) : null}
      {selection?.error ? (
        <p role="alert" className="text-sm text-clay">
          {selection.error}
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm">
          <span>
            {error}
            {page ? '。当前仍显示上次成功载入的内容。' : ''}
          </span>
          <Button variant="ghost" disabled={loading} onClick={onRetry}>
            重试
          </Button>
        </div>
      ) : null}
      {!page && loading ? (
        <div role="status" className="grid gap-2">
          <span className="sr-only">正在加载记录</span>
          <Skeleton className="h-12" />
          <Skeleton className="h-24" />
        </div>
      ) : page && page.items.length === 0 && !draftRows ? (
        <div className="rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <p className="font-medium">{hasFilters ? '没有匹配的记录' : '还没有记录'}</p>
          <p className="text-sm text-muted">{hasFilters ? '调整筛选条件后重试。' : '新增记录，或从来源设置导入数据。'}</p>
        </div>
      ) : page ? (
        <TableScroll label="记录表格，超出宽度时可水平滚动">
          <Table
            aria-label="数据记录列表" className="table-fixed"
            style={{
              minWidth: `${112 + 128 + 136 + 160 + (selection ? 40 : 0) + columns.length * 160}px`,
            }}
          >
            <colgroup>
              {selection ? <col style={{ width: 40 }} /> : null}
              <col data-record-column="identity" style={{ width: 112 }} />
              {columns.map((field) => (
                <col key={field.ref.fieldId} />
              ))}
              {columns.length === 0 ? <col data-record-column="remainder" /> : null}
              <col data-record-column="status" style={{ width: 128 }} />
              <col data-record-column="updated" style={{ width: 136 }} />
              <col data-record-column="actions" style={{ width: 160 }} />
            </colgroup>
            <TableHeader>
              <TableRow>
                {selection ? (
                  <TableHead>
                    <Checkbox aria-label="选择本页记录" checked={page.items.length > 0 && page.items.every(selection.isSelected) ? true : page.items.some(selection.isSelected) ? 'indeterminate' : false} disabled={readonly || disabled || loading} onCheckedChange={(checked) => selection.togglePage(page.items, checked === true)} />
                  </TableHead>
                ) : null}
                <TableHead className="w-28" data-column-width="112">
                  记录身份
                </TableHead>
                {columns.map((field) => (
                  <TableHead key={field.ref.fieldId}>
                    <span className="block truncate" title={field.name}>
                      {field.name}{draftRows && field.required ? <span aria-label="必填" className="ml-1 text-danger">*</span> : null}
                    </span>
                  </TableHead>
                ))}
                {columns.length === 0 ? <TableHead aria-hidden="true" data-record-remainder /> : null}
                <TableHead>业务状态</TableHead>
                <TableHead>最近修改</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((record) => {
                const cells = new Map(record.values.map((cell) => [cell.fieldId, cell]))
                const key = record.ref.recordKey,
                  identity = `${keyLabels[key.type]} · ${key.value}`
                const status = record.statusId ? statusMap.get(record.statusId) : undefined
                const statusName = record.statusId ? (status?.name ?? '状态不可用') : '未设置'
                const statusColor = status && /^#[0-9a-f]{6}$/i.test(status.color) ? status.color : undefined
                const statusBadge = <Badge data-status-badge className="gap-1.5 text-ink" style={statusColor ? { backgroundColor: `${statusColor}18` } : undefined}><span aria-hidden="true" className="size-2 rounded-full bg-muted" style={statusColor ? { backgroundColor: statusColor } : undefined} />{statusName}</Badge>
                return (
                  <TableRow key={JSON.stringify(record.ref)} aria-selected={selection ? selection.isSelected(record) : undefined}>
                    {selection ? (
                      <TableCell>
                        <Checkbox aria-label={`选择记录 ${identity}`} checked={selection.isSelected(record)} disabled={readonly || disabled || loading} onCheckedChange={(checked) => selection.toggle(record, checked === true)} />
                      </TableCell>
                    ) : null}
                    <TableCell>
                      <span className="block truncate" title={identity} aria-label={identity}>
                        {identity}
                      </span>
                    </TableCell>
                    {columns.map((field) => {
                      const label = valueLabel(cells.get(field.ref.fieldId))
                      return (
                        <TableCell key={field.ref.fieldId}>
                          <span className="block truncate whitespace-pre" title={label}>
                            {label}
                          </span>
                        </TableCell>
                      )
                    })}
                    {columns.length === 0 ? <TableCell aria-hidden="true" data-record-remainder /> : null}
                    <TableCell>
                      {onStatusChange ? (
                        <Button size="sm" variant="ghost" disabled={readonly || loading || disabled} aria-label={`修改状态 ${identity}`} onClick={() => onStatusChange(record)}>
                          {statusBadge}
                        </Button>
                      ) : statusBadge}
                    </TableCell>
                    <TableCell><time className="block truncate text-muted" title={new Date(record.updatedAt).toLocaleString('zh-CN')} dateTime={record.updatedAt}>{new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(record.updatedAt))}</time></TableCell>
                    <TableCell><div className="flex items-center gap-1">
                      <Button size="sm" variant="ghost" className="text-clay" aria-label={`查看记录 ${identity}`} data-record-open={JSON.stringify(record.ref.recordKey)} onClick={() => onOpen(record)}>
                        查看
                      </Button>
                      {onEdit && !readonly ? <Button size="sm" variant="ghost" className="text-clay" disabled={disabled || loading} aria-label={`编辑记录 ${identity}`} onClick={() => onEdit(record)}>编辑</Button> : null}
                      {onDelete && !readonly ? <DropdownMenu><DropdownMenuTrigger asChild><Button size="sm" variant="ghost" className="w-8 px-0" disabled={disabled || loading} aria-label={`更多记录 ${identity}操作`}><DotsThree size={22} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem className="text-danger" disabled={disabled || loading} onSelect={() => onDelete(record)}><Trash size={16} />删除记录</DropdownMenuItem></DropdownMenuContent></DropdownMenu> : null}
                    </div></TableCell>
                  </TableRow>
                )
              })}
              {draftRows}
            </TableBody>
          </Table>
        </TableScroll>
      ) : null}
      {page ? <Pagination showPage offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={loading || queryLocked} onOffsetChange={(offset) => onPageChange(Math.floor(offset / page.pageSize) + 1)} /> : null}
      <p className="m-0 flex items-start gap-2 text-xs text-muted"><Info size={20} className="shrink-0" aria-hidden="true"/>业务状态由本项目维护，修改记录内容不会自动改变业务状态。</p>
    </section>
  )
}
