import type {ApiResponse} from '../api'
import {parseApiWireError} from '../../../shared/api/client'
import {getBackendBaseUrl} from './config'
import {getStudioTransportRevision,studioFetch} from './transport'
import {isDebugControlReceipt,isDebugControlRequest,type DebugControlRequest,type DebugControlReceipt} from '../lib/debugControlContract'
/** A lost reply is resolved by the original command ID, never by issuing another step. */
export async function sendDebugControl(workflowId:string,action:'resume'|'step',request:DebugControlRequest):Promise<ApiResponse<DebugControlReceipt>> {
  if(!workflowId || !isDebugControlRequest(request))return {success:false,httpStatus:422,error:'缺少有效的调试命令和暂停标识'}
  const origin=getBackendBaseUrl(),revision=getStudioTransportRevision()
  const current=()=>revision===getStudioTransportRevision()
  const unknown=()=>({success:false,error:'调试命令结果尚未确认，请等待状态同步或停止运行'})
  try {
    const response=await studioFetch(`${origin}/api/workflows/${encodeURIComponent(workflowId)}/debug/${action}`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(10000),
    })
    const result:unknown=await response.json()
    if(!current())return unknown()
    if(response.status>=500)throw new Error('服务响应需要查询确认')
    if(isDebugControlReceipt(result,workflowId,action,request)){
      if(response.ok && result.success)return {success:true,data:result}
      if(!result.success)return {success:false,httpStatus:response.status,error:result.error || '调试命令被拒绝',data:result}
      throw new Error('调试命令状态不一致')
    }
    if(!response.ok && result && typeof result==='object' && !Array.isArray(result) &&
      (!('commandId' in result) || result.commandId===request.commandId) && !('success' in result && result.success===true)){
      const error=parseApiWireError(result)?.message || ('error' in result && typeof result.error==='string'?result.error:`HTTP ${response.status}`)
      return {success:false,httpStatus:response.status,error}
    }
    throw new Error('调试确认身份或结构错误')
  } catch {
    if(!current())return unknown()
    try {
      const response=await studioFetch(`${origin}/api/events/commands/${encodeURIComponent(request.commandId)}`,{signal:AbortSignal.timeout(10000)})
      const result:unknown=await response.json()
      if(!current() || !response.ok || !isDebugControlReceipt(result,workflowId,action,request))return unknown()
      const status=result.httpStatus
      if(typeof status!=='number' || !Number.isInteger(status) || status<200 || status>599)return unknown()
      if(result.success && status>=400)return unknown()
      return {success:result.success,httpStatus:status,data:result,...(!result.success?{error:result.error || '调试命令被拒绝'}:{})}
    } catch {return unknown()}
  }
}
