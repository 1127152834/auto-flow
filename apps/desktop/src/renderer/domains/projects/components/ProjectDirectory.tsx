import { ArrowClockwise, ArrowLeft, CaretRight, Plus } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Pagination } from '../../../shared/components/ui/pagination'
import { ScrollArea } from '../../../shared/components/ui/scroll-area'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Select } from '../../../shared/components/ui/select'
import type { ProjectListConditions, ProjectPage, ProjectSummary } from '../types'
import { ProjectCard } from './ProjectCard'

export type ProjectDirectoryMode = 'recent' | 'all'

type Props = {
  mode?: ProjectDirectoryMode
  onModeChange?(mode: ProjectDirectoryMode): void
  recentItems?: ProjectSummary[]
  recentLoading?: boolean
  recentError?: string | null
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

export function ProjectDirectory({ mode = 'all', onModeChange, recentItems = [], recentLoading = false, recentError = null, page, conditions, loading, refreshing, disabled, error, onConditionsChange, onRefresh, onCreate, onOpen, onEdit, initialScrollTop = 0, onScrollTopChange }: Props) {
  const recent = recentItems.filter(project => project.lifecycleState === 'active' && project.lastOpenedAt != null).slice(0, 6)
  const items = mode === 'recent' ? recent : page?.items ?? []
  const currentLoading = mode === 'recent' ? recentLoading : loading
  const currentError = mode === 'recent' ? recentError : error
  const viewport = useRef<HTMLDivElement>(null)
  useEffect(() => { if (viewport.current) viewport.current.scrollTop = initialScrollTop }, [initialScrollTop, mode, page, recentItems])
  const update = (next: Partial<ProjectListConditions>) => onConditionsChange({ ...conditions, ...next })
  const search = (query: string) => { update({ query, page: 1 }); if (mode === 'recent') onModeChange?.('all') }

  return <section aria-label="项目目录" className="grid gap-8">
    <header>
      <h1 className="m-0 text-5xl font-semibold tracking-tight text-ink">项目</h1><p className="mb-0 mt-3 text-base text-muted">继续最近的工作，或创建一个新项目</p>
    </header>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2"><Button variant="primary" disabled={disabled} onClick={onCreate}><Plus aria-hidden="true" />新建项目</Button><Button variant="ghost" className="h-10 w-10 p-0" aria-label="刷新项目" title="刷新项目" disabled={refreshing} onClick={onRefresh}><ArrowClockwise aria-hidden="true" className={refreshing ? 'animate-spin' : ''} /></Button></div>
      <div className="ml-auto flex min-w-0 flex-1 flex-wrap justify-end gap-2">
        <div className="w-full min-w-56 sm:w-72"><SearchInput aria-label="搜索项目" placeholder="搜索名称或描述" value={mode === 'recent' ? '' : conditions.query} onChange={event => search(event.target.value)} onClear={() => search('')} /></div>
        {mode === 'all' ? <><Select aria-label="项目状态" clearable={false} value={conditions.lifecycle} options={lifecycleOptions} onValueChange={value => update({ lifecycle: value as ProjectListConditions['lifecycle'], page: 1 })} /><Select aria-label="项目排序" clearable={false} value={conditions.sort} options={sortOptions} onValueChange={value => update({ sort: value as ProjectListConditions['sort'], page: 1 })} /></> : null}
      </div>
    </div>
    {currentError ? <div role="alert" className="rounded-control border border-clay/30 bg-clay/10 px-4 py-3 text-sm">{currentError}{items.length ? '。当前仍显示上次成功载入的内容。' : '。'}</div> : null}
    <div className="flex flex-wrap items-center gap-3"><h2 className="m-0 text-xl font-semibold text-ink">{mode === 'recent' ? '最近项目' : '全部项目'}</h2><span className="text-sm text-muted">{mode === 'recent' ? `${items.length} 个项目` : page ? `${page.total} 个项目` : ''}</span>{mode === 'all' ? <Button className="ml-auto" variant="ghost" onClick={() => onModeChange?.('recent')}><ArrowLeft aria-hidden="true" />返回最近</Button> : null}</div>
    <ScrollArea ref={viewport} onScroll={event => onScrollTopChange?.(event.currentTarget.scrollTop)} className="max-h-[min(62vh,44rem)]" viewportClassName="max-h-[min(62vh,44rem)]">
      {items.length ? <div className="grid gap-5 lg:grid-cols-2">{items.map(project => <ProjectCard key={project.projectId} project={project} disabled={disabled} onOpen={onOpen} onEdit={onEdit} />)}</div> : null}
      {currentLoading ? <p role="status" className="m-0 rounded-card border border-line bg-surface px-6 py-14 text-center text-muted">正在加载项目…</p> : !items.length ? <div role="status" className="rounded-card border border-line bg-surface px-6 py-14 text-center text-muted"><p className="m-0">{mode === 'recent' ? '尚无最近访问，可从上方查看全部项目或新建项目。' : conditions.query.trim() || conditions.lifecycle !== 'active' ? '没有匹配的项目' : '还没有项目'}</p></div> : null}
    </ScrollArea>
    {mode === 'recent' ? <div><Button variant="ghost" className="px-0 text-ink" aria-label="查看全部项目" onClick={() => onModeChange?.('all')}>全部项目<CaretRight aria-hidden="true" /></Button></div> : null}
    {mode === 'all' && page && page.total > page.pageSize ? <Pagination offset={(page.page - 1) * page.pageSize} limit={page.pageSize} total={page.total} count={page.items.length} disabled={refreshing} onOffsetChange={offset => update({ page: Math.floor(offset / page.pageSize) + 1 })} /> : null}
  </section>
}
