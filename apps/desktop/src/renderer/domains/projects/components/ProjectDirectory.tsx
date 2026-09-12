import { ArrowClockwise, PencilSimple, Plus } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Pagination } from '../../../shared/components/ui/pagination'
import { ScrollArea } from '../../../shared/components/ui/scroll-area'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Select } from '../../../shared/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../shared/components/ui/table'
import type { ProjectListConditions, ProjectPage, ProjectSummary } from '../types'

type Props = {
  page?: ProjectPage
  conditions: ProjectListConditions
  loading: boolean
  refreshing: boolean
  disabled: boolean
  error: string | null
  onConditionsChange(value: ProjectListConditions): void
  onRefresh(): void
  onCreate(): void
  onOpen(project: ProjectSummary): void
  onEdit(project: ProjectSummary): void
  initialScrollTop?: number
  onScrollTopChange?(value: number): void
}

const lifecycleOptions = [{ value: 'active', label: '活动项目' }, { value: 'archived', label: '已归档' }, { value: 'all', label: '全部状态' }]
const sortOptions = [{ value: '-lastOpenedAt', label: '最近打开' }, { value: 'lastOpenedAt', label: '最早打开' }, { value: '-updatedAt', label: '最近更新' }, { value: 'updatedAt', label: '最早更新' }, { value: 'name', label: '名称 A–Z' }, { value: '-name', label: '名称 Z–A' }]

function date(value: string | null | undefined) {
  if (!value) return '从未打开'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
const lifecycleLabel: Record<string, string> = { active: '活动', closing: '正在归档', archived: '已归档', deleting: '正在删除', deleted: '已删除' }

export function ProjectDirectory({ page, conditions, loading, refreshing, disabled, error, onConditionsChange, onRefresh, onCreate, onOpen, onEdit, initialScrollTop = 0, onScrollTopChange }: Props) {
  const items = page?.items ?? []
  const viewport = useRef<HTMLDivElement>(null)
  useEffect(() => { if (page && viewport.current) viewport.current.scrollTop = initialScrollTop }, [initialScrollTop, page])
  const update = (next: Partial<ProjectListConditions>) => onConditionsChange({ ...conditions, ...next })
  return <section aria-label="项目目录" className="grid gap-4">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="m-0 text-2xl font-semibold text-ink">项目</h1><p className="mb-0 mt-1 text-sm text-muted">创建并打开本地自动化工作空间。</p></div>
      <div className="flex gap-2"><Button type="button" variant="ghost" disabled={refreshing} onClick={onRefresh}><ArrowClockwise className={refreshing ? 'animate-spin' : ''} />刷新</Button><Button type="button" variant="primary" disabled={disabled} onClick={onCreate}><Plus />新建项目</Button></div>
    </header>
    <div className="flex flex-wrap gap-3 rounded-card border border-line bg-surface p-3">
      <SearchInput className="min-w-56 flex-1" aria-label="搜索项目" placeholder="搜索名称或描述" value={conditions.query} onChange={event => update({ query: event.target.value, page: 1 })} onClear={() => update({ query: '', page: 1 })} />
      <Select aria-label="项目状态" clearable={false} value={conditions.lifecycle} options={lifecycleOptions} onValueChange={value => update({ lifecycle: value as ProjectListConditions['lifecycle'], page: 1 })} />
      <Select aria-label="项目排序" clearable={false} value={conditions.sort} options={sortOptions} onValueChange={value => update({ sort: value as ProjectListConditions['sort'], page: 1 })} />
    </div>
    {error ? <div role="alert" className="rounded-control border border-clay/30 bg-clay/10 px-4 py-3 text-sm">{error}。当前仍显示上次成功载入的内容。</div> : null}
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <ScrollArea ref={viewport} onScroll={event => onScrollTopChange?.(event.currentTarget.scrollTop)} className="max-h-[min(62vh,44rem)]" viewportClassName="max-h-[min(62vh,44rem)]"><Table><TableHeader><TableRow><TableHead>名称</TableHead><TableHead>描述</TableHead><TableHead>状态</TableHead><TableHead>最近更新</TableHead><TableHead>最近打开</TableHead><TableHead><span className="sr-only">操作</span></TableHead></TableRow></TableHeader>
        <TableBody>{items.map(project => { const canOpen = !disabled && project.lifecycleState !== 'deleting' && project.lifecycleState !== 'deleted'; return <TableRow key={project.projectId} tabIndex={canOpen ? 0 : -1} aria-disabled={!canOpen || undefined} className={canOpen ? 'cursor-pointer focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-clay' : 'opacity-60'} onClick={() => { if (canOpen) onOpen(project) }} onKeyDown={event => { if (canOpen && event.target === event.currentTarget && event.key === 'Enter') { event.preventDefault(); onOpen(project) } }}>
          <TableCell className="font-medium">{project.name}</TableCell><TableCell className="max-w-sm truncate text-muted">{project.description || '—'}</TableCell><TableCell className="text-muted">{lifecycleLabel[project.lifecycleState] ?? project.lifecycleState}</TableCell><TableCell className="text-muted">{date(project.updatedAt)}</TableCell><TableCell className="text-muted">{date(project.lastOpenedAt)}</TableCell><TableCell><Button type="button" variant="ghost" className="h-8 px-3" aria-label={`编辑${project.name}`} disabled={disabled || project.lifecycleState !== 'active'} onClick={event => { event.stopPropagation(); onEdit(project) }}><PencilSimple />编辑</Button></TableCell>
        </TableRow> })}</TableBody></Table></ScrollArea>
      {loading ? <p role="status" className="m-0 px-6 py-14 text-center text-muted">正在加载项目…</p> : !items.length ? <p role="status" className="m-0 px-6 py-14 text-center text-muted">{conditions.query.trim() || conditions.lifecycle !== 'active' ? '没有匹配的项目' : '还没有项目'}</p> : null}
    </div>
    {page && page.total > page.pageSize ? <Pagination offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={refreshing} onOffsetChange={offset => update({ page: Math.floor(offset / page.pageSize) + 1 })} /> : null}
  </section>
}
