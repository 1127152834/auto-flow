import type { ReactNode } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
export function RecordEditPage({ mode, editorForm, footer, identity, statusName = '未设置', loading, error, disabled, onBack, onRetry, onStatus }: {
  mode: 'create' | 'edit'; editorForm?: ReactNode; footer?: ReactNode; identity?: string; statusName?: string; loading?: boolean; error?: string | null; disabled?: boolean; onBack(): void; onRetry?(): void; onStatus?(): void
}) {
  return <section aria-label={mode === 'create' ? '新增记录' : '编辑记录'} className="grid min-w-0 gap-5" data-record-page={mode}>
    <Button size="sm" variant="ghost" className="w-fit px-0" onClick={onBack} disabled={disabled}>返回记录列表</Button>
    <h1 className="m-0 text-2xl font-semibold">{mode === 'create' ? '新增记录' : '编辑记录'}</h1>
    {error ? <div role="alert" className="rounded-control border border-danger/30 bg-danger/5 p-4 text-sm"><p>{error}</p>{onRetry ? <Button size="sm" variant="ghost" onClick={onRetry} disabled={loading || disabled}>重试</Button> : null}</div> : null}
    {loading && !editorForm ? <div role="status" aria-label="正在加载记录表单"><Skeleton className="h-64" /></div> : editorForm ? <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section aria-label="基本信息" className="min-w-0 rounded-card border border-line bg-surface p-6"><h2 className="mb-5 text-base font-semibold">基本信息</h2>{identity ? <div className="mb-5 border-b border-line pb-4 text-sm"><p className="mb-1 text-muted">记录身份 · 只读</p><p className="break-all">{identity}</p></div> : null}{editorForm}</section>
      <aside className="grid min-w-0 gap-5"><section aria-label="业务状态" className="rounded-card border border-line bg-surface p-5"><h2 className="mb-4 text-base font-semibold">业务状态</h2><p className="text-sm">{mode === 'create' ? '未设置' : statusName}</p><p className="mt-3 text-sm leading-6 text-muted">{mode === 'create' ? '新记录的业务状态默认为未设置。创建后可在记录详情中设置。' : '保存字段内容不会修改业务状态。请在记录详情中单独设置。'}</p>{mode === 'edit' && onStatus ? <Button className="mt-3" size="sm" variant="ghost" onClick={onStatus} disabled={disabled}>前往设置业务状态</Button> : null}</section>
        {mode === 'edit' ? <p className="rounded-card border border-clay/20 bg-clay/5 p-4 text-sm leading-6 text-muted">未修改的异常单元格保留原始证据，无需修复整行即可修改其他字段。</p> : null}
      </aside>
    </div> : null}
    {editorForm && footer ? <footer className="sticky bottom-0 z-[var(--layer-sticky)] flex min-w-0 flex-wrap items-center justify-end gap-3 rounded-card border border-line bg-surface p-4 shadow-sm">{footer}</footer> : null}
  </section>
}
