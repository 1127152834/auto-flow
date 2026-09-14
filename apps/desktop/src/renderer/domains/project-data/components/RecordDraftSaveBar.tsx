import { Button } from '../../../shared/components/ui/button'
export type GridSaveState = 'draft' | 'submitting' | 'uncertain' | 'recovering' | 'notAccepted' | 'stale'
export function RecordDraftSaveBar({ count, state, disabled, saveDisabled, message, onSave, onDiscard, onReconcile }: {
  count: number; state: GridSaveState; disabled?: boolean; saveDisabled?: boolean; message?: string
  onSave(): void; onDiscard(): void; onReconcile(): void
}) {
  const pending = state === 'uncertain' || state === 'recovering' || state === 'submitting'
  return <><div aria-hidden className="h-28" /><footer aria-label="新增记录保存" className="fixed inset-x-4 bottom-3 z-10 mx-auto flex max-w-screen-xl min-w-0 flex-wrap items-center justify-between gap-3 rounded-panel border border-line bg-surface px-5 py-3 shadow-sm">
    <div aria-live="polite" className="min-w-0 text-sm"><span className="font-medium text-clay">{pending ? '保存结果待确认' : `未保存 · 新增 ${count} 行`}</span>
      {message ? <p className="mt-1 break-words text-muted">{message}</p> : null}</div>
    <div className="flex flex-wrap gap-2">
      {!pending ? <Button disabled={disabled} onClick={onDiscard}>放弃新增</Button> : null}
      {state === 'uncertain' || state === 'recovering' ? <Button disabled={disabled} variant="primary" loading={state === 'recovering'} onClick={onReconcile}>查询保存结果</Button>
        : <Button aria-label={state === 'submitting' ? `正在保存 ${count} 行` : state === 'notAccepted' ? '重发原请求' : `保存 ${count} 行`} variant="primary" disabled={disabled || saveDisabled || !count || state === 'stale'} loading={state === 'submitting'} loadingText={`正在保存 ${count} 行…`} onClick={onSave}>{state === 'notAccepted' ? '重发原请求' : `保存 ${count} 行`}</Button>}
    </div>
  </footer></>
}
