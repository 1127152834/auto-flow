import { Button } from '../../../shared/components/ui/button'
import type { ProjectOverview } from '../types'
import { resourceLabel, resourceRoute, type ResourceLocator } from './overview-resource'

const severityClass: Record<string, string> = {
  info: 'border-line bg-surface',
  warning: 'border-amber-500/40 bg-amber-500/5',
  error: 'border-danger/40 bg-danger/5',
}

export function AttentionList({ items, onOpen }: { items: ProjectOverview['activity']; onOpen(route: NonNullable<ReturnType<typeof resourceRoute>>): void }) {
  if (items.length === 0) return null
  return <section aria-label="需要关注" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <h2 className="m-0 text-sm font-semibold text-ink">需要关注<span className="ml-2 font-normal tabular-nums text-muted">{items.length}</span></h2>
    <ul className="m-0 grid list-none gap-2 p-0">
      {items.map(item => {
        const route = resourceRoute(item.resource as ResourceLocator)
        return <li key={`${item.kind}:${item.occurredAt}:${item.message}`} className={`min-w-0 rounded-control border px-3 py-2 ${severityClass[item.severity] ?? severityClass.info}`}>
          <p className="m-0 break-words text-sm text-ink">{item.message}</p>
          <p className="mb-0 mt-1 flex min-w-0 items-center gap-2 text-xs text-muted">
            <span className="shrink-0">{resourceLabel(item.resource.type)}</span>
            <time dateTime={item.occurredAt} className="min-w-0 truncate">{new Date(item.occurredAt).toLocaleString('zh-CN', { hour12: false })}</time>
            {route
              ? <Button size="sm" variant="ghost" className="ml-auto shrink-0" onClick={() => onOpen(route)}>查看</Button>
              : <span className="ml-auto shrink-0" title="该对象没有可打开的页面">暂不可打开</span>}
          </p>
        </li>
      })}
    </ul>
  </section>
}
