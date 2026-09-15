import { MagnifyingGlass } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { useEffect, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Select } from '../../../shared/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'

type Attempt = Omit<components['schemas']['NodeAttemptView'], 'nodeName'> & { nodeName?: string }
type Attempts = Omit<components['schemas']['NodeAttemptPage'], 'items'> & { items: Attempt[] }; type Logs = components['schemas']['RunLogPage']
const statuses: Record<string, string> = { running: '运行中', succeeded: '成功', failed: '失败' }
const tone = (status: string) => status === 'failed' ? 'danger' : status === 'succeeded' ? 'success' : 'neutral'
const nodeName = (nodeNames: Record<string, string> | undefined, nodeId: string | null | undefined, frozen?: string) => nodeId && nodeNames?.[nodeId]?.trim() || frozen?.trim() || '步骤'
const clock = (value: string | null) => value ? new Date(value).toLocaleTimeString('zh-CN', { hour12: false }) : '未执行'

export function TaskLog({ attempts, logs, nodeNames, selectedNode, level, query, loading, error, onNodeChange, onLevelChange, onQueryChange, onLoadMore, onLoadMoreAttempts, onRetry }: { attempts?: Attempts; logs?: Logs; nodeNames?: Record<string, string>; selectedNode: string | null; level: string | null; query: string; loading?: boolean; error?: string; onNodeChange(value: string | null): void; onLevelChange(value: string | null): void; onQueryChange(value: string): void; onLoadMore(): void; onLoadMoreAttempts(): void; onRetry(): void }) {
  const [searchDraft, setSearchDraft] = useState(query)
  useEffect(() => { setSearchDraft(query) }, [query])
  const groups = Array.from((attempts?.items ?? []).reduce((result, item) => {
    const current = result.get(item.nodeId) ?? []
    current.push(item); result.set(item.nodeId, current)
    return result
  }, new Map<string, Attempt[]>()))
  const nodeOptions = groups.map(([id, items]) => ({ value: id, label: nodeName(nodeNames, id, items[0]?.nodeName) }))
  const selectedGroup = groups.find(([id]) => id === selectedNode)?.[1]
  const selectedName = selectedNode ? nodeName(nodeNames, selectedNode, selectedGroup?.[0]?.nodeName) : null
  return <div className="grid min-w-0 gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
    <aside className="min-w-0 rounded-card border border-line bg-surface p-4">
      <h3 className="mt-0">节点时间线</h3>
      {groups.length ? <ol className="ml-3 grid list-none gap-1 border-l border-line py-1 pl-5">{groups.map(([id, items]) => {
        const latest = items.at(-1)!
        const name = nodeName(nodeNames, id, latest.nodeName)
        return <li className="relative min-w-0" key={id}><span aria-hidden className={'absolute -left-[1.72rem] top-4 size-3 rounded-full border-2 border-surface ' + (latest.status === 'failed' ? 'bg-danger' : latest.status === 'succeeded' ? 'bg-success' : 'bg-muted')}/><button type="button" title={name} aria-pressed={selectedNode === id} className="w-full min-w-0 rounded-control px-3 py-2 text-left hover:bg-surface-hover aria-pressed:bg-clay-soft" onClick={() => onNodeChange(id)}><span className="flex items-center justify-between gap-3"><strong className="truncate">{name}</strong><time className="shrink-0 text-xs text-muted" dateTime={latest.completedAt ?? latest.startedAt ?? undefined}>{clock(latest.completedAt ?? latest.startedAt)}</time></span>{items.map(item => <span className="mt-1 flex items-center justify-between gap-2 text-xs" key={item.nodeVisitId + '-' + item.attempt}><span>尝试 {item.attempt}</span><TableStatus tone={tone(item.status)}>{statuses[item.status] ?? item.status}</TableStatus></span>)}</button></li>
      })}</ol> : !loading && !error ? <p className="text-sm text-muted">{attempts ? '暂无节点尝试' : '尚未读取节点尝试'}</p> : null}
      {attempts && attempts.items.length < attempts.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreAttempts}>加载更多尝试</Button> : null}
    </aside>
    <section className="min-w-0 rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="m-0">{selectedName ? `${selectedName} · 历史日志` : '历史日志'}</h3><div className="flex flex-wrap gap-2"><form role="search" aria-label="日志全文搜索" className="flex min-w-0 gap-1" onSubmit={event => { event.preventDefault(); onQueryChange(searchDraft.trim()) }}><SearchInput className="w-56 max-w-full" aria-label="搜索日志内容" placeholder="搜索日志内容" maxLength={200} value={searchDraft} loading={loading} onChange={event => setSearchDraft(event.target.value)} onClear={() => { setSearchDraft(''); onQueryChange('') }} clearLabel="清除日志搜索"/><Button type="submit" variant="ghost" className="h-10 w-10 p-0" aria-label="应用日志搜索"><MagnifyingGlass size={18} aria-hidden/></Button></form><Select aria-label="筛选日志节点" className="w-40" clearable={false} value={selectedNode ?? ''} options={[{ value: '', label: '全部节点' }, ...nodeOptions]} onValueChange={value => onNodeChange(value || null)}/><Select aria-label="筛选日志级别" className="w-36" clearable={false} value={level ?? ''} options={[{ value: '', label: '全部级别' }, { value: 'debug', label: '调试' }, { value: 'info', label: '信息' }, { value: 'warning', label: '警告' }, { value: 'error', label: '错误' }]} onValueChange={value => onLevelChange(value || null)}/></div></div>
      {error ? <div role="alert" className="my-3 flex items-center justify-between gap-3 rounded-control bg-warning/10 p-3"><span className="min-w-0 break-words">{error}</span><Button onClick={onRetry}>重试</Button></div> : null}
      <TableScroll label="任务日志" className="mt-4 rounded-control border border-line"><Table><TableHeader><TableRow><TableHead>时间</TableHead><TableHead>级别</TableHead><TableHead>日志内容</TableHead></TableRow></TableHeader><TableBody>{logs?.items.map(item => <TableRow key={item.eventId}><TableCell><time dateTime={item.occurredAt}>{new Date(item.occurredAt).toLocaleTimeString('zh-CN', { hour12: false })}</time></TableCell><TableCell><TableStatus tone={item.level === 'error' ? 'danger' : item.level === 'warning' ? 'warning' : 'neutral'}>{item.level.toUpperCase()}</TableStatus></TableCell><TableCell className="max-w-xl whitespace-normal break-words">{item.message}</TableCell></TableRow>)}</TableBody></Table></TableScroll>
      {loading ? <p role="status">正在读取日志…</p> : null}
      {!loading && !error && !logs?.items.length ? <p className="text-sm text-muted">{logs ? '没有匹配的日志。' : '尚未读取日志。'}</p> : null}
      {logs?.hasMore ? <Button className="mt-3" disabled={loading} onClick={onLoadMore}>加载更多日志</Button> : null}
      <p className="text-xs text-muted">日志按持久序号连续读取。</p>
    </section>
  </div>
}
