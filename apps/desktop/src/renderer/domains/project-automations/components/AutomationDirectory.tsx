import { ArrowRight, Clock, Database, DotsThree, FileText, FlowArrow, MagnifyingGlass, Plus, Trash } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { Pagination } from '../../../shared/components/ui/pagination'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Select } from '../../../shared/components/ui/select'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { TableStatus } from '../../../shared/components/ui/table-status'
import type { Automation, AutomationDirectoryQuery, AutomationValidation } from '../types'

export type AutomationDirectoryProps = {
  items: Automation[]
  total: number
  page: number
  pageSize: number
  query: string
  sort: AutomationDirectoryQuery['sort']
  loading?: boolean
  errorMessage?: string
  refreshing?: boolean
  readOnly?: boolean
  validationById?: Record<string, AutomationValidation | undefined>
  onQueryChange(value: string): void
  onSortChange(value: AutomationDirectoryQuery['sort']): void
  onPageChange(page: number): void
  onCreate(): void
  onOpen(automation: Automation): void
  onEdit(automation: Automation): void
  /** Deletion carries its own impact confirmation, so it is optional for read-only hosts. */
  onDelete?(automation: Automation): void
  onRetry(): void
}

const sortOptions = [
  { value: '-updatedAt', label: '最近修改' },
  { value: 'updatedAt', label: '最早修改' },
  { value: 'name', label: '名称升序' },
  { value: '-name', label: '名称降序' },
]

const formatUpdatedAt = (value: string) => new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))

function ValidationStatus({ validation }: { validation?: AutomationValidation }) {
  if (!validation) return null
  if (validation.runnable && validation.status === 'ready') return <TableStatus tone="success">可以运行</TableStatus>
  if (validation.status === 'unavailable') return <TableStatus tone="neutral">运行状态不可用</TableStatus>
  return <TableStatus tone="warning">运行受阻</TableStatus>
}

