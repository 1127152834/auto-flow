import type { ProjectOverview } from '../types'

const counters: { key: string; label: string }[] = [
  { key: 'automations', label: '自动化' },
  { key: 'tables', label: '数据表' },
  { key: 'batches', label: '运行批次' },
  { key: 'environments', label: '环境' },
]

export function OverviewCounts({ counts, dataChanges }: { counts: ProjectOverview['counts']; dataChanges?: ProjectOverview['dataChanges'] }) {
  return <dl aria-label="项目计数" className="m-0 grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
    {counters.map(counter => <div key={counter.key} className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">{counter.label}</dt>
      <dd className="m-0 mt-1 text-xl font-semibold tabular-nums text-ink">{counts[counter.key] ?? 0}</dd>
    </div>)}
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">今日数据变化</dt>
      <dd className="m-0 mt-1 text-sm text-ink">{dataChanges ? `新增 ${dataChanges.newRecords} · 更新 ${dataChanges.updatedRecords}` : '暂无数据'}</dd>
      {dataChanges ? <p className="mb-0 mt-1 text-xs text-muted">统计口径：{dataChanges.timezone}</p> : null}
    </div>
  </dl>
}
