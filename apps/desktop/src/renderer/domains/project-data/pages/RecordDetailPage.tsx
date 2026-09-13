import type { ReactNode } from 'react'
import { DotsThree, PencilSimple, Trash } from '@phosphor-icons/react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'

export type RecordDetailPageProps = {
  title: string
  fieldsView?: ReactNode
  statusForm?: ReactNode
  recordKeyLabel?: string
  createdAt?: string
  updatedAt?: string
  loading?: boolean
  error?: string | null
  readonly?: boolean
  disabled?: boolean
  onBack(): void
  onEdit(): void
  onDelete(): void
  onRetry?(): void
}
export function RecordDetailPage({ title, fieldsView, statusForm, recordKeyLabel, updatedAt, loading, error, readonly, disabled, onEdit, onDelete, onRetry }: RecordDetailPageProps) {
  return <section aria-label="记录详情" className="grid min-w-0 gap-5" data-record-page="detail">
    <header className="flex min-w-0 flex-wrap items-center justify-between gap-4"><h2 className="m-0 min-w-0 flex-1 break-words text-[28px] font-semibold [overflow-wrap:anywhere]">{title}</h2><div className="flex gap-4"><Button className="h-12 px-6 text-base" variant="primary" onClick={onEdit} disabled={readonly || disabled || loading || !fieldsView}><PencilSimple />编辑记录</Button><DropdownMenu><DropdownMenuTrigger asChild><Button className="h-12 w-14" variant="secondary" aria-label="更多记录操作" disabled={readonly || disabled || loading || !fieldsView}><DotsThree size={24}/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem className="text-danger" disabled={readonly || disabled || loading || !fieldsView} onSelect={onDelete}><Trash size={16}/>删除记录</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div></header>
    {error ? <div role="alert" className="rounded-control border border-danger/30 bg-danger/5 p-4 text-sm"><p>{error}</p>{onRetry ? <Button size="sm" variant="ghost" onClick={onRetry} disabled={loading || disabled}>重试</Button> : null}</div> : null}
    {loading && !fieldsView ? <div role="status" aria-label="正在加载记录"><Skeleton className="h-64" /></div> : fieldsView ? <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      {fieldsView}
      <aside className="min-w-0"><section aria-label="业务状态" className="grid gap-5 rounded-card border border-line bg-surface p-5"><div><h3 className="mb-2 text-2xl font-semibold">项目内状态</h3><p className="text-base text-muted">业务状态仅保存在本项目内，不写入来源文件。</p></div>{statusForm}<dl className="m-0 grid gap-5 border-t border-line pt-5 text-base"><div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-4"><dt className="text-muted">最近修改</dt><dd className="m-0 break-words"><time dateTime={updatedAt}>{updatedAt ? new Date(updatedAt).toLocaleString('zh-CN', { hour12: false }) : '暂无记录'}</time></dd></div>{recordKeyLabel ? <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-4"><dt className="text-muted">记录编号</dt><dd className="m-0 break-all">{recordKeyLabel}</dd></div> : null}</dl></section></aside>
    </div> : null}
  </section>
}
