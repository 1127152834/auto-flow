import type {components} from '../../../shared/api/generated'
export type DebugPauseContext = components['schemas']['StudioDebugPauseContext']
export type DebugControlRequest = components['schemas']['StudioDebugControlRequest']
export type DebugControlReceipt = components['schemas']['StudioDebugControlReceipt']
export type DebugControlLookup = components['schemas']['StudioDebugControlLookup']
export type DebugVariablesRequest = components['schemas']['StudioDebugVariablesRequest']
export type DebugVariablesReceipt = components['schemas']['StudioDebugVariablesReceipt']
function isJsonValue(value:unknown,seen=new Set<object>()):boolean {
  if(value===null || typeof value==='string' || typeof value==='boolean')return true
  if(typeof value==='number')return Number.isFinite(value)
  if(typeof value!=='object')return false
  if(seen.has(value))return false
  seen.add(value)
  const valid=Array.isArray(value)
    ? value.every(item=>isJsonValue(item,seen))
    : Object.getPrototypeOf(value)===Object.prototype && Object.values(value as Record<string,unknown>).every(item=>isJsonValue(item,seen))
  seen.delete(value)
  return valid
}
export function isDebugPauseContext(value:unknown):value is DebugPauseContext {
  if(!value || typeof value!=='object' || Array.isArray(value))return false
  const context=value as Record<string,unknown>
  return typeof context.runId==='string' && !!context.runId.trim() && typeof context.pauseId==='string' && !!context.pauseId.trim() && Number.isSafeInteger(context.controlRevision) && Number(context.controlRevision)>=0
}
export function isDebugControlRequest(value:unknown):value is DebugControlRequest {
  return isDebugPauseContext(value) && 'commandId' in value && typeof value.commandId==='string' && !!value.commandId.trim() && Object.keys(value).every(key=>['runId','pauseId','controlRevision','commandId'].includes(key))
}
export function isDebugControlReceipt(value:unknown,workflowId:string,action:'resume'|'step',request:DebugControlRequest):value is DebugControlReceipt {
  if(!isDebugPauseContext(value))return false
  const receipt=value as Record<string,unknown>
  return receipt.commandId===request.commandId && receipt.workflowId===workflowId && receipt.action===action &&
    receipt.runId===request.runId && receipt.pauseId===request.pauseId && receipt.controlRevision===request.controlRevision && typeof receipt.success==='boolean' &&
    (receipt.success?receipt.error===null:typeof receipt.error==='string' && !!receipt.error.trim())
}
export function isDebugVariablesRequest(value:unknown):value is DebugVariablesRequest {
  if(!isDebugPauseContext(value) || !value || typeof value!=='object' || Array.isArray(value))return false
  const request=value as Record<string,unknown>
  if(typeof request.commandId!=='string' || !request.commandId.trim() || !Array.isArray(request.changes) || request.changes.length<1 || request.changes.length>200)return false
  const names=new Set<string>()
  if(!request.changes.every(change=>{
    if(!change || typeof change!=='object' || Array.isArray(change))return false
    const item=change as Record<string,unknown>
    if(Object.keys(item).some(key=>!['name','value'].includes(key)) || typeof item.name!=='string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(item.name) || item.name.length>128 || names.has(item.name))return false
    names.add(item.name);return 'value' in item && isJsonValue(item.value)
  }))return false
  if(Object.keys(request).some(key=>!['runId','pauseId','controlRevision','commandId','changes'].includes(key)))return false
  try{return new Blob([JSON.stringify(request)]).size<=1024*1024}catch{return false}
}
export function isDebugVariablesReceipt(value:unknown,workflowId:string,request:DebugVariablesRequest):value is DebugVariablesReceipt {
  if(!value || typeof value!=='object' || Array.isArray(value))return false
  const receipt=value as Record<string,unknown>
  if(!isDebugVariablesRequest({runId:receipt.runId,pauseId:receipt.pauseId,controlRevision:receipt.controlRevision,commandId:receipt.commandId,changes:receipt.changes}))return false
  return receipt.commandId===request.commandId && receipt.workflowId===workflowId && receipt.runId===request.runId &&
    receipt.pauseId===request.pauseId && receipt.controlRevision===request.controlRevision && JSON.stringify(receipt.changes)===JSON.stringify(request.changes) &&
    typeof receipt.success==='boolean' && (receipt.success?receipt.error===null:typeof receipt.error==='string' && !!receipt.error.trim())
}
