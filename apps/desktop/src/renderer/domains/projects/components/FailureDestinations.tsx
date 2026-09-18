import { SquaresFour } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'

type FailureDestination = components['schemas']['FailureDestination']

/** 失败任务去向: counts come from the frozen result set, never from a second live query. */
export function FailureDestinations({ items, onOpen }: { items: FailureDestination[]; onOpen?(automationId: string): void }) {
  return <section aria-label="失败任务去向" className="grid min-w-0 content-start gap-3 rounded-card border border-line bg-surface p-5">
    <h3 className="m-0 text-lg">失败任务去向</h3>
    {items.length === 0
      ? <p className="m-0 text-sm text-muted">本区间没有失败任务。</p>
      : <ul className="m-0 grid list-none gap-3 p-0">
        {items.map(item => <li key={item.automationId} className="flex min-w-0 items-start gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
          <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-control bg-clay-soft text-clay"><SquaresFour size={18} /></span>
          <div className="min-w-0 flex-1">
            <p className="m-0 break-words text-sm font-medium text-ink">{item.name}</p>
            {item.reasonSummary ? <p className="m-0 mt-1 break-words text-xs text-muted">{item.reasonSummary}</p> : null}
          </div>
          <span className="shrink-0 text-sm tabular-nums text-ink">{item.count} 个</span>
          <button type="button" className="shrink-0 border-0 bg-transparent p-0 text-sm text-clay underline-offset-2 hover:underline disabled:text-muted disabled:no-underline" disabled={!onOpen} onClick={() => onOpen?.(item.automationId)}>查看记录 →</button>
        </li>)}
      </ul>}
  </section>
}
