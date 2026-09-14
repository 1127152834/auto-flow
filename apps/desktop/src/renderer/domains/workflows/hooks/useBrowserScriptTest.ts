import {useCallback,useEffect,useRef,useState} from 'react'
import {browserScriptTestsApi as api} from '../api/browserScriptTests'
import {getBackendBaseUrl} from '../api/config'
import {jsonCopy} from '../lib/jsScript'
import {sameScriptTarget,type BrowserScriptState,type BrowserScriptTarget} from '../lib/browserScriptContract'

type Operation={id:string|null;target:BrowserScriptTarget|null;cancelled:boolean;origin:string;wake?:()=>void;recovered:boolean}
export function useBrowserScriptTest(isOpen:boolean,code:string,variables:Record<string,unknown>){
 const operation=useRef<Operation|null>(null)
 const mounted=useRef(true)
 const [busy,setBusy]=useState(false)
 const [phase,setPhase]=useState('')
 const [error,setError]=useState<string|null>(null)
 const [result,setResult]=useState<BrowserScriptState|null>(null)
 const [pageUrl,setPageUrl]=useState('')
 const cancel=useCallback(()=>{
  const active=operation.current
  if(active){active.cancelled=true;active.wake?.();if(mounted.current)setPhase('正在取消，等待服务确认')}
 },[])
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;cancel()}},[cancel])
 useEffect(()=>{setResult(null);setError(null);if(!operation.current){setPhase('');setPageUrl('')}return cancel},[isOpen,code,variables,cancel])
 const start=async()=>{
  if(operation.current)return
  let snapshot:Record<string,unknown>
  let origin:string
  try{if(!code.trim())throw new Error('请输入测试代码');snapshot=jsonCopy(variables);origin=getBackendBaseUrl()}catch(reason){setError(String(reason));return}
  const active:Operation={id:null,target:null,cancelled:false,origin,recovered:false}
  operation.current=active;setBusy(true);setResult(null);setError(null);setPhase('正在读取测试页面')
  const current=()=>operation.current===active
  const update=(callback:()=>void)=>{if(mounted.current && current())callback()}
  const wait=()=>new Promise<void>(resolve=>{
   const finish=()=>{clearTimeout(timer);active.wake=undefined;resolve()}
   const timer=setTimeout(finish,1000);active.wake=finish
  })
  try{
   const context=await api.getContext(AbortSignal.timeout(10000))
   if(active.cancelled){update(()=>setPhase('测试已取消（未提交）'));return}
   if(getBackendBaseUrl()!==active.origin)throw new Error('服务连接已变化，未提交旧页面代码')
   if(!context.success || !context.data)throw new Error(context.error || '无法读取测试页面')
   const target={browserSessionId:context.data.browserSessionId,pageId:context.data.pageId,revision:context.data.revision}
   active.target=target;active.id=context.data.activeRequestId || crypto.randomUUID();active.recovered=!!context.data.activeRequestId
   update(()=>{setPageUrl(context.data!.url);setPhase(active.recovered?'发现上次未结束的测试，请先取消或等待确认':'正在提交脚本测试')})
   let response=active.recovered
    ? await api.get(active.id,AbortSignal.timeout(10000))
    : await api.start({requestId:active.id,context:target,code,variables:snapshot},AbortSignal.timeout(10000))
   // An explicit rejection means this request did not acquire a test. An unknown response is queried, never resubmitted.
   if(!response.success && response.httpStatus && response.httpStatus>=400 && response.httpStatus<500)throw new Error(response.error || '测试请求被拒绝')
   while(current()){
    if(getBackendBaseUrl()!==active.origin)throw new Error('服务连接已变化，旧测试清理未确认；请在原工作区检查')
    if(response.success && response.data){
     if(!sameScriptTarget(response.data.context,target))throw new Error('测试响应属于其他页面，未展示结果')
     if(response.data.status!=='running'){
      update(()=>{
       setPhase(active.cancelled ? (response.data!.status==='cancelled'?'测试已取消':response.data!.status==='completed'?'测试已在取消前完成，结果未应用':'原测试已结束') : '')
       if(active.recovered)setError('上次测试已结束，请重新测试当前编辑代码')
       else {setError(response.data!.error);if(!active.cancelled)setResult(response.data!)}
      })
      return
     }
    }else if(response.httpStatus===404){throw new Error('服务未登记此测试请求，未重新执行代码')}
    else update(()=>setError(response.error || '测试状态尚未确认，正在查询原请求'))
    update(()=>setPhase(active.cancelled?'正在取消，等待服务确认':'正在等待原测试结果'))
    if(active.cancelled){
     response=await api.cancel(active.id,AbortSignal.timeout(10000))
     // Failed cancellation retains ownership; retry the same idempotent cancellation after a backoff.
     if(!response.success || response.data?.status==='running')await wait()
    }else{
     await wait()
     if(active.cancelled)continue
     response=await api.get(active.id,AbortSignal.timeout(10000))
    }
   }
  }catch(reason){update(()=>{setError(reason instanceof Error?reason.message:String(reason));setPhase('')})}
  finally{
   active.wake?.()
   if(current()){update(()=>setBusy(false));operation.current=null}
  }
 }
 return {start,cancel,busy,phase,error,result,pageUrl}
}
