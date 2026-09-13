import type { ReactNode } from 'react'
import { Cloud, Database, FileXls, PencilSimple, Plus, Question } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'

type DataTableView = components['schemas']['DataTableView']
type Props = { toolbar?: ReactNode; items: DataTableView[]; loading?: boolean; error?: string | null; readonly?: boolean; hasFilters?: boolean; onRetry(): void; onCreate(): void; onImportExcel(): void; onOpen(tableId: string): void; onEdit(tableId: string): void }
const sourceLabels: Record<DataTableView['sourceKind'], string> = { local: '本地表', excel: 'Excel 本地副本', sheets: 'Google Sheets', unconfigured: '来源未配置' }
const updated = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const sourceIcon = { local: Database, excel: FileXls, sheets: Cloud, unconfigured: Question }

export function DataTableDirectory({ toolbar, items, loading = false, error, readonly = false, hasFilters = false, onRetry, onCreate, onImportExcel, onOpen, onEdit }: Props) {
  return <section aria-label="数据表目录" className="grid gap-4">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="m-0 text-2xl font-semibold text-ink">数据表</h1><p className="mb-0 mt-1 text-sm text-muted">管理项目中的本地数据与外部来源。</p></div><div role="group" aria-label="数据表工具" className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2">{toolbar}{readonly ? null : <><Button type="button" variant="secondary" onClick={onImportExcel}><FileXls />从 Excel 导入</Button><Button type="button" variant="primary" onClick={onCreate}><Plus />新建数据表</Button></>}</div></header>
    {error ? <div role="alert" className="flex items-center justify-between gap-3 rounded-control border border-clay/30 bg-clay/10 px-4 py-3 text-sm"><span>{error}{items.length ? '。当前仍显示上次成功载入的内容。' : ''}</span><Button type="button" variant="ghost" onClick={onRetry}>重试</Button></div> : null}
    {loading && items.length === 0 ? <div role="status" className="grid gap-3" aria-label="正在加载数据表"><Skeleton className="h-28" /><Skeleton className="h-28" /><span className="sr-only">正在加载数据表</span></div> : items.length === 0 && !error ? <div className="rounded-card border border-dashed border-line bg-surface px-6 py-14 text-center"><p className="m-0 font-medium text-ink">{hasFilters ? '没有匹配的数据表' : '还没有数据表'}</p><p className="mb-0 mt-2 text-sm text-muted">{hasFilters ? '调整筛选条件后重试。' : '创建第一张本地数据表以开始录入记录。'}</p></div> : <div className="grid gap-3 md:grid-cols-2">{items.map(table => {
      const SourceIcon = sourceIcon[table.sourceKind], local = table.sourceKind === 'local'
      return <article key={table.tableId} className="flex min-w-0 flex-col rounded-card border border-line bg-surface p-4 shadow-card">
        <div className="flex min-w-0 items-start gap-3"><span data-testid={`table-source-icon-${table.tableId}`} data-source-tone={local ? 'sage' : 'clay'} className={`grid h-10 w-10 shrink-0 place-items-center rounded-control ${local ? 'bg-sage-soft text-sage-strong' : 'bg-clay-soft text-clay'}`} aria-hidden="true"><SourceIcon size={22} /></span><div className="min-w-0 flex-1"><div className="flex min-w-0 flex-wrap items-start justify-between gap-2"><h2 className="m-0 min-w-0 break-all text-base font-semibold text-ink">{table.name}</h2><Badge className="shrink-0">{sourceLabels[table.sourceKind]}</Badge></div><p className="mt-1 line-clamp-2 break-all text-sm text-muted">{table.description || '暂无描述'}</p></div></div>
        <div data-card-meta className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 pt-4 text-xs text-muted"><span>{table.recordCount} 条记录</span><time dateTime={table.updatedAt}>更新于 {updated(table.updatedAt)}</time></div>
        <div data-card-actions className="mt-4 flex flex-wrap justify-end gap-2"><Button type="button" variant="ghost" aria-label={`打开${table.name}`} onClick={() => onOpen(table.tableId)}>打开</Button>{readonly ? null : <Button type="button" variant="ghost" aria-label={`编辑${table.name}`} onClick={() => onEdit(table.tableId)}><PencilSimple />编辑</Button>}</div>
      </article>
    })}</div>}
  </section>
}
