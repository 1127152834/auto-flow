import { Button } from '../../../shared/components/ui/button'
import type { ProjectOverview } from '../types'
import { resourceLabel, resourceRoute, type ResourceLocator } from './overview-resource'

const MAX_ENTRIES = 4

/** Entries come from recorded facts only; nothing is prefilled from a prototype. */
export function ContinueWork({ items, onOpen }: { items: ProjectOverview['recent']; onOpen(route: NonNullable<ReturnType<typeof resourceRoute>>): void }) {
  const seen = new Set<string>()
  const entries: { key: string; label: string; summary: string; route: NonNullable<ReturnType<typeof resourceRoute>> }[] = []
  for (const item of items) {
    const route = resourceRoute(item.resource as ResourceLocator)
    if (!route) continue
    const key = `${item.resource.type}:${item.activityId}`
    if (seen.has(key)) continue
    seen.add(key)
    entries.push({ key, label: resourceLabel(item.resource.type), summary: item.summary, route })
    if (entries.length === MAX_ENTRIES) break
  }
  if (entries.length === 0) return null
  return <section aria-label="继续工作" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <h2 className="m-0 text-sm font-semibold text-ink">继续工作</h2>
    <ul className="m-0 grid list-none gap-2 p-0">
      {entries.map(entry => <li key={entry.key} className="flex min-w-0 items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="m-0 text-xs text-muted">{entry.label}</p>
          <p className="m-0 break-words text-sm text-ink">{entry.summary}</p>
        </div>
        <Button size="sm" className="shrink-0" onClick={() => onOpen(entry.route)}>继续</Button>
      </li>)}
    </ul>
  </section>
}
