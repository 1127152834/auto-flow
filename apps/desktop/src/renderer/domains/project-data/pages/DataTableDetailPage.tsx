import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { createProjectDataApi } from '../api'
import { createDataCatalogApi } from '../catalog-api'
import { DataRecordsTable } from '../components/DataRecordsTable'
import { RecordFilterEditor } from '../components/RecordFilterEditor'
import { emptyRecordQuery, type RecordQuery } from '../record-query'
import { createRecordsApi, type RecordKey } from '../records-api'
import type { DataTableTab } from '../types'

type Schema=components['schemas'];type Table=Schema['DataTableView']
export type DataTableDetailPageProps={workspaceKey:string;instanceId:string;projectId:string;tableId:string;tab:DataTableTab;client:StreamingApiClient;disabled?:boolean;readonly?:boolean;onBack():void;onTabChange(tab:DataTableTab):void;registerLeaveGuard(guard:(()=>Promise<boolean>)|null):void}
const labels:Record<DataTableTab,string>={records:'记录',fields:'字段',statuses:'状态',source:'来源',settings:'设置'}
const errorMessage=(value:unknown)=>value instanceof Error?value.message:'读取数据失败'
function cellLabel(value:Schema['DataCellView']):string{if(!value.readable)return'不可读取';if(value.error)return`读取失败：${value.error}`;if(value.value===null)return'空值';if(value.value==='')return'空字符串';if(typeof value.value==='boolean')return value.value?'是':'否';if(typeof value.value==='object')return`${value.value.value}${value.value.precision==='datetime'?` ${value.value.offset??'无时区'}`:''}`;return String(value.value)}

export function DataTableDetailPage(props:DataTableDetailPageProps){
  return <DataTableDetail key={JSON.stringify([props.workspaceKey,props.projectId,props.tableId])} {...props}/>
}

