import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { ArrowsDownUp, Columns, DownloadSimple, Funnel, Plus, Stack, X } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '../../../shared/components/ui/popover'
import { SearchInput } from '../../../shared/components/ui/search-input'
import { Select } from '../../../shared/components/ui/select'
import { parseRecordQuery, recordQueryDraft, RecordQueryError, type RecordQuery, type RecordQueryDraft } from '../record-query'
import { RecordFilterDraftEditor, RecordSortDraftEditor } from './RecordFilterEditor'

type Schema = components['schemas']
type Field = Schema['DataFieldView']
type Status = Schema['DataStatusView']
export type QuickSearch = { fieldId: string | null; keyword: string }
export type RecordQueryToolbarProps = {
  fields: Field[]; statuses: Status[]; query: RecordQuery; visibleFieldIds: string[] | null; quickSearch: QuickSearch
  disabled?: boolean; readonly?: boolean; exportDisabled?: boolean; queryError?: string; selectionCount: number; onClearSelection(): void; onCreate(): void; onBatchStatus(): void; onExport(): void
  onApplyQuery(query: RecordQuery): boolean | void; onApplyColumns(ids: string[]): void; onApplySearch(search: QuickSearch): boolean | void; resetKey: string
}
type QueryPanel = 'filter' | 'sort' | 'columns' | null
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function composeRecordQuery(fields: Field[], advanced: RecordQuery, search: QuickSearch): RecordQuery {
  const keyword = search.keyword.trim()
  const searchFilter = {type:'compare' as const,fieldId:search.fieldId ?? '',operator:'contains',value:keyword}
  const filter = keyword ? { type:'all' as const, items:advanced.filter.type==='all'?[...advanced.filter.items,searchFilter]:[advanced.filter,searchFilter] } : advanced.filter
  const statusIds = new Set<string>()
  const collectStatuses = (node: RecordQuery['filter']) => { if(node.type==='status'&&node.statusId)statusIds.add(node.statusId);else if(node.type==='not')collectStatuses(node.item);else if(node.type==='all'||node.type==='any')node.items.forEach(collectStatuses) }
  collectStatuses(advanced.filter)
  return parseRecordQuery(recordQueryDraft({ filter, orderBy: advanced.orderBy }), fields, [...statusIds].map(statusId=>({statusId})))
}

