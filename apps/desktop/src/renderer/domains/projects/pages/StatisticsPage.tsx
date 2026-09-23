import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { createAutomationApi } from '../../project-automations/api'
import { FailureDestinations } from '../components/FailureDestinations'
import { StatisticsTrend } from '../components/StatisticsTrend'
import { StudioStatisticsPanel } from '../components/StudioStatisticsPanel'
import { createProjectStatisticsApi, type ProjectStatistics, type StatisticsInterval } from '../statistics-api'
import type { RunFrozen } from '../types'

type Range = '7d' | '30d' | '90d'
type Browse = { range: Range; automationId: string | null; interval: StatisticsInterval; scroll: number }

const rangeOptions: { value: Range; label: string }[] = [
  { value: '7d', label: '近7天' },
  { value: '30d', label: '近30天' },
  { value: '90d', label: '近90天' },
]
const rangeDays: Record<Range, number> = { '7d': 7, '30d': 30, '90d': 90 }
const initialBrowse: Browse = { range: '7d', automationId: null, interval: 'day', scroll: 0 }
const DAY = 86_400_000
const zone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const dayLabel = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', hour12: false })
const momentLabel = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })

/**
 * 每次挂载都会生成新的时间窗口与查询键，React Query 无法自行保留上一次结果；
 * 契约要求刷新失败时保留上次范围与数值并标明过期，所以按工作区+项目记下最后一次成功快照。
 */
function readSnapshot(key: string): { data: ProjectStatistics; window: { from: string; to: string } } | null {
  try {
    const raw = sessionStorage.getItem(`${key}:snapshot`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { data?: ProjectStatistics; window?: { from?: unknown; to?: unknown } }
    const from = parsed.window?.from
    const to = parsed.window?.to
    if (!parsed.data || typeof from !== 'string' || typeof to !== 'string') return null
    return { data: parsed.data, window: { from, to } }
  } catch {
    return null
  }
}

const formatPercent = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : null
function formatDuration(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  if (value < 1000) return `${Math.round(value)} 毫秒`
  if (value < 60_000) return `${Math.round(value / 1000)} 秒`
  const minutes = Math.floor(value / 60_000)
  return `${minutes} 分 ${Math.round((value - minutes * 60_000) / 1000)} 秒`
}

export function presentStatisticsError(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === 'STATISTICS_RESULT_EXPIRED') return '统计结果已过期，请刷新后重试'
    if (error.status === 422) return '统计条件无效，请调整区间或自动化筛选'
    if (error.status === 404) return '统计结果在当前项目找不到'
  }
  return '统计读取失败，请稍后重试'
}

function restore(key: string): Browse {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return initialBrowse
    const saved = JSON.parse(raw) as Partial<Browse>
    return {
      range: rangeOptions.some(option => option.value === saved.range) ? (saved.range as Range) : '7d',
      automationId: typeof saved.automationId === 'string' ? saved.automationId : null,
      interval: 'day',
      scroll: typeof saved.scroll === 'number' && Number.isFinite(saved.scroll) ? saved.scroll : 0,
    }
  } catch {
    return initialBrowse
  }
}

