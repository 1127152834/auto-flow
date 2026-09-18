import { Button } from '../../../shared/components/ui/button'
import type { ProjectOverview } from '../types'
import { resourceLabel, resourceRoute, type ResourceLocator } from './overview-resource'

export function ActivityFeed({ items, onOpen }: { items: ProjectOverview['recent']; onOpen(route: NonNullable<ReturnType<typeof resourceRoute>>): void }) {
  return <section aria-label="最近活动" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <h2 className="m-0 text-sm font-semibold text-ink">最近活动</h2>
    {items.length === 0
      ? <p className="m-0 text-sm text-muted">还没有运行或数据变更记录。</p>
      : <ul className="m-0 grid list-none gap-2 p-0">
        {items.map(item => {
          const route = resourceRoute(item.resource as ResourceLocator)
          return <li key={item.activityId} className="flex min-w-0 items-start gap-3 border-b border-line pb-2 last:border-b-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <p className="m-0 break-words text-sm text-ink">{item.summary}</p>
              <p className="mb-0 mt-1 flex gap-2 text-xs text-muted">
                <span>{resourceLabel(item.resource.type)}</span>
                <time dateTime={item.occurredAt}>{new Date(item.occurredAt).toLocaleString('zh-CN', { hour12: false })}</time>
              </p>
            </div>
            {route
              ? <Button size="sm" variant="ghost" className="shrink-0" onClick={() => onOpen(route)}>打开</Button>
              : <Button size="sm" variant="ghost" className="shrink-0" disabled title="该对象没有可打开的页面">打开</Button>}
          </li>
        })}
      </ul>}
  </section>
}