const panelWidth = { filter: 'w-[min(32rem,calc(100vw-2rem))]', sort: 'w-[min(25rem,calc(100vw-2rem))]', columns: 'w-[min(18rem,calc(100vw-2rem))]' }
function Panel({ open, onOpenChange, kind, trigger, label, icon, applied, disabled, footer, children }: { open: boolean; onOpenChange(open:boolean):void; kind:Exclude<QueryPanel,null>; trigger:string; label:string; icon:ReactNode; applied:boolean; disabled?:boolean; footer:ReactNode; children:ReactNode }) {
  return <Popover open={open} onOpenChange={onOpenChange}><PopoverTrigger asChild><Button type="button" variant="secondary" aria-label={trigger} disabled={disabled} data-query-applied={applied} data-query-panel-trigger data-record-action={kind}>{icon}{trigger}{applied ? <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-clay" /> : null}</Button></PopoverTrigger><PopoverContent aria-label={label} data-query-panel-size={kind} className={`${panelWidth[kind]} overflow-hidden p-0`} onInteractOutside={event=>{if((event.target as Element).closest('[data-query-panel-trigger]'))event.preventDefault()}}><div className="flex max-h-[var(--radix-popover-content-available-height)] flex-col"><header className="flex shrink-0 items-center justify-between border-b border-line px-4 py-3"><h2 className="m-0 text-base font-semibold">{label}</h2><Button type="button" variant="ghost" className="h-8 w-8 p-0" aria-label={`关闭${label}`} onClick={()=>onOpenChange(false)}><X /></Button></header><div data-query-panel-body className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div><footer data-query-panel-footer className="flex shrink-0 justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer></div></PopoverContent></Popover>
}

export function RecordQueryToolbar({ fields, statuses, query, visibleFieldIds, quickSearch, disabled=false, readonly=false, exportDisabled=false, queryError, selectionCount, onClearSelection, onCreate, onBatchStatus, onExport, onApplyQuery, onApplyColumns, onApplySearch, resetKey }: RecordQueryToolbarProps) {
  const textFields=fields.filter(field=>field.type==='string')
  const normalizedSearch=(value:QuickSearch):QuickSearch=>({fieldId:textFields.some(field=>field.ref.fieldId===value.fieldId)?value.fieldId:textFields[0]?.ref.fieldId??null,keyword:value.keyword})
  const [panel,setPanel]=useState<QueryPanel>(null),[draft,setDraft]=useState<RecordQueryDraft>(()=>recordQueryDraft(query)),[columns,setColumns]=useState<string[]>(visibleFieldIds??fields.map(field=>field.ref.fieldId)),[search,setSearch]=useState<QuickSearch>(()=>normalizedSearch(quickSearch)),[error,setError]=useState<RecordQueryError|null>(null),[submitError,setSubmitError]=useState(false)
  const errorRef=useRef<HTMLParagraphElement>(null)
  const appliedSearchRef=useRef(normalizedSearch(quickSearch))
  const close=()=>{setPanel(null);setError(null);setSubmitError(false)}
  const open=(next:Exclude<QueryPanel,null>)=>{setDraft(recordQueryDraft(query));setColumns(visibleFieldIds??fields.map(field=>field.ref.fieldId));setError(null);setSubmitError(false);setPanel(next)}
  useEffect(()=>{const next=normalizedSearch(quickSearch);setSearch(current=>same(current,appliedSearchRef.current)?next:current);appliedSearchRef.current=next},[quickSearch,fields])
  useEffect(()=>{const next=normalizedSearch(quickSearch);close();setDraft(recordQueryDraft(query));setColumns(visibleFieldIds??fields.map(field=>field.ref.fieldId));setSearch(next);appliedSearchRef.current=next},[resetKey])
  useEffect(()=>{if(submitError||queryError)errorRef.current?.focus();else if(error){const target=document.querySelector<HTMLElement>('[data-af-popup] [role="alert"]');target?.setAttribute('tabindex','-1');target?.focus()}},[submitError,queryError,error])
  const applyQuery=(kind:'filter'|'sort')=>{try{const parsed=parseRecordQuery(draft,fields,statuses);const next=kind==='filter'?{filter:parsed.filter,orderBy:query.orderBy}:{filter:query.filter,orderBy:parsed.orderBy};setError(null);if(same(next,query)){close();return}if(onApplyQuery(next)===false){setSubmitError(true);return}close()}catch(caught){setError(caught instanceof RecordQueryError?caught:new RecordQueryError(kind,'查询条件无效'))}}
  const applySearch=(next:QuickSearch)=>{if(onApplySearch(next)===false){setSubmitError(true);return false}setSubmitError(false);setSearch(next);appliedSearchRef.current=next;return true}
  const submitSearch=(event:FormEvent)=>{event.preventDefault();const next={fieldId:search.fieldId,keyword:search.keyword.trim()};if(same(next,quickSearch)){setSubmitError(false);setSearch(next);appliedSearchRef.current=next;return}applySearch(next)}
  const enabled=!disabled, canSearch=textFields.length>0
  const visibleSet=new Set(visibleFieldIds), allColumnsVisible=visibleFieldIds!==null&&visibleSet.size===fields.length&&fields.every(field=>visibleSet.has(field.ref.fieldId))
  const appliedFilter=query.filter.type!=='all'||query.filter.items.length>0, appliedSort=query.orderBy.length>0, appliedColumns=visibleFieldIds!==null&&!allColumnsVisible
  const showQueryError=submitError||Boolean(queryError), queryErrorMessage=queryError??'应用失败，请检查后重试。'
  return <section aria-label="记录查询工具" className="grid min-w-0 gap-3">
    <div role="toolbar" aria-label="记录工具" className="flex min-w-0 flex-wrap items-center gap-2">
      <form role="search" className="flex w-full min-w-0 flex-wrap gap-2 xl:w-auto xl:flex-1" onSubmit={submitSearch}><Select className="w-40 max-w-full" aria-label="搜索字段" value={search.fieldId} disabled={!enabled||!canSearch} clearable={false} options={textFields.map(field=>({value:field.ref.fieldId,label:field.name}))} onValueChange={fieldId=>{setSubmitError(false);setSearch(value=>({...value,fieldId}))}}/><SearchInput className="min-w-36 flex-1" aria-label="文本搜索" disabled={!enabled||!canSearch} value={search.keyword} clearLabel="清除文本搜索" onChange={event=>{setSubmitError(false);setSearch(value=>({...value,keyword:event.target.value}))}} onClear={()=>{const next={fieldId:search.fieldId,keyword:''};if(same(next,quickSearch)){setSubmitError(false);setSearch(next);appliedSearchRef.current=next}else applySearch(next)}}/><Button type="submit" disabled={!enabled||!canSearch}>搜索记录</Button></form>
      <Panel kind="filter" applied={appliedFilter} open={panel==='filter'} onOpenChange={value=>value?open('filter'):setPanel(current=>current==='filter'?null:current)} trigger="筛选" label="记录筛选" icon={<Funnel />} disabled={!enabled} footer={<><Button variant="ghost" onClick={close}>取消</Button><Button variant="primary" disabled={!enabled} onClick={()=>applyQuery('filter')}>应用筛选</Button></>}><div className="grid gap-4"><RecordFilterDraftEditor fields={fields} statuses={statuses} filter={draft.filter} disabled={!enabled} error={error} onChange={filter=>{setDraft(value=>({...value,filter}));setError(null)}}/>{showQueryError?<p ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-danger">{queryErrorMessage}</p>:null}</div></Panel>
      <Panel kind="sort" applied={appliedSort} open={panel==='sort'} onOpenChange={value=>value?open('sort'):setPanel(current=>current==='sort'?null:current)} trigger="排序" label="记录排序" icon={<ArrowsDownUp />} disabled={!enabled} footer={<><Button variant="ghost" onClick={close}>取消</Button><Button variant="primary" disabled={!enabled} onClick={()=>applyQuery('sort')}>应用排序</Button></>}><div className="grid gap-4"><RecordSortDraftEditor fields={fields} orderBy={draft.orderBy} disabled={!enabled} error={error} onChange={orderBy=>{setDraft(value=>({...value,orderBy}));setError(null)}}/>{showQueryError?<p ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-danger">{queryErrorMessage}</p>:null}</div></Panel>
      <Panel kind="columns" applied={appliedColumns} open={panel==='columns'} onOpenChange={value=>value?open('columns'):setPanel(current=>current==='columns'?null:current)} trigger="显示列" label="显示列" icon={<Columns />} disabled={!enabled} footer={<><Button variant="ghost" onClick={close}>取消</Button><Button variant="primary" disabled={!enabled} onClick={()=>{const applied=visibleFieldIds??fields.map(field=>field.ref.fieldId);if(!same(columns,applied))onApplyColumns(columns);close()}}>应用显示列</Button></>}><div className="grid gap-3">{fields.map(field=><label key={field.ref.fieldId} className="flex items-center gap-2 text-sm"><Checkbox aria-label={field.name} checked={columns.includes(field.ref.fieldId)} disabled={!enabled} onCheckedChange={checked=>setColumns(value=>checked===true?[...value,field.ref.fieldId]:value.filter(id=>id!==field.ref.fieldId))}/><span>{field.name}</span></label>)}</div></Panel>
      <Button variant="secondary" data-record-action="batch-status" disabled={!enabled||readonly||selectionCount===0} onClick={onBatchStatus}><Stack />批量设置状态</Button><Button variant="secondary" data-record-action="export" disabled={!enabled||exportDisabled} onClick={onExport}><DownloadSimple />导出 Excel</Button>{!readonly?<Button variant="primary" data-record-action="create" disabled={!enabled} onClick={onCreate}><Plus />新增记录</Button>:null}
    </div>
    {!canSearch?<p className="text-xs text-muted">没有可搜索的文本字段</p>:null}
    {selectionCount>0?<div className="flex items-center gap-2 text-sm"><span>已选择 {selectionCount} 条</span><Button size="sm" variant="ghost" disabled={!enabled} onClick={onClearSelection}>清空选择</Button></div>:null}
    {showQueryError&&panel===null?<p ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-danger">{queryErrorMessage}</p>:null}
  </section>
}
