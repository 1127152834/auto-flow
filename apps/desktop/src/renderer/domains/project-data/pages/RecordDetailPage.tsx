import type { ReactNode } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'

export type RecordDetailPageProps = {
  title: string
  fieldsView?: ReactNode
  statusForm?: ReactNode
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
export function RecordDetailPage({ title, fieldsView, statusForm, createdAt, updatedAt, loading, error, readonly, disabled, onBack, onEdit, onDelete, onRetry }: RecordDetailPageProps) {
  return <section aria-label="记录详情" className="grid min-w-0 gap-5" data-record-page="detail">
    <Button size="sm" variant="ghost" className="w-fit px-0" onClick={onBack} disabled={disabled}>返回记录列表</Button>
    <header className="flex min-w-0 flex-wrap items-center justify-between gap-3"><h1 className="m-0 min-w-0 flex-1 break-words text-2xl font-semibold [overflow-wrap:anywhere]">{title}</h1><div className="flex gap-2"><Button onClick={onEdit} disabled={readonly || disabled || loading || !fieldsView}>编辑记录</Button><Button variant="danger" onClick={onDelete} disabled={readonly || disabled || loading || !fieldsView}>删除记录</Button></div></header>
    {error ? <div role="alert" className="rounded-control border border-danger/30 bg-danger/5 p-4 text-sm"><p>{error}</p>{onRetry ? <Button size="sm" variant="ghost" onClick={onRetry} disabled={loading || disabled}>重试</Button> : null}</div> : null}
    {loading && !fieldsView ? <div role="status" aria-label="正在加载记录"><Skeleton className="h-64" /></div> : fieldsView ? <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      {fieldsView}
      <aside className="grid min-w-0 gap-5"><section aria-label="业务状态" className="rounded-card border border-line bg-surface p-5"><h2 className="mb-4 text-base font-semibold">业务状态</h2>{statusForm}</section>
        <section aria-label="时间信息" className="rounded-card border border-line bg-surface p-5"><h2 className="mb-4 text-base font-semibold">时间信息</h2><dl className="grid gap-4 text-sm">{[['创建时间', createdAt], ['更新时间', updatedAt]].map(([label, value]) => <div key={label}><dt className="mb-1 text-muted">{label}</dt><dd className="m-0 break-words"><time dateTime={value}>{value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无记录'}</time></dd></div>)}</dl></section>
      </aside>
    </div> : null}
  </section>
}