/** 统计页：一次冻结窗口同时驱动四指标、趋势、失败去向与下钻集合。 */
export function StatisticsPage({
  workspaceKey,
  instanceId,
  projectId,
  client,
  disabled,
  onOpenRuns,
  onOpenFailures,
}: {
  workspaceKey: string
  instanceId: string
  projectId: string
  client: StreamingApiClient
  disabled: boolean
  onOpenRuns(): void
  onOpenFailures(frozen: RunFrozen): void
}) {
  const key = `autoflow:statistics:${JSON.stringify([workspaceKey, projectId])}`
  const [browse, setBrowse] = useState(() => restore(key))
  const [drillFailure, setDrillFailure] = useState<string | null>(null)
  const [showStudio, setShowStudio] = useState(false)
  const api = useMemo(() => createProjectStatisticsApi(client, projectId), [client, projectId])
  const automations = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const timezone = useMemo(zone, [])
  const interval = browse.interval
  const window_ = useMemo(() => {
    const to = new Date()
    return { from: new Date(to.getTime() - rangeDays[browse.range] * DAY).toISOString(), to: to.toISOString() }
  }, [browse.range])

  const stats = useQuery({
    queryKey: [workspaceKey, instanceId, 'project-statistics', projectId, window_, browse.automationId, interval],
    queryFn: ({ signal }) => api.get({ ...window_, timezone, ...(browse.automationId ? { automationId: browse.automationId } : {}), interval }, signal),
    enabled: !disabled,
    placeholderData: previous => previous,
  })
  const [snapshot, setSnapshot] = useState(() => readSnapshot(key))
  const options = useQuery({
    queryKey: [workspaceKey, instanceId, 'project-statistics-automations', projectId],
    enabled: !disabled,
    queryFn: async ({ signal }) => {
      const result: { id: string; name: string }[] = []
      for (let page = 1; ; page++) {
        const data = await automations.list({ page, pageSize: 200, sort: 'name', query: '' }, signal)
        result.push(...data.items.map(item => ({ id: item.automationId, name: item.name })))
        if (page * 200 >= data.total || data.items.length === 0) return result
      }
    },
  })

  useEffect(() => {
    try { sessionStorage.setItem(key, JSON.stringify(browse)) } catch { /* Viewing stays available without storage. */ }
  }, [key, browse])
  useEffect(() => {
    if (!stats.data) return
    const next = { data: stats.data, window: { from: window_.from, to: window_.to } }
    setSnapshot(next)
    try { sessionStorage.setItem(`${key}:snapshot`, JSON.stringify(next)) } catch { /* Viewing stays available without storage. */ }
  }, [key, stats.data, window_])
  const data = stats.data ?? snapshot?.data
  const shownWindow = stats.data ? window_ : snapshot?.window ?? window_
  const loaded = Boolean(data)
  useEffect(() => {
    if (loaded && browse.scroll > 0) window.scrollTo(0, browse.scroll)
    // Restoration happens once this view has data, not on every refresh.
  }, [loaded])

  const remember = () => setBrowse(value => ({ ...value, scroll: window.scrollY }))
  /** 下钻沿用同一冻结标识；按自动化查看时先取该自动化的冻结集合，不重跑实时筛选。 */
  const openFailures = async (automationId?: string, intervalStart?: string) => {
    if (!data) return
    setDrillFailure(null)
    try {
      const scoped = automationId && automationId !== browse.automationId
        ? await api.get({ ...shownWindow, timezone, automationId, interval })
        : data
      remember()
      onOpenFailures({ resultSetId: scoped.resultSetId, result: 'failed', ...(intervalStart ? { intervalStart } : {}), ...(automationId ? { automationId } : {}) })
    } catch (error) {
      setDrillFailure(presentStatisticsError(error))
    }
  }

  const error = stats.isError ? presentStatisticsError(stats.error) : null
  const automationOptions = [{ value: '', label: '全部自动化' }, ...(options.data ?? []).map(item => ({ value: item.id, label: item.name }))]
  const windowLabel = `${dayLabel.format(new Date(shownWindow.from))} — ${dayLabel.format(new Date(shownWindow.to))}（截至 ${momentLabel.format(new Date(shownWindow.to))}）`

  return <section aria-label="统计" className="grid min-w-0 gap-5">
    <details onToggle={event => setShowStudio(event.currentTarget.open)}><summary className="cursor-pointer">Studio 运行统计</summary>{showStudio ? <StudioStatisticsPanel {...{ workspaceKey, instanceId, projectId, client, disabled }} /> : null}</details>
    {stats.isLoading && !data ? <><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></> : null}
    {disabled && !data ? <p role="status" className="m-0 rounded-control border border-line bg-surface px-4 py-3 text-sm text-muted">本地服务暂不可用，统计会在连接恢复后重新加载。</p> : null}
    {error && !data ? <div role="alert" className="flex items-center gap-3 rounded-control border border-danger/30 bg-surface px-4 py-3 text-sm text-danger">
      <span>{error}</span>
      <Button size="sm" disabled={stats.isFetching} onClick={() => void stats.refetch()}>重试</Button>
    </div> : null}
    {data ? <>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="m-0 text-xl font-semibold text-ink">统计</h2>
          <p className="m-0 text-sm text-muted">按任务结束时间汇总</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select aria-label="自动化筛选" className="w-44" clearable={false} value={browse.automationId ?? ''} options={automationOptions} disabled={disabled} onValueChange={value => setBrowse(current => ({ ...current, automationId: value || null }))}/>
          <Select aria-label="统计区间" className="w-32" clearable={false} value={browse.range} options={rangeOptions} disabled={disabled} onValueChange={value => setBrowse(current => ({ ...current, range: value as Range }))}/>
          <p className="m-0 text-sm text-muted" aria-label="统计窗口">{windowLabel}</p>
          <Button size="sm" variant="ghost" onClick={onOpenRuns}>查看运行记录 →</Button>
        </div>
      </header>
      {error ? <p role="status" className="m-0 rounded-control border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-ink">
        统计刷新失败：{error}。以下是 {momentLabel.format(new Date(data.calculatedAt))} 的结果。
        <Button size="sm" className="ml-2" disabled={stats.isFetching} onClick={() => void stats.refetch()}>重新加载</Button>
      </p> : null}
      {drillFailure ? <p role="alert" className="m-0 rounded-control border border-danger/30 bg-surface px-3 py-2 text-sm text-danger">{drillFailure}</p> : null}
      <Metrics data={data} onDrillDown={() => void openFailures()}/>
      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <StatisticsTrend buckets={data.trend} timezone={data.timezone} emptyRangeLabel={`${dayLabel.format(new Date(window_.from))} — ${dayLabel.format(new Date(window_.to))}`} from={window_.from} to={window_.to} interval={interval} onDrillDown={(_result, intervalStart) => void openFailures(undefined, intervalStart)}/>
        <FailureDestinations items={data.failuresByAutomation} onOpen={automationId => void openFailures(automationId)}/>
      </div>
      <p className="m-0 flex items-center gap-3 border-t border-line pt-4 text-sm text-muted"><span>资源使用</span><span aria-hidden>—</span><span>尚未采集</span></p>
      <p className="m-0 text-xs text-muted">成功率 = 成功 /（成功 + 失败）；不计运行中与等待人工；任务数不等于数据新增量。</p>
    </> : null}
  </section>
}