function DataTableDetail({workspaceKey,instanceId,projectId,tableId,tab,client,disabled=false,readonly=false,onBack,onTabChange,registerLeaveGuard}:DataTableDetailPageProps){
  const [table,setTable]=useState<Table|null>(null)
  const [query,setQuery]=useState<RecordQuery>(emptyRecordQuery()),[recordPage,setRecordPage]=useState(1),[filterDirty,setFilterDirty]=useState(false),[generationWarning,setGenerationWarning]=useState<string|null>(null),[filterSession,setFilterSession]=useState(0)
  const [detailTarget,setDetailTarget]=useState<{key:RecordKey;generation:string}|null>(null),[leaveOpen,setLeaveOpen]=useState(false)
  const leaveResolve=useRef<((allowed:boolean)=>void)|null>(null),leaveAction=useRef<(()=>void)|null>(null),dirtyRef=useRef(filterDirty)
  const prefix=useMemo(()=>[workspaceKey,instanceId,'project-data',projectId,'table',tableId] as const,[workspaceKey,instanceId,projectId,tableId])
  const tableApi=useMemo(()=>createProjectDataApi(client,projectId),[client,projectId])
  const tableQuery=useQuery({queryKey:[...prefix,'view'],queryFn:({signal})=>tableApi.get(tableId,signal),placeholderData:previous=>previous})
  useLayoutEffect(()=>{dirtyRef.current=filterDirty},[filterDirty])
  useEffect(()=>{const next=tableQuery.data;if(!next)return;if(table&&table.datasetGeneration!==next.datasetGeneration&&dirtyRef.current){setGenerationWarning('数据代次已变化；请先处理当前筛选草稿再重新载入。');return}if(table?.datasetGeneration!==next.datasetGeneration){setQuery(emptyRecordQuery());setRecordPage(1);setFilterSession(value=>value+1);setDetailTarget(null)}setTable(next);setGenerationWarning(null)},[table,tableQuery.data])
  const generation=table?.datasetGeneration
  const catalogApi=useMemo(()=>generation?createDataCatalogApi(client,{projectId,tableId,datasetGeneration:generation}):null,[client,generation,projectId,tableId])
  const catalogQuery=useQuery({queryKey:[...prefix,generation,'catalog'],queryFn:async({signal})=>{if(!catalogApi)throw new Error('数据表不可用');return Promise.all([catalogApi.fields(signal),catalogApi.statuses(signal)])},enabled:Boolean(catalogApi)&&!generationWarning})
  const recordsApi=useMemo(()=>generation?createRecordsApi(client,{projectId,tableId,datasetGeneration:generation}):null,[client,generation,projectId,tableId])
  const recordsQuery=useQuery({queryKey:[...prefix,generation,'records',query,recordPage],queryFn:({signal})=>{if(!recordsApi)throw new Error('数据表不可用');return recordsApi.list({filter:query.filter,orderBy:query.orderBy,page:recordPage,pageSize:50},signal)},enabled:Boolean(recordsApi)&&!generationWarning})
  const detailQuery=useQuery({queryKey:[...prefix,detailTarget?.generation,'record',detailTarget?.key],queryFn:({signal})=>{if(!recordsApi||!detailTarget||detailTarget.generation!==generation)throw new Error('记录不可用');return recordsApi.get(detailTarget.key,signal)},enabled:Boolean(recordsApi&&detailTarget&&detailTarget.generation===generation)})
  const fields=catalogQuery.data?.[0].items??[],statuses=catalogQuery.data?.[1].items??[],page=recordsQuery.data
  const askLeave=useCallback((action?:()=>void)=>{if(leaveResolve.current)return Promise.resolve(false);return new Promise<boolean>(resolve=>{if(!dirtyRef.current){action?.();resolve(true);return}leaveResolve.current=resolve;leaveAction.current=action??null;setLeaveOpen(true)})},[])
  useLayoutEffect(()=>{registerLeaveGuard(filterDirty?()=>askLeave():null);return()=>registerLeaveGuard(null)},[askLeave,filterDirty,registerLeaveGuard])
  useEffect(()=>()=>{leaveResolve.current?.(false)},[])
  const acceptLatestGeneration=()=>void askLeave(()=>{const next=tableQuery.data;if(!next)return;setFilterDirty(false);setFilterSession(value=>value+1);setQuery(emptyRecordQuery());setRecordPage(1);setDetailTarget(null);setTable(next);setGenerationWarning(null)})
  const loadingTable=tableQuery.isPending&&!table,tableError=tableQuery.error?errorMessage(tableQuery.error):null
  if(loadingTable&&!table)return <div role="status" aria-label="正在加载数据表"><Skeleton className="h-28"/></div>
  if(!table)return <section role="alert" className="rounded-card border border-line p-6"><p>{tableError??'数据表不可用'}</p><div className="flex gap-2"><Button onClick={()=>void tableQuery.refetch()}>重新载入</Button><Button variant="ghost" onClick={onBack}>返回数据表</Button></div></section>
  return <section className="grid min-w-0 gap-5"><header className="flex flex-wrap items-start justify-between gap-3"><div><Button variant="ghost" disabled={disabled} onClick={onBack}>返回数据表</Button><h1 className="m-0 break-words text-2xl font-semibold">{table.name}</h1><p className="text-sm text-muted">{table.description||'暂无说明'}</p></div><Badge>{readonly?'只读':table.sourceKind==='local'?'本地数据':table.sourceKind==='excel'?'Excel 导入':table.sourceKind==='sheets'?'Google Sheets':'来源未配置'}</Badge></header>{tableError?<p role="alert">{tableError}<Button onClick={()=>void tableQuery.refetch()}>重新载入</Button></p>:null}{generationWarning?<p role="alert">{generationWarning} <Button onClick={acceptLatestGeneration}>处理草稿并载入新代次</Button></p>:null}
    <Tabs value={tab} onValueChange={value=>onTabChange(value as DataTableTab)}><TabsList className="w-full justify-start overflow-x-auto">{(Object.keys(labels) as DataTableTab[]).map(value=><TabsTrigger key={value} value={value} disabled={disabled}>{labels[value]}</TabsTrigger>)}</TabsList>
      <TabsContent value="records" className="grid gap-5"><RecordFilterEditor key={`${projectId}:${tableId}:${table.datasetGeneration}:${filterSession}`} fields={fields} statuses={statuses} appliedQuery={query} disabled={disabled||Boolean(generationWarning)} onDirtyChange={setFilterDirty} onApply={next=>{setQuery(next);setRecordPage(1)}}/><DataRecordsTable page={page} fields={fields} statuses={statuses} loading={recordsQuery.isPending} error={recordsQuery.error?errorMessage(recordsQuery.error):catalogQuery.error?errorMessage(catalogQuery.error):undefined} hasFilters={query.filter.type!=='all'||query.filter.items.length>0||query.orderBy.length>0} readonly onRetry={()=>void (catalogQuery.error?catalogQuery.refetch():recordsQuery.refetch())} onOpen={record=>setDetailTarget({key:record.ref.recordKey,generation:record.ref.datasetGeneration})} onPageChange={setRecordPage}/></TabsContent>
      <TabsContent value="fields"><section aria-label="字段目录" className="grid gap-3">{catalogQuery.isPending?<Skeleton className="h-24"/>:catalogQuery.error?<p role="alert">{errorMessage(catalogQuery.error)} <Button onClick={()=>void catalogQuery.refetch()}>重新载入</Button></p>:fields.length===0?<p>暂无字段</p>:fields.map(field=><article key={field.ref.fieldId} className="rounded-card border border-line p-4"><h2 className="m-0 break-words text-base font-semibold">{field.name}</h2><p className="text-sm text-muted">{field.type==='string'?'文本':field.type==='number'?'数字':field.type==='boolean'?'布尔':'日期'} · {field.required?'必填':'可选'} · {field.formula?'公式字段':field.writable?'可写':'只读'} · 修订 {field.fieldRevision}</p></article>)}</section></TabsContent>
      <TabsContent value="statuses"><section aria-label="状态目录" className="grid gap-3">{catalogQuery.isPending?<Skeleton className="h-24"/>:catalogQuery.error?<p role="alert">{errorMessage(catalogQuery.error)} <Button onClick={()=>void catalogQuery.refetch()}>重新载入</Button></p>:statuses.length===0?<p>暂无状态</p>:statuses.map(status=><article key={status.statusId} className="flex items-center gap-3 rounded-card border border-line p-4"><span aria-label={`颜色 ${status.color}`} className="h-4 w-4 rounded-full" style={{backgroundColor:status.color}}/><strong>{status.name}</strong><span className="text-sm text-muted">顺序 {status.order} · 修订 {status.statusRevision}</span></article>)}</section></TabsContent>
      <TabsContent value="source"><dl className="grid gap-3 rounded-card border border-line p-5"><dt>来源类型</dt><dd>{table.sourceKind==='local'?'本地数据':table.sourceKind==='excel'?'Excel 导入':table.sourceKind==='sheets'?'Google Sheets':'来源未配置'}</dd><dt>身份规则</dt><dd>{table.identity.mode==='system'?'系统身份':`字段 ${table.identity.fieldId}`}</dd><dt>同步状态</dt><dd>{table.syncSummary.status==='notApplicable'?'不适用':table.syncSummary.status==='pending'?'待同步':table.syncSummary.status==='confirmed'?'已确认':'未知'} · 待处理 {table.syncSummary.pendingCount} · 未知 {table.syncSummary.unknownCount}</dd>{table.syncSummary.lastConfirmedAt?<><dt>最近确认</dt><dd>{table.syncSummary.lastConfirmedAt}</dd></>:null}</dl></TabsContent>
      <TabsContent value="settings"><dl className="grid gap-3 rounded-card border border-line p-5"><dt>名称</dt><dd className="break-words">{table.name}</dd><dt>说明</dt><dd className="break-words">{table.description||'暂无说明'}</dd><dt>表修订</dt><dd>表修订 {table.tableRevision}</dd><dt>数据代次</dt><dd className="break-all">{table.datasetGeneration}</dd><dt>更新时间</dt><dd>{table.updatedAt}</dd></dl></TabsContent>
    </Tabs>
    <Modal open={detailTarget!==null} onOpenChange={open=>{if(!open)setDetailTarget(null)}} title="记录详情" description={detailTarget?`${detailTarget.key.type} · ${detailTarget.key.value}`:''} size="small"><div className="grid gap-3">{detailQuery.error?<p role="alert">{errorMessage(detailQuery.error)} <Button onClick={()=>void detailQuery.refetch()}>重新载入</Button></p>:!detailQuery.data?<Skeleton className="h-24"/>:detailQuery.data.values.map(cell=><div key={cell.fieldId}><strong>{fields.find(field=>field.ref.fieldId===cell.fieldId)?.name??cell.fieldId}</strong><p className="whitespace-pre-wrap break-words">{cellLabel(cell)}</p></div>)}</div></Modal>
    <AlertDialog open={leaveOpen} onOpenChange={next=>{if(!next){setLeaveOpen(false);leaveResolve.current?.(false);leaveResolve.current=null;leaveAction.current=null}}}><AlertDialogContent><AlertDialogTitle>放弃筛选修改？</AlertDialogTitle><AlertDialogDescription>未应用的筛选和排序修改将丢失。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" onClick={()=>{const action=leaveAction.current;setLeaveOpen(false);setFilterDirty(false);setFilterSession(value=>value+1);leaveResolve.current?.(true);leaveResolve.current=null;leaveAction.current=null;action?.()}}>放弃并离开</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </section>
}
