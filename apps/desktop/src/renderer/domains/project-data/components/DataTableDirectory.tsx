import type { ReactNode } from 'react'
import { ArrowRight, Cloud, Database, DotsThree, FileXls, PencilSimple, Plus, Question } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { Skeleton } from '../../../shared/components/ui/skeleton'

type DataTableView = components['schemas']['DataTableView']
type Props = { toolbar?: ReactNode; items: DataTableView[]; totalCount?: number; loading?: boolean; error?: string | null; readonly?: boolean; disabled?: boolean; hasFilters?: boolean; onRetry(): void; onCreate(): void; onImportExcel(): void; onOpen(tableId: string): void; onEdit(tableId: string): void }
const sourceLabels: Record<DataTableView['sourceKind'], string> = { local: '本地表', excel: 'Excel 本地副本', sheets: 'Google Sheets', unconfigured: '来源未配置' }
const updated = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const sourceIcon = { local: Database, excel: FileXls, sheets: Cloud, unconfigured: Question }

export function DataTableDirectory({ toolbar, items, totalCount, loading = false, error, readonly = false, disabled = false, hasFilters = false, onRetry, onCreate, onImportExcel, onOpen, onEdit }: Props) {
  return <section aria-label="数据表目录" className="grid gap-4">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><div className="flex items-baseline gap-3"><h1 className="m-0 text-3xl font-semibold text-ink">数据表</h1>{totalCount == null ? null : <span className="text-base text-muted">{totalCount} 张</span>}</div><p className="mb-0 mt-1 text-base text-muted">按用途找到数据，进入表内维护记录。</p></div><div role="group" aria-label="数据表工具" className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-3">{toolbar}{readonly ? null : <><Button type="button" variant="secondary" disabled={disabled} onClick={onImportExcel}><FileXls />从 Excel 导入</Button><Button type="button" variant="primary" disabled={disabled} onClick={onCreate}><Plus />新建数据表</Button></>}</div></header>
    {error ? <div role="alert" className="flex items-center justify-between gap-3 rounded-control border border-clay/30 bg-clay/10 px-4 py-3 text-sm"><span>{error}{items.length ? '。当前仍显示上次成功载入的内容。' : ''}</span><Button type="button" variant="ghost" onClick={onRetry}>重试</Button></div> : null}
    {loading && items.length === 0 ? <div role="status" className="grid gap-4 md:grid-cols-2" aria-label="正在加载数据表"><Skeleton className="h-[270px]" /><Skeleton className="h-[270px]" /><span className="sr-only">正在加载数据表</span></div> : items.length === 0 && !error ? <div className="rounded-card border border-dashed border-line bg-surface px-6 py-14 text-center"><p className="m-0 font-medium text-ink">{hasFilters ? '没有匹配的数据表' : '还没有数据表'}</p><p className="mb-0 mt-2 text-sm text-muted">{hasFilters ? '调整筛选条件后重试。' : '创建第一张本地数据表以开始录入记录。'}</p></div> : <div className="grid gap-4 md:grid-cols-2">{items.map(table => {
      const SourceIcon = sourceIcon[table.sourceKind], local = table.sourceKind === 'local'
      const access = disabled ? '连接恢复中' : table.sourceKind === 'unconfigured' ? '待配置' : readonly ? '只读' : table.sourceKind === 'sheets' ? '同步暂未开放' : '本地可维护'
      return <article key={table.tableId} className="relative flex min-h-[270px] min-w-0 flex-col rounded-card border border-line bg-surface p-6 shadow-card">
        {!readonly ? <div className="absolute right-4 top-4"><DropdownMenu><DropdownMenuTrigger asChild><Button type="button" variant="ghost" className="h-9 w-9 p-0" aria-label={`更多${table.name}操作`} disabled={disabled}><DotsThree size={22} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => onEdit(table.tableId)}><PencilSimple className="mr-2" />编辑数据表</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div> : null}
        <div className="flex min-w-0 items-start gap-5 pr-10"><span data-testid={`table-source-icon-${table.tableId}`} data-source-tone={local ? 'sage' : 'clay'} className={`grid h-16 w-16 shrink-0 place-items-center rounded-control ${local ? 'bg-sage-soft text-sage-strong' : 'bg-clay-soft text-clay'}`} aria-hidden="true"><SourceIcon size={32} /></span><div className="min-w-0 flex-1"><h2 className="m-0 min-w-0 break-all text-2xl font-semibold text-ink">{table.name}</h2><p className="mb-0 mt-1 line-clamp-2 break-all text-base text-muted">{table.description || '暂无描述'}</p><p className="mb-0 mt-2 text-sm text-muted">{sourceLabels[table.sourceKind]}</p></div></div>
        <div data-card-meta className="mt-7"><span className="sr-only">{table.recordCount} 条记录</span><div aria-hidden="true" className="flex items-baseline gap-3"><strong className="text-[40px] leading-none text-ink">{table.recordCount}</strong><span className="text-base text-muted">条</span><span className="text-sm text-muted">本地记录</span></div></div>
        <div data-card-actions className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-sm text-muted"><span><span>{access}</span> · <time dateTime={table.updatedAt}>更新于 {updated(table.updatedAt)}</time></span><Button type="button" variant="ghost" className="px-0 text-clay" aria-label={`打开数据表：${table.name}`} onClick={() => onOpen(table.tableId)}>打开数据表<ArrowRight /></Button></div>
      </article>
    })}</div>}
  </section>
}
