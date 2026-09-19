import type { components } from '../../../shared/api/generated'

type Bucket = components['schemas']['StatisticsBucket']

export type StatisticsTrendProps = {
  buckets: Bucket[]
  timezone: string
  emptyRangeLabel: string
  from?: string
  to?: string
  interval?: 'day' | 'week' | 'month'
  onDrillDown?(result: 'failed', intervalStart: string): void
}

type Row = { kind: 'gap'; key: string; start: string; end: string } | { kind: 'bucket'; bucket: Bucket }

const day = (value: string, timezone: string) => new Date(value).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', timeZone: timezone })
const ended = (bucket: Bucket) => bucket.succeeded + bucket.failed + bucket.cancelled + bucket.timed_out + bucket.interrupted
const share = (value: number, peak: number) => `${Math.round(value / peak * 100)}%`
const STEP: Record<'day' | 'week', number> = { day: 86_400_000, week: 604_800_000 }

/**
 * Bucket rows are the server's; gap rows only label the window between two
 * returned buckets and never synthesise counts.
 * ponytail: day/week gaps step by fixed milliseconds. Month buckets render
 * without gap rows instead of guessing calendar arithmetic in the browser.
 */
function buildRows(buckets: Bucket[], from: string | undefined, to: string | undefined, interval: 'day' | 'week' | 'month' | undefined): Row[] {
  const sorted = [...buckets].sort((left, right) => left.bucketStart.localeCompare(right.bucketStart))
  const step = interval === 'day' || interval === 'week' ? STEP[interval] : null
  const rows: Row[] = []
  if (!step || !from || !sorted.length) return sorted.map(bucket => ({ kind: 'bucket', bucket }))
  let cursor = new Date(from).getTime()
  for (const bucket of sorted) {
    const start = new Date(bucket.bucketStart).getTime()
    if (cursor < start) rows.push({ kind: 'gap', key: `gap:${cursor}`, start: new Date(cursor).toISOString(), end: new Date(start - step).toISOString() })
    rows.push({ kind: 'bucket', bucket })
    cursor = start + step
  }
  if (to && cursor < new Date(to).getTime()) rows.push({ kind: 'gap', key: `gap:${cursor}`, start: new Date(cursor).toISOString(), end: to })
  return rows
}

export function StatisticsTrend({ buckets, timezone, emptyRangeLabel, from, to, interval, onDrillDown }: StatisticsTrendProps) {
  const peak = Math.max(1, ...buckets.map(ended))
  const rows = buildRows(buckets, from, to, interval)
  return <section aria-label="按日处理量" className="grid min-w-0 content-start gap-3 rounded-card border border-line bg-surface p-5">
    <header><h3 className="m-0 text-lg">按日处理量</h3><p className="m-0 mt-1 text-sm text-muted">按结束时间</p></header>
    {buckets.length === 0
      ? <p className="m-0 rounded-control border border-line bg-surface-subtle p-3 text-sm text-muted">{emptyRangeLabel} 无已结束任务。</p>
      : <ol className="m-0 grid list-none gap-4 p-0">
        {rows.map(item => item.kind === 'gap'
          ? <li key={item.key} className="text-sm text-muted">{day(item.start, timezone)} — {day(item.end, timezone)} 无已结束任务。</li>
          : <li key={item.bucket.bucketStart} className="grid gap-2">
            <div className="flex items-center gap-3">
              <span className="w-24 shrink-0 text-sm">{day(item.bucket.bucketStart, timezone)}</span>
              <span className="flex h-3 min-w-0 flex-1 overflow-hidden rounded-control bg-surface-subtle"><span className="h-full bg-success" style={{ width: share(item.bucket.succeeded, peak) }}/><span className="h-full bg-danger" style={{ width: share(ended(item.bucket) - item.bucket.succeeded, peak) }}/></span>
              <span className="w-16 shrink-0 text-right text-sm tabular-nums">{ended(item.bucket)} 个</span>
            </div>
            <p className="m-0 pl-24 text-sm text-muted">成功 {item.bucket.succeeded} · 失败 <button type="button" className="border-0 bg-transparent p-0 text-danger underline-offset-2 hover:underline disabled:no-underline" disabled={!onDrillDown || item.bucket.failed === 0} onClick={() => onDrillDown?.('failed', item.bucket.bucketStart)}>{item.bucket.failed}</button></p>
          </li>)}
      </ol>}
  </section>
}
