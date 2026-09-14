import {useEffect,useRef,useState} from 'react'
import {browserApi} from '../api'
import {getStudioTransportRevision} from '../api/transport'
import type {components} from '../../../shared/api/generated'
import {UrlInput} from './controls/url-input'
import {Button} from './controls/button'
type Pages=components['schemas']['StudioBrowserPages']
/** Approved target-page controls; the existing browser service owns actual page operations. */
export function BrowserPagesPanel({url,onUrlChange,blocked=false,onBegin=()=>true,onEnd=()=>{},onError=()=>{}}:{url:string;onUrlChange:(url:string)=>void;blocked?:boolean;onBegin?:()=>boolean;onEnd?:()=>void;onError?:(message:string)=>void}) {
 const [state,setState]=useState<Pages|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const active=useRef(true),pending=useRef(false),serial=useRef(0),owner=useRef(getStudioTransportRevision()),fetching=useRef(false)
 const refresh=async()=>{
  if(pending.current||fetching.current)return
  fetching.current=true
  const request=++serial.current
  try{
   const result=await browserApi.pages()
   if(!active.current||request!==serial.current)return
   if(!result.success||!result.data){setError(result.error||'无法读取页面');return}
   owner.current=getStudioTransportRevision();setState(result.data)
  }catch(cause){if(active.current&&request===serial.current)setError(String(cause))}
  finally{fetching.current=false}
 }
 useEffect(()=>{
  active.current=true;void refresh()
  const timer=setInterval(()=>void refresh(),1000)
  return()=>{active.current=false;serial.current++;clearInterval(timer)}
 },[])
 const command=async(action:'select'|'focus'|'navigate',pageId=state?.targetPageId)=>{
  if(!state||!pageId||pending.current||blocked)return
  if(owner.current!==getStudioTransportRevision()){setState(null);setError('浏览器所属服务已变更，请刷新页面列表');return}
  if(!onBegin())return
  const connection=getStudioTransportRevision(),session=state.sessionId
  pending.current=true;serial.current++;setBusy(true);setError('')
  try{
   const response=await browserApi.page({sessionId:session,expectedRevision:state.revision,pageId,action,url:action==='navigate'?url:null})
   if(!active.current||connection!==getStudioTransportRevision())return
   if(!response.success||!response.data){setError(response.error||'页面操作未确认');onError(response.error||'页面操作未确认');return}
   if(response.data.sessionId!==session)throw Error('浏览器会话已变化，操作结果未应用')
   setState(response.data)
  }catch(cause){if(active.current)setError(String(cause))}
  finally{pending.current=false;onEnd();if(active.current)setBusy(false)}
 }
 return <section aria-label="浏览器目标页面" className="space-y-2">
  <label className="block text-xs">目标标签页<select aria-label="目标标签页" disabled={!state||busy||blocked} value={state?.targetPageId??''} onChange={event=>void command('select',event.target.value)}>
   <option value="" disabled>请选择目标页面</option>
   {state?.pages.map(page=><option key={page.pageId} value={page.pageId}>{page.title||'无标题'} · {page.url}</option>)}
  </select></label>
  {state&&!state.targetPageId&&<p role="status">目标页面已关闭或未选择，请明确选择页面。</p>}
  <div className="flex gap-2"><Button size="sm" disabled={!state?.targetPageId||busy||blocked} onClick={()=>void command('focus')}>聚焦目标页</Button><Button size="sm" disabled={busy||blocked} onClick={()=>void refresh()}>刷新页面列表</Button></div>
  <label className="block text-xs">导航到网址</label>
  <div className="flex gap-2"><UrlInput value={url} onChange={onUrlChange} placeholder="https://example.com"/><Button size="sm" disabled={!url||!state?.targetPageId||busy||blocked} onClick={()=>void command('navigate')}>跳转</Button></div>
  {error&&<p role="alert">{error}</p>}
 </section>
}