function Metrics({ data, onDrillDown }: { data: ProjectStatistics; onDrillDown(): void }) {
  const sample = data.sample
  const finished = sample.succeeded + sample.failed + sample.cancelled + sample.timed_out + sample.interrupted
  const rate = formatPercent(data.successRate)
  const duration = formatDuration(data.averageDurationMs)
  return <dl aria-label="统计指标" className="m-0 grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">本期已结束任务</dt>
      <dd className="m-0 mt-1 text-2xl font-semibold tabular-nums text-ink">{finished} 个</dd>
      <p className="m-0 mt-1 text-xs text-muted">成功 {sample.succeeded} · 失败 <button type="button" className="border-0 bg-transparent p-0 text-danger underline-offset-2 hover:underline" onClick={onDrillDown}>{sample.failed}</button></p>
    </div>
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">任务成功率</dt>
      <dd className="m-0 mt-1 text-2xl font-semibold tabular-nums text-ink">{rate ?? '无样本'}</dd>
      <p className="m-0 mt-1 text-xs text-muted">{rate ? '成功 /（成功 + 失败）' : '本区间没有成功或失败任务'}</p>
    </div>
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">失败任务</dt>
      <dd className="m-0 mt-1 text-2xl font-semibold tabular-nums text-ink">{sample.failed} 个</dd>
      <p className="m-0 mt-1 text-xs text-muted">取消 {sample.cancelled} · 超时 {sample.timed_out} · 中断 {sample.interrupted}</p>
    </div>
    <div className="min-w-0 bg-surface px-4 py-3">
      <dt className="text-xs font-medium text-muted">平均任务耗时</dt>
      <dd className="m-0 mt-1 text-2xl font-semibold tabular-nums text-ink">{duration ?? '无有效样本'}</dd>
      <p className="m-0 mt-1 text-xs text-muted">{duration ? '成功与失败任务的已结束耗时' : '暂无起止时间完整的任务'}</p>
    </div>
  </dl>
}
