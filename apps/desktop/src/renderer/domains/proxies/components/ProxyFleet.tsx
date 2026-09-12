import { Spinner } from '../../../shared/components/ui/spinner'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../../shared/components/ui/table'
import { Combobox } from '../../../shared/components/ui/combobox'
import { Pagination } from '../../../shared/components/ui/pagination'
import { Pulse } from '@phosphor-icons/react'
import type { ProxyFilters, ProxyPage, ProxyView } from '../api'
import { Button } from '../../../shared/components/ui/button'
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
  const colors = tone === 'success' ? 'text-sage-strong' : tone === 'danger' ? 'text-danger' : 'text-ink'
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

            <SearchInput onClear={() => onFiltersChange({ ...filters, q: '', offset: 0 })}  value={filters.q ?? ''} placeholder="搜索名称、城市、IP 或运营商" onChange={(event) => onFiltersChange({ ...filters, q: event.target.value, offset: 0 })} />
          </label>
          <Select clearable={false} aria-label="健康状态" value={filters.health ?? ''} onValueChange={(value) => onFiltersChange({ ...filters, health: (value ?? '') as ProxyFilters['health'], offset: 0 })} options={[{ value: "", label: "全部健康状态" }, { value: "healthy", label: "健康" }, { value: "unhealthy", label: "异常" }, { value: "untested", label: "未检测" }]} />
          <Combobox aria-label="运营商" value={filters.carrier ?? ''} onValueChange={(value) => onFiltersChange({ ...filters, carrier: (value ?? ''), offset: 0 })} options={[{ value: "", label: "全部运营商" }, ...carriers.map((value) => ({ value: value, label: String(value) }))]} />
          <Combobox aria-label="城市" value={filters.city ?? ''} onValueChange={(value) => onFiltersChange({ ...filters, city: (value ?? ''), offset: 0 })} options={[{ value: "", label: "全部城市" }, ...cities.map((value) => ({ value: value, label: String(value) }))]} />
        </div>
      </div>
      {page.items.length === 0 ? (
        <div className="grid min-h-48 place-items-center p-8 text-center">
          <div><p className="font-medium text-ink">当前连接没有匹配的已同步代理</p><p className="mt-1 text-sm text-muted">调整筛选条件或刷新代理。</p></div>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <Table className="w-full min-w-[1080px] border-collapse text-left text-sm">
            <TableHeader className="bg-surface-subtle text-xs text-muted">
              <TableRow>
                {['代理名称', '远程状态', '本地健康', '运营商', '城市', '出口 IP', '延迟', '关联配置', '操作'].map((label) => <TableHead className="whitespace-nowrap px-4 py-3 font-medium" scope="col" key={label}>{label}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((proxy) => (
                <TableRow className="border-t border-line hover:bg-surface-hover" key={proxy.id}>
                  <TableCell className="min-w-48 max-w-xs break-words px-4 py-3 font-medium text-ink">
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{proxy.name_override || proxy.name}</span>
                      {proxy.stale ? <StatusPill tone="warning">待同步</StatusPill> : null}
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3"><StatusPill tone={proxy.remote_missing ? 'danger' : 'neutral'}>{proxy.remote_missing ? '远端缺失' : proxy.remote_status || '未知'}</StatusPill></TableCell>
                  <TableCell className="px-4 py-3"><HealthPill health={proxy.health} /></TableCell>
                  <TableCell className="whitespace-nowrap px-4 py-3 text-muted">{proxy.carrier || '—'}</TableCell>
                  <TableCell className="px-4 py-3 text-muted">{[proxy.city, proxy.region].filter(Boolean).join(', ') || '—'}</TableCell>
                  <TableCell className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted">{proxy.exit_ip || proxy.health.exit_ip || '—'}</TableCell>
                  <TableCell className="whitespace-nowrap px-4 py-3 text-muted">{proxy.health.latency_ms == null ? '—' : `${Math.round(proxy.health.latency_ms)} ms`}</TableCell>
                  <TableCell className="px-4 py-3 text-muted">{proxy.reference_count}</TableCell>
                  <TableCell className="w-40 whitespace-nowrap px-4 py-3">
                    <div className="flex gap-1">
                      <Button className="h-8 shrink-0 whitespace-nowrap px-3" variant="ghost" onClick={() => onOpen(proxy)}>详情</Button>
                      <Button className="h-8 shrink-0 whitespace-nowrap px-3" variant="ghost" aria-busy={checkingId === proxy.id} disabled={retryAfterSeconds > 0 || checkingId === proxy.id || !proxy.credential_available || proxy.remote_missing || (!proxy.http_endpoint && !proxy.socks5_endpoint)} onClick={() => onProbe(proxy)}>
                        {checkingId === proxy.id ? <Spinner  aria-hidden="true" /> : <Pulse aria-hidden="true" />}检测
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <footer className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 text-sm text-muted">
        <span>共 {page.matched_count} 个匹配项</span>
        <Pagination offset={page.offset} limit={page.limit} total={page.matched_count} count={page.items.length} onOffsetChange={offset => onFiltersChange({...filters, offset})} />
      </footer>
    </section>
  )
}

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b))
}
