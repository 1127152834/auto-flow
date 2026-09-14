import type {components} from '../../../shared/api/generated'
export type DebugPauseContext = components['schemas']['StudioDebugPauseContext']
export type DebugControlRequest = components['schemas']['StudioDebugControlRequest']
export type DebugControlReceipt = components['schemas']['StudioDebugControlReceipt']
export type DebugControlLookup = components['schemas']['StudioDebugControlLookup']
export function isDebugPauseContext(value:unknown):value is DebugPauseContext {
  if(!value || typeof value!=='object' || Array.isArray(value))return false
  const context=value as Record<string,unknown>
  return typeof context.pauseId==='string' && !!context.pauseId.trim() && Number.isSafeInteger(context.controlRevision) && Number(context.controlRevision)>=0
}
export function isDebugControlRequest(value:unknown):value is DebugControlRequest {
  return isDebugPauseContext(value) && 'commandId' in value && typeof value.commandId==='string' && !!value.commandId.trim() && Object.keys(value).every(key=>['pauseId','controlRevision','commandId'].includes(key))
}
export function isDebugControlReceipt(value:unknown,workflowId:string,action:'resume'|'step',request:DebugControlRequest):value is DebugControlReceipt {
  if(!isDebugPauseContext(value))return false
  const receipt=value as Record<string,unknown>
  return receipt.commandId===request.commandId && receipt.workflowId===workflowId && receipt.action===action &&
    receipt.pauseId===request.pauseId && receipt.controlRevision===request.controlRevision && typeof receipt.success==='boolean' &&
    (receipt.success?receipt.error===null:typeof receipt.error==='string' && !!receipt.error.trim())
}
