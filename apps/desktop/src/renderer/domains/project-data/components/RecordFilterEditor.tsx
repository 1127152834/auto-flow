import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { emptyRecordQuery, operatorsFor, parseRecordQuery, recordQueryDraft, RecordQueryError, type FieldType, type FilterDraft, type OrderBy, type RecordQuery, type RecordQueryDraft } from '../record-query'
import { scalarDraft } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

type Schema = components['schemas']
type Field = Schema['DataFieldView']
type Status = Schema['DataStatusView']
export type RecordFilterEditorProps = { fields: Field[]; statuses: Status[]; appliedQuery?: RecordQuery; disabled?: boolean; onApply(query: RecordQuery): void; onDirtyChange?(dirty: boolean): void }

const operatorLabels: Record<string, string> = { eq: '等于', neq: '不等于', contains: '包含', startsWith: '开头是', gt: '大于', gte: '大于等于', lt: '小于', lte: '小于等于', isNull: '为空', isNotNull: '不为空' }
const defaultQuery = emptyRecordQuery()
const initialValue = (type: FieldType) => scalarDraft(type === 'boolean' ? false : type === 'number' ? 0 : type === 'string' ? '' : undefined)
const compare = (field?: Field): FilterDraft => ({ type: 'compare', fieldId: field?.ref.fieldId ?? '', operator: 'eq', value: initialValue(field?.type ?? 'string') })
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right)
const nodeDepth = (node: FilterDraft): number => node.type === 'not' ? 1 + nodeDepth(node.item) : node.type === 'all' || node.type === 'any' ? 1 + Math.max(0, ...node.items.map(nodeDepth)) : 1

