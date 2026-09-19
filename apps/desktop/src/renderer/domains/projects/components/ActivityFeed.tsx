import { Button } from '../../../shared/components/ui/button'
import type { ProjectOverview } from '../types'
import { resourceLabel, resourceRoute, type ResourceLocator } from './overview-resource'

type Entry = ProjectOverview['recent'][number]
type Route = NonNullable<ReturnType<typeof resourceRoute>>

/** 项目活动 = 进行中的当前工作 + 已记录的最近活动。两组都只渲染已提交事实。 */
export function ActivityFeed({ current = [], items, onOpen }: { current?: ProjectOverview['current']; items: ProjectOverview['recent']; onOpen(route: Route): void }) {
  return <section aria-label="项目活动" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <h2 className="m-0 text-sm font-semibold text-ink">项目活动</h2>
    <Group name="当前工作" label="当前" empty="当前没有进行中的工作。" entries={current} onOpen={onOpen} />
    <Group name="最近活动" label="最近" empty="还没有运行或数据变更记录。" entries={items} onOpen={onOpen} />
  </section>
}

function Group({ name, label, empty, entries, onOpen }: { name: string; label: string; empty: string; entries: Entry[]; onOpen(route: Route): void }) {
  return <section aria-label={name} className="grid min-w-0 gap-2">
    <h3 className="m-0 text-xs font-medium text-muted">{label}</h3>
    {entries.length === 0
      ? <p className="m-0 text-sm text-muted">{empty}</p>
      : <ul className="m-0 grid list-none gap-2 p-0">
        {entries.map(entry => <Row key={entry.activityId} entry={entry} onOpen={onOpen} />)}
      </ul>}
  </section>
}

function Row({ entry, onOpen }: { entry: Entry; onOpen(route: Route): void }) {
  const route = resourceRoute(entry.resource as ResourceLocator)
  return <li className="flex min-w-0 items-start gap-3 border-b border-line pb-2 last:border-b-0 last:pb-0">
    <div className="min-w-0 flex-1">
      <p className="m-0 break-words text-sm text-ink">{entry.summary}</p>
      <p className="mb-0 mt-1 flex gap-2 text-xs text-muted">
        <span>{resourceLabel(entry.resource.type)}</span>
        <time dateTime={entry.occurredAt}>{new Date(entry.occurredAt).toLocaleString('zh-CN', { hour12: false })}</time>
      </p>
    </div>
    {route
      ? <Button size="sm" variant="ghost" className="shrink-0" onClick={() => onOpen(route)}>打开</Button>
      : <Button size="sm" variant="ghost" className="shrink-0" disabled title="该对象没有可打开的页面">打开</Button>}
  </li>
}
