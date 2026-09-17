import { Info, Lock, Plus } from '@phosphor-icons/react'
import { useId } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'

type Status = components['schemas']['DataStatusView']
type Usage = components['schemas']['DataStatusUsageDirectory']
export type DataStatusTableProps = {
  statuses: Status[]
  usage?: Usage
  loading?: boolean
  error?: string | null
  readonly?: boolean
  disabled?: boolean
  onCreate(): void
  onEdit(status: Status): void
  onDelete(status: Status): void
  onRetryUsage(): void
}

export function DataStatusTable({ statuses, usage, loading = false, error, readonly = false, disabled = false, onCreate, onEdit, onDelete, onRetryUsage }: DataStatusTableProps) {
  const id = useId()
  const locked = readonly || disabled
  const references = new Map(usage?.items.map(item => [item.statusId, item]))
  const unavailable = error ? '引用暂时无法读取' : loading ? '正在读取…' : !usage ? '尚未读取' : null
  const canRetry = !loading && (Boolean(error) || !usage || statuses.some(status => !references.has(status.statusId)))

  return <section aria-labelledby={`${id}-title`} className="grid gap-3 rounded-control border border-line bg-surface p-4">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h3 id={`${id}-title`} className="text-xl font-semibold">数据状态</h3>
        <p className="mt-1 text-base text-muted">用于标记记录的整理进度，仅保存在当前项目。</p>
      </div>
      <Button size="sm" className="text-sm" variant="primary" disabled={locked} onClick={() => { if (!locked) onCreate() }}><Plus aria-hidden="true" size={18} />新增状态</Button>
    </header>
    <p className="m-0 flex items-start gap-2 rounded-control bg-clay-soft px-4 py-3 text-base text-muted"><Info aria-hidden="true" size={23} className="shrink-0 text-clay" />当前记录与未完成批量操作的引用分别统计，不相加；有引用的状态不能删除。</p>
    {error ? <div role="alert" className="text-sm text-danger">状态引用读取失败，请重试。</div> : null}
    {readonly ? <p className="m-0 text-sm text-muted">当前项目为只读，可以查看数据状态。</p> : null}
    <TableScroll label="数据状态列表" className="rounded-control border border-line">
      <Table aria-label="数据状态" aria-busy={loading} className="min-w-[40rem]">
        <TableHeader><TableRow><TableHead className="w-[34%]">状态名称</TableHead><TableHead>当前记录</TableHead><TableHead>未完成批量操作</TableHead><TableHead className="w-[26%]">操作</TableHead></TableRow></TableHeader>
        <TableBody>
          {statuses.map(status => {
            const count = unavailable ? undefined : references.get(status.statusId)
            const missing = unavailable ?? (!count ? '待刷新' : null)
            const inUse = count && (count.currentRecords > 0 || count.activeBatchOperations > 0)
            const canDelete = !locked && count?.currentRecords === 0 && count.activeBatchOperations === 0
            const reason = readonly ? '当前项目为只读。' : disabled ? '当前操作尚未结束。' : missing ? `${missing}，确认引用后才能删除。` : inUse ? `仍有 ${count.currentRecords.toLocaleString()} 条记录、${count.activeBatchOperations.toLocaleString()} 个未完成批量操作引用。` : '下一步检查删除影响。'
            const color = /^#[0-9a-f]{6}$/i.test(status.color) ? status.color : undefined
            const reasonId = `${id}-${status.statusId}-delete-reason`
            return <TableRow key={status.statusId}>
              <TableCell><span className="inline-flex items-center gap-2 break-all"><span data-status-color aria-hidden="true" className="size-2.5 shrink-0 rounded-full bg-muted" style={color ? { backgroundColor: color } : undefined} />{status.name}</span></TableCell>
              <TableCell>{missing ?? count!.currentRecords.toLocaleString()}</TableCell>
              <TableCell>{missing ?? count!.activeBatchOperations.toLocaleString()}</TableCell>
              <TableCell>
                <div className="flex items-center gap-3">
                  <Button size="sm" variant="ghost" className="h-7 px-1 text-sm text-clay" aria-label={`编辑状态 ${status.name}`} disabled={locked} onClick={() => { if (!locked) onEdit(status) }}>重命名</Button>
                  <span aria-hidden="true" className="text-muted">|</span>
                  <Button size="sm" variant="ghost" className="h-7 px-1 text-sm text-muted" aria-label={`删除状态 ${status.name}`} aria-describedby={reasonId} title={reason} disabled={!canDelete} onClick={() => { if (canDelete) onDelete(status) }}>{!canDelete ? <Lock aria-hidden="true" size={15} /> : null}删除</Button>
                </div>
                <p id={reasonId} className={missing || inUse ? 'mt-1 text-xs text-muted' : 'sr-only'}>{reason}</p>
              </TableCell>
            </TableRow>
          })}
          {!statuses.length ? <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted">尚未设置数据状态</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </TableScroll>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="m-0 text-sm text-muted">{usage?.configurationReferences.availability === 'notImplemented' ? '配置引用尚未接通，不表示没有引用。' : ''}删除前仍需检查影响。</p>
      {canRetry ? <Button onClick={onRetryUsage}>重新读取引用</Button> : null}
    </div>
  </section>
}
