import { MagnifyingGlass, Pulse } from '@phosphor-icons/react'
import type { ProxyFilters, ProxyPage, ProxyView } from '../api'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { HealthPill, StatusPill } from './presentation'

export function ProxySummary({ page }: { page: ProxyPage }) {
  const healthy = page.items.filter((proxy) => proxy.health.state === 'healthy').length
  const unhealthy = page.items.filter((proxy) => proxy.health.state === 'unhealthy').length
  return (
    <section className="grid gap-3 sm:grid-cols-3" aria-label="代理摘要">
      <SummaryCard label="已同步" value={page.matched_count} detail="当前筛选结果" />
      <SummaryCard label="当前页健康" value={healthy} detail="基于本地 HTTPS 探测" tone="success" />
      <SummaryCard label="当前页异常" value={unhealthy} detail="不包含连接同步错误" tone={unhealthy ? 'danger' : 'neutral'} />
    </section>
  )
}

function SummaryCard({ label, value, detail, tone = 'neutral' }: {
  label: string
  value: number
  detail: string
  tone?: 'success' | 'danger' | 'neutral'
}) {
  const colors = tone === 'success' ? 'text-sage-strong' : tone === 'danger' ? 'text-red-700' : 'text-ink'
  return (
    <article className="rounded-card border border-line bg-surface p-5 shadow-sm">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${colors}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{detail}</p>
    </article>
  )
}

type ProxyTableProps = {
  page: ProxyPage
  filters: ProxyFilters
  checkingId?: string
  retryAfterSeconds?: number
  onFiltersChange: (filters: ProxyFilters) => void
  onOpen: (proxy: ProxyView) => void
  onProbe: (proxy: ProxyView) => void
}

export function ProxyTable({ page, filters, checkingId, retryAfterSeconds = 0, onFiltersChange, onOpen, onProbe }: ProxyTableProps) {
  const carriers = uniqueValues([...page.items.map((item) => item.carrier), filters.carrier])
  const cities = uniqueValues([...page.items.map((item) => item.city), filters.city])

  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface shadow-sm" aria-labelledby="proxy-fleet-title">
      <div className="flex flex-col gap-4 border-b border-line p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="font-semibold text-ink" id="proxy-fleet-title">ProxyPanel 代理</h2>
          <p className="mt-1 text-sm text-muted">远程代理的本地同步投影</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(15rem,1fr)_10rem_10rem_10rem]">
          <label className="relative sm:col-span-2 lg:col-span-1">
            <span className="sr-only">搜索代理</span>
            <MagnifyingGlass className="pointer-events-none absolute left-3 top-3 text-muted" />
            <Input className="pl-9" value={filters.q ?? ''} placeholder="搜索名称、城市、IP 或运营商" onChange={(event) => onFiltersChange({ ...filters, q: event.target.value, offset: 0 })} />
          </label>
          <Select aria-label="健康状态" value={filters.health ?? ''} onChange={(event) => onFiltersChange({ ...filters, health: event.target.value as ProxyFilters['health'], offset: 0 })}>
            <option value="">全部健康状态</option>
            <option value="healthy">健康</option>
            <option value="unhealthy">异常</option>
            <option value="untested">未检测</option>
          </Select>
          <Select aria-label="运营商" value={filters.carrier ?? ''} onChange={(event) => onFiltersChange({ ...filters, carrier: event.target.value, offset: 0 })}>
            <option value="">全部运营商</option>
            {carriers.map((value) => <option value={value} key={value}>{value}</option>)}
          </Select>
          <Select aria-label="城市" value={filters.city ?? ''} onChange={(event) => onFiltersChange({ ...filters, city: event.target.value, offset: 0 })}>
            <option value="">全部城市</option>
            {cities.map((value) => <option value={value} key={value}>{value}</option>)}
          </Select>
        </div>
      </div>
      {page.items.length === 0 ? (
        <div className="grid min-h-48 place-items-center p-8 text-center">
          <div><p className="font-medium text-ink">当前连接没有匹配的已同步代理</p><p className="mt-1 text-sm text-muted">调整筛选条件或刷新代理。</p></div>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
            <thead className="bg-surface-subtle text-xs text-muted">
              <tr>
                {['代理名称', '远程状态', '本地健康', '运营商', '城市', '出口 IP', '延迟', '关联配置', '操作'].map((label) => <th className="whitespace-nowrap px-4 py-3 font-medium" scope="col" key={label}>{label}</th>)}
              </tr>
            </thead>
            <tbody>
              {page.items.map((proxy) => (
                <tr className="border-t border-line hover:bg-surface-hover" key={proxy.id}>
                  <td className="min-w-48 max-w-xs break-words px-4 py-3 font-medium text-ink">
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{proxy.name_override || proxy.name}</span>
                      {proxy.stale ? <StatusPill tone="warning">待同步</StatusPill> : null}
                    </div>
                  </td>
                  <td className="px-4 py-3"><StatusPill tone={proxy.remote_missing ? 'danger' : 'neutral'}>{proxy.remote_missing ? '远端缺失' : proxy.remote_status || '未知'}</StatusPill></td>
                  <td className="px-4 py-3"><HealthPill health={proxy.health} /></td>
                  <td className="whitespace-nowrap px-4 py-3 text-muted">{proxy.carrier || '—'}</td>
                  <td className="px-4 py-3 text-muted">{[proxy.city, proxy.region].filter(Boolean).join(', ') || '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted">{proxy.exit_ip || proxy.health.exit_ip || '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-muted">{proxy.health.latency_ms == null ? '—' : `${Math.round(proxy.health.latency_ms)} ms`}</td>
                  <td className="px-4 py-3 text-muted">{proxy.reference_count}</td>
                  <td className="w-40 whitespace-nowrap px-4 py-3">
                    <div className="flex gap-1">
                      <Button className="h-8 shrink-0 whitespace-nowrap px-3" variant="ghost" onClick={() => onOpen(proxy)}>详情</Button>
                      <Button className="h-8 shrink-0 whitespace-nowrap px-3" variant="ghost" disabled={retryAfterSeconds > 0 || checkingId === proxy.id || !proxy.credential_available || proxy.remote_missing || (!proxy.http_endpoint && !proxy.socks5_endpoint)} onClick={() => onProbe(proxy)}>
                        <Pulse className={checkingId === proxy.id ? 'animate-pulse' : ''} />检测
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 text-sm text-muted">
        <span>共 {page.matched_count} 个匹配项</span>
        {page.matched_count > page.limit ? <div className="flex items-center gap-2"><span>显示 {page.offset + 1}–{Math.min(page.offset + page.items.length, page.matched_count)}</span><Button className="h-8 px-3" disabled={page.offset === 0} onClick={() => onFiltersChange({ ...filters, offset: Math.max(0, page.offset - page.limit) })}>上一页</Button><Button className="h-8 px-3" disabled={page.offset + page.items.length >= page.matched_count} onClick={() => onFiltersChange({ ...filters, offset: page.offset + page.limit })}>下一页</Button></div> : null}
      </footer>
    </section>
  )
}

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b))
}