function AutomationCard({ automation, validation, readOnly, refreshing, onOpen, onEdit, onDelete }: {
  automation: Automation
  validation?: AutomationValidation
  readOnly: boolean
  refreshing: boolean
  onOpen(automation: Automation): void
  onEdit(automation: Automation): void
  onDelete?(automation: Automation): void
}) {
  const inputs = automation.inputPlan.inputs.length
  return <article className="grid min-w-0 gap-5 rounded-control border border-line bg-surface p-5 shadow-sm">
    <div className="flex min-w-0 items-start gap-4">
      <span data-testid="automation-document-icon" className="flex h-14 w-14 shrink-0 items-center justify-center rounded-control border border-clay/15 bg-clay-soft text-clay"><FileText size={28} aria-hidden /></span>
      <div className="min-w-0 flex-1"><h3 className="m-0 [overflow-wrap:anywhere] text-lg font-semibold">{automation.name}</h3><p className="mt-1 line-clamp-2 [overflow-wrap:anywhere] text-sm text-muted">{automation.description || '尚未填写用途说明'}</p></div>
      {!readOnly ? <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" className="h-8 w-8 p-0" aria-label={`更多${automation.name}操作`} disabled={refreshing}><DotsThree size={21} aria-hidden /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => onEdit(automation)}>编辑基本信息</DropdownMenuItem>{onDelete ? <DropdownMenuItem onSelect={() => onDelete(automation)}><Trash aria-hidden="true" className="mr-2" />删除自动化</DropdownMenuItem> : null}</DropdownMenuContent></DropdownMenu> : null}
    </div>
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-4 text-sm text-muted">
      <TableStatus tone="success">配置已保存</TableStatus>
      <ValidationStatus validation={validation} />
      <span className="flex items-center gap-2"><Database size={18} aria-hidden />{inputs ? `${inputs} 项数据输入` : '无数据输入'}</span>
      <time className="flex items-center gap-2" dateTime={automation.updatedAt}><Clock size={18} aria-hidden />{formatUpdatedAt(automation.updatedAt)}</time>
      <Button variant="ghost" className="ml-auto text-clay" aria-label={`${readOnly ? '查看' : '打开'}自动化 ${automation.name}`} onClick={() => onOpen(automation)}>{readOnly ? '查看' : '打开'}<ArrowRight size={18} aria-hidden /></Button>
    </div>
  </article>
}

function LoadingCards() {
  return <div role="status" aria-label="正在加载自动化" className="grid grid-cols-1 gap-3 lg:grid-cols-2"><span className="sr-only">正在加载自动化…</span>{Array.from({ length: 6 }, (_, index) => <div data-testid="automation-skeleton" key={index} className="rounded-control border border-line bg-surface p-5"><div className="flex gap-4"><Skeleton className="h-14 w-14"/><div className="flex-1"><Skeleton className="h-5 w-1/2"/><Skeleton className="mt-3 h-4 w-3/4"/></div></div><Skeleton className="mt-8 h-10 w-full"/></div>)}</div>
}

function CenterState({ icon, title, detail, action }: { icon: React.ReactNode; title: string; detail: string; action: React.ReactNode }) {
  return <div className="grid min-h-96 place-items-center py-12 text-center"><div className="grid justify-items-center gap-3"><span className="flex h-24 w-24 items-center justify-center rounded-full bg-clay-soft text-muted">{icon}</span><h3 className="m-0 text-2xl font-semibold">{title}</h3><p className="m-0 text-muted">{detail}</p>{action}</div></div>
}

export function AutomationDirectory({ items, total, page, pageSize, query, sort, loading = false, errorMessage, refreshing = false, readOnly = false, validationById = {}, onQueryChange, onSortChange, onPageChange, onCreate, onOpen, onEdit, onDelete, onRetry }: AutomationDirectoryProps) {
  const [searchDraft, setSearchDraft] = useState(query)
  useEffect(() => { setSearchDraft(query) }, [query])
  const clearSearch = () => { setSearchDraft(''); onQueryChange('') }
  const initialLoading = loading && items.length === 0
  const initialError = Boolean(errorMessage && items.length === 0)
  return <section className="grid min-w-0 gap-4">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <h2 className="m-0 text-xl font-semibold" aria-label={`自动化 ${initialError ? '总数未知' : `${total} 个`}`}>自动化 <span className="ml-2 text-base font-normal text-muted">{initialLoading ? '正在加载…' : initialError ? '总数未知' : `${total} 个`}</span></h2>
      {total > 0 || query || initialLoading || initialError ? <div className="flex min-w-0 flex-1 flex-wrap justify-end gap-3">
        <form role="search" aria-label="自动化目录搜索" className="flex min-w-0 gap-1" onSubmit={event => { event.preventDefault(); onQueryChange(searchDraft) }}>
          <SearchInput className="w-64 max-w-full" aria-label="搜索自动化" placeholder="搜索名称或用途" value={searchDraft} loading={refreshing} onChange={event => setSearchDraft(event.target.value)} onClear={clearSearch} />
          <Button type="submit" variant="ghost" className="h-10 w-10 p-0" aria-label="应用自动化搜索"><MagnifyingGlass size={18} aria-hidden /></Button>
        </form>
        <Select className="w-40 max-w-full" aria-label="自动化排序" value={sort} options={sortOptions} clearable={false} disabled={refreshing} onValueChange={value => value && onSortChange(value as AutomationDirectoryQuery['sort'])}/>
        {!readOnly ? <Button variant="primary" disabled={refreshing} onClick={onCreate}><Plus aria-hidden />新建自动化</Button> : null}
      </div> : null}
    </div>
    {errorMessage && items.length ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-warning/30 bg-warning/10 p-3 text-sm"><span>自动化列表刷新失败：{errorMessage}。当前显示上次读取的结果。</span><Button size="sm" onClick={onRetry}>重试读取</Button></div> : null}
    {initialLoading ? <LoadingCards /> : initialError ? <div role="alert"><CenterState icon={<FileText size={52}/>} title="自动化暂时无法加载" detail="搜索条件已保留，请重新读取" action={<Button variant="primary" onClick={onRetry}>重新加载</Button>}/></div>
      : items.length ? <div data-testid="automation-grid" className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-2">{items.map(automation => <AutomationCard key={automation.automationId} automation={automation} validation={validationById[automation.automationId]} readOnly={readOnly} refreshing={refreshing} onOpen={onOpen} onEdit={onEdit} onDelete={onDelete}/>)}</div>
      : query ? <CenterState icon={<FileText size={52}/>} title="没有找到匹配的自动化" detail={`未找到与「${query}」匹配的名称或用途。`} action={<Button variant="primary" onClick={clearSearch}>清除搜索条件</Button>}/>
      : <CenterState icon={<FlowArrow size={52}/>} title="还没有自动化" detail="创建一个自动化，整理你的工作流程" action={!readOnly ? <Button variant="primary" onClick={onCreate}>新建自动化</Button> : null}/>}
    {!initialLoading && !initialError ? <><Pagination offset={(page - 1) * pageSize} limit={pageSize} total={total} count={items.length} disabled={refreshing} showPage onOffsetChange={offset => onPageChange(Math.floor(offset / pageSize) + 1)}/><p className="m-0 flex items-center gap-2 text-xs text-muted"><Database size={15} aria-hidden />配置状态不代表执行状态</p></> : null}
  </section>
}
