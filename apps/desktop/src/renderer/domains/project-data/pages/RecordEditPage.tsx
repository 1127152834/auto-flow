import type { ReactNode } from 'react'
import { Info } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
export function RecordEditPage({ mode, editorForm, footer, embedded = false, loading, error, disabled, onBack, onRetry }: {
  mode: 'create' | 'edit'; editorForm?: ReactNode; footer?: ReactNode; embedded?: boolean; loading?: boolean; error?: string | null; disabled?: boolean; onBack(): void; onRetry?(): void
}) {
  return <section aria-label={mode === 'create' ? '新增记录' : '编辑记录'} className="grid min-w-0 gap-5" data-record-page={mode}>
    {!embedded ? <h1 className="m-0 text-2xl font-semibold">{mode === 'create' ? '新增记录' : '编辑记录'}</h1> : null}
    {error ? <div role="alert" className="rounded-control border border-danger/30 bg-danger/5 p-4 text-sm"><p>{error}</p>{onRetry ? <Button size="sm" variant="ghost" onClick={onRetry} disabled={loading || disabled}>重试</Button> : null}</div> : null}
    {loading && !editorForm ? <div role="status" aria-label="正在加载记录表单"><Skeleton className="h-64" /></div> : editorForm}
    <p className="m-0 flex items-center gap-2 text-sm text-muted"><Info size={20} />业务状态在记录详情中单独维护。</p>
    {editorForm && footer ? <footer className="sticky bottom-0 z-[var(--layer-sticky)] -mx-5 -mb-5 flex min-w-0 flex-wrap items-center justify-end gap-3 border-t border-line bg-surface p-5">{footer}</footer> : !editorForm && !loading ? <Button variant="ghost" className="w-fit" onClick={onBack}>返回记录列表</Button> : null}
  </section>
}
