import { useEffect, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Info } from '@phosphor-icons/react'
import { operatorsFor, type FieldType, type FilterDraft, type RecordQueryError } from '../record-query'
import { scalarDraft } from '../scalar-draft'
import { RecordFilterDraftEditor } from './RecordFilterEditor'
import { ScalarValueEditor } from './ScalarValueEditor'

type Field = components['schemas']['DataFieldView']
type Status = components['schemas']['DataStatusView']
type SimpleFilter = { compare?: Extract<FilterDraft,{type:'compare'}>; comparePath?:string; status?: Extract<FilterDraft,{type:'status'}>; statusPath?:string }
const labels:Record<string,string>={eq:'等于',neq:'不等于',contains:'包含',startsWith:'开头是',gt:'大于',gte:'大于等于',lt:'小于',lte:'小于等于',isNull:'为空',isNotNull:'不为空'}
const emptyValue=(type:FieldType)=>scalarDraft(type==='boolean'?false:type==='number'?0:type==='string'?'':undefined)

function simpleFilter(filter:FilterDraft):SimpleFilter|null {
  const items=filter.type==='all'?filter.items:[filter]
  if(items.length>2)return null
  const compare=items.filter((item):item is Extract<FilterDraft,{type:'compare'}>=>item.type==='compare')
  const status=items.filter((item):item is Extract<FilterDraft,{type:'status'}>=>item.type==='status')
  if(compare.length>1||status.length>1||status.some(item=>item.operator!=='eq')||compare.length+status.length!==items.length)return null
  const path=(item:FilterDraft|undefined)=>item?filter.type==='all'?`filter.items.${items.indexOf(item)}`:'filter':undefined
  return {compare:compare[0],comparePath:path(compare[0]),status:status[0],statusPath:path(status[0])}
}
const combine=({compare,status}:SimpleFilter):FilterDraft=>{const items:FilterDraft[]=[];if(compare)items.push(compare);if(status)items.push(status);return items.length===1?items[0]:{type:'all',items}}

export function GalleryRecordFilter({fields,statuses,filter,disabled=false,error=null,onChange}:{fields:Field[];statuses:Status[];filter:FilterDraft;disabled?:boolean;error?:RecordQueryError|null;onChange(filter:FilterDraft):void}) {
  const simple=simpleFilter(filter),[advanced,setAdvanced]=useState(simple===null)
  useEffect(()=>{if(simple===null)setAdvanced(true)},[simple])
  if(advanced)return <div className="grid gap-3"><div className="flex items-center justify-between"><span className="text-sm font-medium">高级条件</span><Button type="button" size="sm" variant="ghost" disabled={disabled||simple===null} onClick={()=>setAdvanced(false)}>使用简单条件</Button></div>{simple===null?<p className="text-xs text-muted">请先在高级条件中调整为一个字段条件和一个业务状态条件。</p>:null}<section aria-label="高级条件编辑器"><RecordFilterDraftEditor fields={fields} statuses={statuses} filter={filter} disabled={disabled} error={error} onChange={onChange}/></section></div>
  const current=simple??{},field=fields.find(item=>item.ref.fieldId===current.compare?.fieldId),isNull=current.compare?.operator==='isNull'||current.compare?.operator==='isNotNull'
  const fieldError=error?.path===current.comparePath?error:null,statusError=error?.path===current.statusPath?error:null
  const basicValue=current.compare&&field&&(field.type==='number'||field.type==='string'&&!/[\r\n]/.test(current.compare.value.text))&&current.compare.value.presence==='value'
  return <div className="grid gap-4">
    <section className="grid gap-3"><div className="flex items-center justify-between"><h3 className="m-0 text-sm font-semibold">字段条件</h3><Button type="button" size="sm" variant="ghost" onClick={()=>setAdvanced(true)}>高级条件</Button></div><div className="grid grid-cols-2 gap-2"><Select aria-label="字段" value={current.compare?.fieldId??null} disabled={disabled} options={fields.map(item=>({value:item.ref.fieldId,label:item.name}))} onValueChange={fieldId=>{const next=fields.find(item=>item.ref.fieldId===fieldId);onChange(combine({...current,compare:next?{type:'compare',fieldId:next.ref.fieldId,operator:'eq',value:emptyValue(next.type)}:undefined}))}}/><Select aria-label="字段运算符" value={current.compare?.operator??null} disabled={disabled||!field} clearable={false} options={(field?operatorsFor(field.type):[]).map(value=>({value,label:labels[value]}))} onValueChange={operator=>operator&&current.compare&&onChange(combine({...current,compare:{...current.compare,operator,value:operator==='isNull'||operator==='isNotNull'?scalarDraft(undefined):current.compare.value}}))}/></div>{basicValue?<div className="grid gap-1"><Input aria-label="比较值" inputMode={field.type==='number'?'decimal':undefined} value={current.compare!.value.text} disabled={disabled} aria-invalid={Boolean(fieldError)} onChange={event=>onChange(combine({...current,compare:{...current.compare!,value:{...current.compare!.value,text:event.target.value}}}))}/>{fieldError?<p role="alert" className="text-xs text-danger">{fieldError.message}</p>:null}</div>:current.compare&&field&&!isNull?<ScalarValueEditor compact presenceDisplay="contextual" id="simple-filter-value" label="比较值" type={field.type} draft={current.compare.value} disabled={disabled} error={fieldError?.message} errorTarget={fieldError?.control} onChange={value=>onChange(combine({...current,compare:{...current.compare!,value}}))}/>:null}{fieldError&&!field?<p role="alert" className="text-xs text-danger">{fieldError.message}</p>:null}</section>
    <div className="h-px bg-line" />
    <section className="grid gap-2"><h3 className="m-0 text-sm font-semibold">业务状态</h3><Select aria-label="业务状态" value={current.status?.statusId??null} disabled={disabled} options={statuses.map(item=>({value:item.statusId,label:item.name}))} onValueChange={statusId=>onChange(combine({...current,status:statusId?{type:'status',operator:'eq',statusId}:undefined}))}/>{statusError?<p role="alert" className="text-xs text-danger">{statusError.message}</p>:null}</section>
    <p className="flex items-center gap-2 text-xs text-muted"><Info className="shrink-0"/>两项条件同时满足时显示；业务状态仅属于本项目。</p>{error&&!fieldError&&!statusError?<p role="alert" className="text-xs text-danger">{error.message}</p>:null}
  </div>
}
