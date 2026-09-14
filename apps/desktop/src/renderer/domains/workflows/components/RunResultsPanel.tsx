import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { workflowApi } from '../api'
import { getStudioTransportRevision } from '../api/transport'
import { DataTable } from './DataTable'
import { DialogPortal } from './controls/dialog-portal'

/** Approved run-history adapter around the migrated WebRPA table; results remain immutable. */
export function RunResultsPanel({runId}:{runId:string}) {
  const [page,setPage]=useState<components['schemas']['StudioRunResultPage']|null>(null)
  const [cursor,setCursor]=useState(0)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const [exporting,setExporting]=useState(false)
  const [detail,setDetail]=useState<{title:string;text:string;loading:boolean}|null>(null)
  const request=useRef(0), valueRequest=useRef(0), mounted=useRef(true)
  const load=useCallback(async(nextCursor=0,through?:number)=>{
    const token=++request.current, connection=getStudioTransportRevision()
    setLoading(true);setError('');setDetail(null);valueRequest.current++
    const result=await workflowApi.getRunResults(runId,nextCursor,100,through)
    if(!mounted.current||token!==request.current||connection!==getStudioTransportRevision())return
    setLoading(false)
    if(!result.success||!result.data){setError(result.error||'运行结果读取失败');return}
    setPage(result.data);setCursor(nextCursor)
  },[runId])
  useEffect(()=>{
    mounted.current=true
    const refresh=()=>{setPage(null);setExporting(false);void load()}
    void load()
    window.addEventListener('studio:transport-changed',refresh)
    window.addEventListener('studio:connection-restored',refresh)
    return()=>{
      mounted.current=false;request.current++;valueRequest.current++
      window.removeEventListener('studio:transport-changed',refresh)
      window.removeEventListener('studio:connection-restored',refresh)
    }
  },[load])
  const rows=useMemo(()=>page?.items.map(row=>({...row.values,...Object.fromEntries(Object.entries(row.largeValues??{}).map(([key,value])=>[key,`${value}…（点击读取完整值）`]))}))||[],[page])
  const columns=useMemo(()=>Array.from(new Set(rows.flatMap(row=>Object.keys(row)))),[rows])
  const inspect=async(index:number,key:string)=>{
    const row=page?.items[index]
    if(!row)return
    const title=`结果 ${row.sequence} · ${key} · 节点 ${row.nodeId} · 执行 ${row.executionId}`
    const token=++valueRequest.current,connection=getStudioTransportRevision()
    if(!Object.hasOwn(row.largeValues??{},key)){setDetail({title,text:JSON.stringify(row.values[key],null,2),loading:false});return}
    setDetail({title,text:'',loading:true})
    const result=await workflowApi.getRunResultValue(runId,row.sequence,key)
    if(!mounted.current||token!==valueRequest.current||connection!==getStudioTransportRevision())return
    setDetail({title,text:result.success&&result.data?JSON.stringify(result.data.value,null,2):result.error||'结果值读取失败',loading:false})
  }
  const download=async()=>{
    if(!page||exporting)return
    setExporting(true);setError('')
    const connection=getStudioTransportRevision()
    const result=await workflowApi.exportRunResults(runId,page.throughSequence)
    if(!mounted.current||connection!==getStudioTransportRevision())return
    setExporting(false)
    if(!result.success||!result.data){setError(result.error||'结果导出失败，未使用其他运行的数据');return}
    const url=URL.createObjectURL(result.data),link=document.createElement('a')
    link.href=url;link.download=`results-${runId}.jsonl`;link.click();URL.revokeObjectURL(url)
  }
  return <section aria-label="运行结果" className="flex min-h-0 flex-1 flex-col">
    <div className="flex flex-wrap items-center gap-3 px-3 py-2 text-xs">
      <span>运行 {runId} · {page?`${cursor+page.items.length}/${page.total}`:'尚未读取'}</span>
      <button disabled={loading} onClick={()=>void load()}>刷新结果</button>
      <button disabled={loading||!page||cursor===0} onClick={()=>void load(Math.max(0,cursor-100),page?.throughSequence)}>上一页结果</button>
      <button disabled={loading||page?.nextCursor==null} onClick={()=>void load(page!.nextCursor!,page!.throughSequence)}>下一页结果</button>
      <button disabled={!page||exporting} onClick={()=>void download()}>{exporting?'正在导出结果…':'导出本次运行结果'}</button>
      <span>每页100条；筛选和排序作用于本页。点击单元格查看完整值。</span>
    </div>
    {loading&&<p role="status" className="px-3 text-xs">正在读取运行结果…</p>}
    {error&&<p role="alert" className="px-3 text-xs text-red-600">{error}</p>}
    {page&&page.total===0&&<p className="px-3 text-xs">本次运行没有结果</p>}
    {page&&page.items.length>0&&<DataTable key={`${runId}:${cursor}:${page.throughSequence}`} readOnly data={rows} columns={columns} displayMode="head" onInspect={(index,key)=>void inspect(index,key)}/>}
    {detail&&<DialogPortal><div className="fixed inset-0 z-[1200] grid place-items-center bg-black/30"><section role="dialog" aria-modal="true" aria-label="完整结果值" className="flex w-[min(90vw,900px)] flex-col gap-3 rounded-lg border bg-[hsl(var(--card))] p-4">
      <strong className="break-all text-sm">{detail.title}</strong>
      {detail.loading?<p role="status">正在读取完整结果…</p>:<textarea aria-label="完整结果内容" readOnly value={detail.text} className="h-72 w-full resize-y rounded border bg-transparent p-2 font-mono text-xs"/>}
      <button onClick={()=>{valueRequest.current++;setDetail(null)}}>关闭结果详情</button>
    </section></div></DialogPortal>}
  </section>
}
