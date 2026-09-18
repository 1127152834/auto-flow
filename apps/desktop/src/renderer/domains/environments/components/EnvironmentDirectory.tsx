import { DotsThree, HardDrive } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import type { Environment, EnvironmentPage } from '../api'

const time = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const states: Record<string, string> = { ready: '就绪', unavailable: '不可用', deleting: '删除中', deleted: '已删除' }
// The directory renders where a saved copy came from, so the source label is product
// language rather than the internal enum the API carries.
const sources: Record<string, string> = { newFromProfile: '按浏览器配置新建', fixedEnvironment: '来自持久环境', inputEnvironment: '来自记录关联环境' }
const tones: Record<string, string> = {
  ready: 'border-sage/40 bg-sage-soft text-sage-strong',
  unavailable: 'border-warning/40 bg-warning-soft text-warning',
  deleting: 'border-line bg-surface-subtle text-muted',
  deleted: 'border-line bg-surface-subtle text-muted',
}
const pill = (state: string) => <span className={`inline-flex items-center rounded-control border px-2 py-0.5 text-xs ${tones[state] ?? 'border-line bg-surface-subtle text-muted'}`}>{states[state] ?? state}</span>

export function EnvironmentDirectory({ page, query = '', loading = false, error, disabled = false, onOpen, onOpenTask, onMaintenance, onRetry }: {
  page?: EnvironmentPage
  query?: string
  loading?: boolean
  error?: string
  disabled?: boolean
  onOpen(environmentId: string): void
  onOpenTask?(taskId: string): void
  onMaintenance?(item: { environmentId: string; contentGeneration: number }): void
  onRetry(): void
}) {
  const initial = loading && !page
  const menu = (item: Environment) => <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="ghost" className="h-8 w-8 p-0" aria-label={`更多 ${item.name} 操作`} disabled={disabled}><DotsThree size={21} aria-hidden /></Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end">
      <DropdownMenuItem onSelect={() => onOpen(item.ref.environmentId)}>查看环境</DropdownMenuItem>
      {onMaintenance ? <DropdownMenuItem onSelect={() => onMaintenance({ environmentId: item.ref.environmentId, contentGeneration: item.ref.contentGeneration })}>维护打开</DropdownMenuItem> : null}
    </DropdownMenuContent>
  </DropdownMenu>
  return <section className="grid gap-4" aria-label="持久环境">
    {error ? <div role="alert" className="flex items-center justify-between rounded-control border border-warning/30 bg-warning/10 p-3"><span>{page ? `刷新失败，当前显示上次读取的记录：${error}` : `持久环境读取失败：${error}`}</span><Button onClick={onRetry}>重试读取</Button></div> : null}
    {initial ? <div role="status" aria-label="正在加载持久环境" className="grid gap-2">{[1, 2, 3].map(item => <Skeleton key={item} className="h-16" />)}</div> : page?.items.length ? <TableScroll label="持久环境目录" className="rounded-control border border-line bg-surface"><Table><TableHeader><TableRow><TableHead>环境</TableHead><TableHead>状态</TableHead><TableHead>最近来源</TableHead><TableHead>保存时间</TableHead><TableHead>引用</TableHead><TableHead className="w-12 text-right">更多</TableHead></TableRow></TableHeader><TableBody>{page.items.map(item => <TableRow key={item.ref.environmentId}>
      <TableCell><strong className="[overflow-wrap:anywhere]">{item.name}</strong><small className="block text-muted">{sources[item.createdFromSource ?? ''] ?? '保存的环境副本'}</small></TableCell>
      <TableCell>{pill(item.state)}</TableCell>
      <TableCell>{item.createdFromTaskId && onOpenTask ? <Button variant="ghost" className="h-auto p-0 text-sm text-clay" onClick={() => onOpenTask(item.createdFromTaskId!)}>查看任务</Button> : '—'}</TableCell>
      <TableCell><time dateTime={item.updatedAt}>{time(item.updatedAt)}</time></TableCell>
      <TableCell>{item.linkedRecordCount ?? 0}</TableCell>
      <TableCell className="text-right">{menu(item)}</TableCell>
    </TableRow>)}</TableBody></Table></TableScroll> : !error ? <div className="grid min-h-72 place-items-center text-center"><div><HardDrive size={52} className="mx-auto text-muted" /><h3>{page && page.total === 0 && !query.trim() ? '还没有持久环境' : '没有匹配的持久环境'}</h3><p className="text-muted">任务结束时明确保留登录上下文后，环境会出现在这里。</p></div></div> : null}
  </section>
}