function FilterNode({ node, fields, statuses, disabled, depth, path, error, onChange, onRemove }: { node: FilterDraft; fields: Field[]; statuses: Status[]; disabled: boolean; depth: number; path: string; error: RecordQueryError | null; onChange(node: FilterDraft): void; onRemove?(): void }) {
  const remove = onRemove ? <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={onRemove}>删除条件</Button> : null
  const wrap = <Button type="button" size="sm" variant="ghost" disabled={disabled || depth + nodeDepth(node) > 5} onClick={() => onChange({type:'not',item:node})}>反向此条件</Button>
  if (node.type === 'all' || node.type === 'any') return <fieldset className="grid min-w-0 gap-3 rounded-control border border-line p-3">
    <legend className="px-1 text-sm font-medium">条件组</legend>
    <div className="flex flex-wrap gap-2"><Select aria-label={`${path}匹配方式`} value={node.type} clearable={false} disabled={disabled} options={[{value:'all',label:'满足全部'},{value:'any',label:'满足任一'}]} onValueChange={value => value && onChange({ ...node, type: value as 'all'|'any' })} />{wrap}{remove}</div>
    {node.items.map((item, index) => <FilterNode key={index} node={item} fields={fields} statuses={statuses} disabled={disabled} depth={depth + 1} path={`${path}.items.${index}`} error={error} onChange={next => onChange({ ...node, items: node.items.map((value, itemIndex) => itemIndex === index ? next : value) })} onRemove={() => onChange({ ...node, items: node.items.filter((_, itemIndex) => itemIndex !== index) })} />)}
    {node.type === 'any' && node.items.length === 0 ? <p className="text-xs text-muted">“满足任一”至少需要一个条件。</p> : null}
    {error?.path === path ? <p role="alert" className="text-xs text-danger">{error.message}</p> : null}
    <div className="flex flex-wrap gap-2"><Button type="button" size="sm" disabled={disabled || node.items.length >= 50} onClick={() => onChange({ ...node, items: [...node.items, compare(fields[0])] })}>添加字段条件</Button><Button type="button" size="sm" disabled={disabled || node.items.length >= 50} onClick={() => onChange({ ...node, items: [...node.items, {type:'status',operator:'eq',statusId:statuses[0]?.statusId ?? ''}] })}>添加状态条件</Button><Button type="button" size="sm" disabled={disabled || depth >= 5 || node.items.length >= 50} onClick={() => onChange({ ...node, items: [...node.items, {type:'all',items:[]}] })}>添加条件组</Button><Button type="button" size="sm" disabled={disabled || depth >= 4 || node.items.length >= 50} onClick={() => onChange({ ...node, items: [...node.items, {type:'not',item:compare(fields[0])}] })}>添加反向条件</Button></div>
  </fieldset>
  if (node.type === 'not') return <fieldset className="grid gap-2 rounded-control border border-line p-3"><legend className="px-1 text-sm font-medium">不满足以下条件</legend><FilterNode node={node.item} fields={fields} statuses={statuses} disabled={disabled} depth={depth + 1} path={`${path}.item`} error={error} onChange={item => onChange({type:'not',item})} />{wrap}{remove}{error?.path===path?<p role="alert" className="text-xs text-danger">{error.message}</p>:null}</fieldset>
  if (node.type === 'status') return <fieldset className="grid gap-2 rounded-control border border-line p-3"><legend className="px-1 text-sm font-medium">状态条件</legend><Select aria-label={`${path}状态运算符`} value={node.operator} clearable={false} disabled={disabled} options={['eq','neq','isNull','isNotNull'].map(value=>({value,label:operatorLabels[value]}))} onValueChange={value=>value&&onChange({...node,operator:value,statusId:value==='isNull'||value==='isNotNull'?'':node.statusId})}/>{node.operator === 'isNull' || node.operator === 'isNotNull' ? null : <Select aria-label={`${path}状态`} value={node.statusId || null} disabled={disabled} options={statuses.map(value=>({value:value.statusId,label:value.name}))} onValueChange={value=>onChange({...node,statusId:value??''})}/>} {wrap}{remove}{error?.path===path?<p role="alert" className="text-xs text-danger">{error.message}</p>:null}</fieldset>
  const field = fields.find(value => value.ref.fieldId === node.fieldId)
  const type = field?.type ?? 'string'
  const isNull = node.operator === 'isNull' || node.operator === 'isNotNull'
  return <fieldset className="grid min-w-0 gap-2 rounded-control border border-line p-3"><legend className="px-1 text-sm font-medium">字段条件</legend><Select aria-label={`${path}字段`} value={node.fieldId || null} disabled={disabled} options={fields.map(value=>({value:value.ref.fieldId,label:value.name}))} onValueChange={value=>{const next=fields.find(item=>item.ref.fieldId===value);onChange(compare(next))}}/><Select aria-label={`${path}运算符`} value={node.operator} clearable={false} disabled={disabled} options={operatorsFor(type).map(value=>({value,label:operatorLabels[value]}))} onValueChange={value=>value&&onChange({...node,operator:value,value:value==='isNull'||value==='isNotNull'?scalarDraft(undefined):node.value})}/>{isNull?null:<ScalarValueEditor id={`${path}-value`} label="比较值" type={type} draft={node.value} onChange={value=>onChange({...node,value})} disabled={disabled} error={error?.path===path?error.message:undefined} errorTarget={error?.path===path?error.control:undefined}/>} {wrap}{remove}{error?.path===path&&!error.control?<p role="alert" className="text-xs text-danger">{error.message}</p>:null}</fieldset>
}

export function RecordFilterDraftEditor({ fields, statuses, filter, disabled = false, error = null, onChange }: { fields: Field[]; statuses: Status[]; filter: FilterDraft; disabled?: boolean; error?: RecordQueryError | null; onChange(filter: FilterDraft): void }) {
  return <FilterNode node={filter} fields={fields} statuses={statuses} disabled={disabled} depth={1} path="filter" error={error} onChange={onChange}/>
}

export function RecordSortDraftEditor({ fields, orderBy, disabled = false, error = null, onChange }: { fields: Field[]; orderBy: OrderBy[]; disabled?: boolean; error?: RecordQueryError | null; onChange(orderBy: OrderBy[]): void }) {
  const sortOptions=[...fields.map(field=>({value:`field:${field.ref.fieldId}`,label:field.name})),{value:'system:status',label:'状态'},{value:'system:createdAt',label:'创建时间'},{value:'system:updatedAt',label:'更新时间'},{value:'system:recordKey',label:'记录键'}]
  const setOrder=(index:number,target:string|null,direction?:'asc'|'desc')=>{const orders=[...orderBy];if(target){const current=orders[index];const dir=direction??current?.direction??'asc';orders[index]=target.startsWith('field:')?{fieldId:target.slice(6),direction:dir}:{systemField:target.slice(7) as Extract<OrderBy,{systemField:string}>['systemField'],direction:dir}}onChange(orders)}
  return <fieldset className="grid gap-3"><legend className="text-sm font-medium">排序</legend>{orderBy.map((order,index)=>{const target='fieldId'in order?`field:${order.fieldId}`:`system:${order.systemField}`;return <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_auto]" key={index}><Select aria-label={`排序字段 ${index+1}`} value={target} clearable={false} disabled={disabled} options={sortOptions} onValueChange={value=>setOrder(index,value)}/><Select aria-label={`排序方向 ${index+1}`} value={order.direction} clearable={false} disabled={disabled} options={[{value:'asc',label:'升序'},{value:'desc',label:'降序'}]} onValueChange={value=>value&&setOrder(index,target,value as 'asc'|'desc')}/><Button type="button" variant="ghost" disabled={disabled} onClick={()=>onChange(orderBy.filter((_,i)=>i!==index))}>删除排序</Button></div>})}<Button type="button" size="sm" disabled={disabled||orderBy.length>=8} onClick={()=>{const used=new Set(orderBy.map(value=>'fieldId'in value?`field:${value.fieldId}`:`system:${value.systemField}`));const option=sortOptions.find(value=>!used.has(value.value));if(option)setOrder(orderBy.length,option.value)}}>添加排序</Button>{error?.path.startsWith('orderBy')?<p role="alert" className="text-xs text-danger">{error.message}</p>:null}</fieldset>
}

export function RecordFilterEditor({ fields, statuses, appliedQuery = defaultQuery, disabled = false, onApply, onDirtyChange }: RecordFilterEditorProps) {
  const appliedDraft = useMemo(() => recordQueryDraft(appliedQuery), [appliedQuery])
  const [baseline, setBaseline] = useState(appliedDraft), [draft, setDraft] = useState<RecordQueryDraft>(appliedDraft), [error, setError] = useState<RecordQueryError | null>(null)
  const dirty = !same(draft, baseline), dirtyCallback = useRef(onDirtyChange)
  useLayoutEffect(() => { dirtyCallback.current = onDirtyChange }, [onDirtyChange])
  useLayoutEffect(() => { setDraft(current => same(current, baseline) ? appliedDraft : current); setBaseline(appliedDraft) }, [appliedDraft])
  useEffect(() => { onDirtyChange?.(dirty) }, [dirty, onDirtyChange])
  useEffect(() => () => dirtyCallback.current?.(false), [])
  const update = (next: RecordQueryDraft) => { setDraft(next); setError(null) }
  const apply = () => { try { const query=parseRecordQuery(draft,fields,statuses);setError(null);onApply(query) } catch (caught) { setError(caught instanceof RecordQueryError?caught:new RecordQueryError('filter','筛选条件无效')) } }
  return <section aria-label="记录筛选和排序" className="grid min-w-0 gap-4 rounded-card border border-line bg-surface p-4"><RecordFilterDraftEditor fields={fields} statuses={statuses} filter={draft.filter} disabled={disabled} error={error} onChange={filter=>update({...draft,filter})}/><RecordSortDraftEditor fields={fields} orderBy={draft.orderBy} disabled={disabled} error={error} onChange={orderBy=>update({...draft,orderBy})}/><div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={disabled||!dirty} onClick={()=>{setDraft(baseline);setError(null)}}>取消修改</Button><Button type="button" variant="primary" disabled={disabled} onClick={apply}>应用筛选</Button></div></section>
}
